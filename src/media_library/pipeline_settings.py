"""Alcance declarativo del orquestador, sin implementar servicios de medios."""

from dataclasses import asdict, dataclass, field

STAGES = ("preflight", "import_review", "inventory", "plan", "metadata", "normalize",
          "compression", "installation", "export", "audit", "delivery", "close")
FILE_STAGES = STAGES[4:-1]
DEFAULT_MODES = {"import_review": "manual", "metadata": "manual", "normalize": "manual",
                 "compression": "manual", "installation": "auto", "export": "manual",
                 "audit": "manual", "delivery": "disabled"}


@dataclass(frozen=True)
class PipelineSettings:
    include: list[str] = field(default_factory=lambda: ["*"])
    modes: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODES))
    compression_profile: str = "archive-720p30 (pendiente de integrar)"

    def effective(self):
        return asdict(self)


def parse_settings(raw):
    if not isinstance(raw, dict) or set(raw) - {"include", "modes", "compression_profile"}:
        raise ValueError("Campos inválidos en pipeline")
    include = raw.get("include", ["*"])
    if not isinstance(include, list) or not include or any(not isinstance(p, str) or not p or p.startswith("/") or ".." in p.split("/") or "\0" in p for p in include):
        raise ValueError("pipeline.include requiere patrones relativos no vacíos")
    modes = raw.get("modes", {})
    if not isinstance(modes, dict) or set(modes) - set(DEFAULT_MODES) or any(value not in ("auto", "manual", "disabled") for value in modes.values()):
        raise ValueError("Modos de etapa inválidos")
    if modes.get("import_review", "manual") == "auto":
        raise ValueError("La revisión de importación es humana o deshabilitada")
    profile = raw.get("compression_profile", PipelineSettings().compression_profile)
    if not isinstance(profile, str) or not profile.strip() or "\0" in profile:
        raise ValueError("Perfil de compresión inválido")
    return PipelineSettings(list(include), {**DEFAULT_MODES, **modes}, profile)
