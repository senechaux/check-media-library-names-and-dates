"""Lectura estricta y preflight de solo lectura; no crea destinos."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
import fnmatch
import json
import math
import os
import shutil
import tomllib
import unicodedata

from .process import run_tool
from .pipeline_settings import parse_settings
from .date_settings import parse_date_settings


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    executable: str
    version_args: tuple[str, ...] = ("-version",)
    capability_args: tuple[str, ...] = ("-h", "full")
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    source: Path
    workspace: Path
    archive: Path
    export: Path
    exclude: tuple[str, ...]
    timeout_seconds: float
    reserve_bytes: int
    tools: dict[str, Tool]
    pipeline: dict = field(default_factory=dict)
    dates: dict = field(default_factory=dict)

    def effective(self):
        data = asdict(self)
        for key in ("source", "workspace", "archive", "export"):
            data[key] = str(data[key])
        if not self.pipeline:
            data.pop("pipeline")  # Compatible con manifiestos del núcleo anteriores.
        if not self.dates:
            data.pop("dates")
        return json.loads(json.dumps(data))

    def excluded(self, relative):
        relative = Path(relative)
        candidates = [relative.as_posix(), *[p.as_posix() for p in relative.parents if p != Path(".")]]
        return any(fnmatch.fnmatchcase(candidate, pattern) for candidate in candidates for pattern in self.exclude)


def _keys(data, allowed, section):
    if not isinstance(data, dict) or set(data) - set(allowed):
        raise ConfigError(f"Campos inválidos en {section}")


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(s, str) or not s or "\0" in s for s in value):
        raise ConfigError(f"{name} requiere una lista de textos no vacíos")
    return tuple(value)


def load_config(filename):
    filename = Path(filename).resolve(strict=True)
    with filename.open("rb") as handle:
        data = tomllib.load(handle)
    _keys(data, ("paths", "inventory", "execution", "tools", "pipeline", "dates"), "raíz")
    paths = data.get("paths", {})
    _keys(paths, ("source", "workspace", "archive", "export"), "paths")
    if set(paths) != {"source", "workspace", "archive", "export"}:
        raise ConfigError("Se requieren las cuatro rutas")
    resolved = {}
    for key, value in paths.items():
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            raise ConfigError(f"Ruta inválida: {key}")
        resolved[key] = (filename.parent / Path(value).expanduser()).resolve()
    inventory = data.get("inventory", {})
    execution = data.get("execution", {})
    _keys(inventory, ("exclude",), "inventory")
    _keys(execution, ("timeout_seconds", "reserve_bytes"), "execution")
    exclude = _strings(inventory.get("exclude", [".DS_Store", ".localized", "**/.DS_Store", "**/.localized"]), "exclude")
    if any(p.startswith("/") or ".." in Path(p).parts for p in exclude):
        raise ConfigError("Exclusiones relativas al origen, sin '..'")
    timeout = execution.get("timeout_seconds", 60)
    reserve = execution.get("reserve_bytes", 1048576)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError("timeout_seconds debe ser positivo y finito")
    if type(reserve) is not int or reserve < 0:
        raise ConfigError("reserve_bytes debe ser un entero no negativo")
    tools = {}
    tool_data = data.get("tools", {})
    if not isinstance(tool_data, dict):
        raise ConfigError("tools debe ser una tabla")
    for name, raw in tool_data.items():
        _keys(raw, ("executable", "version_args", "capability_args", "required_capabilities"), f"tools.{name}")
        executable = raw.get("executable", name)
        if not isinstance(executable, str) or not executable or "\0" in executable:
            raise ConfigError("Ejecutable inválido")
        if "/" in executable:
            executable = str((filename.parent / executable).resolve())
        tools[name] = Tool(executable, _strings(raw.get("version_args", ["-version"]), "version_args"),
                           _strings(raw.get("capability_args", ["-h", "full"]), "capability_args"),
                           _strings(raw.get("required_capabilities", []), "required_capabilities"))
    try:
        pipeline = parse_settings(data["pipeline"]).effective() if "pipeline" in data else {}
        dates = parse_date_settings(data["dates"]) if "dates" in data else {}
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    config = Config(**resolved, exclude=exclude, timeout_seconds=timeout, reserve_bytes=reserve, tools=tools, pipeline=pipeline, dates=dates)
    validate_paths(config)
    return config


def existing_parent(path):
    while not path.exists():
        if path.is_symlink():
            raise ConfigError(f"Enlace roto: {path}")
        path = path.parent
    if not path.is_dir():
        raise ConfigError(f"No es directorio: {path}")
    return path


def validate_paths(config):
    paths = [config.source, config.workspace, config.archive, config.export]
    if any(path.resolve() != path for path in paths):
        raise ConfigError("Las rutas han cambiado desde su resolución")
    for i, path in enumerate(paths):
        for other in paths[i + 1:]:
            left = Path(unicodedata.normalize("NFD", str(path)).casefold())
            right = Path(unicodedata.normalize("NFD", str(other)).casefold())
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ConfigError(f"Rutas solapadas: {path} y {other}")
    if not config.source.is_dir() or not os.access(config.source, os.R_OK | os.X_OK):
        raise ConfigError("El origen no existe o no es legible")
    for path in paths[1:]:
        parent = existing_parent(path)
        if not os.access(parent, os.W_OK | os.X_OK):
            raise ConfigError(f"Destino no escribible: {path}")


def require_space(path, size, reserve=0):
    if shutil.disk_usage(existing_parent(Path(path))).free < size + reserve:
        raise ConfigError(f"Espacio insuficiente: {path}")


def preflight(config, *, estimates=None, runner=run_tool):
    validate_paths(config)
    # Sumar las reservas/estimaciones en cada volumen, no comparar copias aisladas.
    volumes = {}
    for name in ("workspace", "archive", "export"):
        path = getattr(config, name)
        parent = existing_parent(path)
        device = parent.stat().st_dev
        amount = (estimates or {}).get(name, 0)
        if type(amount) is not int or amount < 0:
            raise ConfigError("Estimación de espacio inválida")
        previous = volumes.get(device, (parent, config.reserve_bytes))
        volumes[device] = (parent, previous[1] + amount)
    for parent, amount in volumes.values():
        require_space(parent, amount)
    versions = {}
    for name, tool in config.tools.items():
        result = runner([tool.executable, *tool.version_args], timeout=config.timeout_seconds).check()
        versions[name] = (result.stdout + result.stderr).strip()
        if tool.required_capabilities:
            help_result = runner([tool.executable, *tool.capability_args], timeout=config.timeout_seconds).check()
            help_text = help_result.stdout + help_result.stderr
            if any(capability not in help_text for capability in tool.required_capabilities):
                raise ConfigError(f"Capacidades insuficientes: {name}")
    return versions
