"""Políticas temporales explícitas, congeladas por ejecución."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .capture_dates import fixed_offset

DEFAULTS = {"policy": "review", "timezone": None, "fold": None, "offset": None,
            "source_tag": None, "date": None, "allow_create_date_fallback": False,
            "quicktime_semantics": "unknown", "remove_historical": False,
            "discard_description": False, "set_file_modify_date": False, "set_file_create_date": False}


def validate_decision(raw, *, partial=False):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Opciones de fecha desconocidas")
    value = {**DEFAULTS, **raw}
    if value["policy"] not in ("review", "filename-to-metadata", "metadata-to-filename"):
        raise ValueError("Política temporal inválida")
    if value["quicktime_semantics"] not in ("unknown", "utc", "local"):
        raise ValueError("Semántica QuickTime inválida")
    if value["fold"] is not None and (type(value["fold"]) is not int or value["fold"] not in (0, 1)):
        raise ValueError("fold debe ser 0 o 1")
    if value["timezone"] is not None:
        if not isinstance(value["timezone"], str):
            raise ValueError("Zona IANA inválida")
        try:
            ZoneInfo(value["timezone"])
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Zona IANA desconocida") from exc
    if value["offset"] is not None:
        if not isinstance(value["offset"], str):
            raise ValueError("Offset inválido")
        fixed_offset(value["offset"])
    if value["source_tag"] is not None and (not isinstance(value["source_tag"], str) or not value["source_tag"]):
        raise ValueError("source_tag inválido")
    if value["date"] is not None:
        from .capture_dates import parse_date
        if not isinstance(value["date"], str) or parse_date(value["date"], "user:date").issue:
            raise ValueError("Fecha explícita inválida")
    for key in ("allow_create_date_fallback", "remove_historical", "discard_description", "set_file_modify_date", "set_file_create_date"):
        if type(value[key]) is not bool:
            raise ValueError(f"{key} requiere true/false")
    return dict(raw) if partial else value


def parse_date_settings(raw):
    if not isinstance(raw, dict):
        raise ValueError("dates requiere una tabla")
    raw = dict(raw)
    files = raw.pop("files", {})
    result = validate_decision(raw)
    if not isinstance(files, dict):
        raise ValueError("dates.files requiere una tabla por ruta original relativa")
    result["files"] = {}
    for relative, decision in files.items():
        from pathlib import Path
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Ruta de decisión inválida")
        result["files"][relative] = validate_decision(decision, partial=True)
    return result


def effective_decision(settings, relative, decisions=None):
    raw = {key: value for key, value in settings.items() if key != "files"}
    raw.update(settings.get("files", {}).get(relative, {}))
    supplied = dict(decisions or {})
    supplied.pop("output", None)
    if "authority" in supplied:
        supplied["policy"] = supplied.pop("authority")
        supplied["policy"] = {"metadata": "metadata-to-filename", "filename": "filename-to-metadata"}.get(supplied["policy"], supplied["policy"])
    for key in ("remove_historical", "discard_description", "set_file_modify_date", "set_file_create_date", "allow_create_date_fallback"):
        if isinstance(supplied.get(key), str) and supplied[key] in ("true", "false"):
            supplied[key] = supplied[key] == "true"
    if "fold" in supplied and isinstance(supplied["fold"], str) and supplied["fold"] in ("0", "1"):
        supplied["fold"] = int(supplied["fold"])
    raw.update(supplied)
    return validate_decision(raw)
