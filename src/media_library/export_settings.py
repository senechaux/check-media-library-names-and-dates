"""Recetas locales explícitas, independientes del perfil de archivo."""

DEFAULTS = {"images": True, "videos": True, "image_max_side": 1200, "image_quality": 90,
            "color_policy": "preserve-icc", "video_profile": "upload-480p30", "video_quality": 22,
            "video_frame_rate_mode": "pfr", "video_quality_reviewed": False,
            "require_capture_date": True, "use_archived_original": True}


def parse_export_settings(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Opciones de export desconocidas")
    result = {**DEFAULTS, **raw}
    for key in ("images", "videos", "video_quality_reviewed", "require_capture_date", "use_archived_original"):
        if type(result[key]) is not bool:
            raise ValueError(f"export.{key} requiere true/false")
    for key, low, high in (("image_max_side", 1, 1200), ("image_quality", 1, 95), ("video_quality", 0, 51)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f"export.{key} fuera de rango")
    if result["color_policy"] != "preserve-icc":
        raise ValueError("Solo está acreditada preserve-icc sin conversión de color")
    if result["video_profile"] not in ("upload-480p30", "archive-720p30", "height-720") or result["video_frame_rate_mode"] not in ("pfr", "cfr"):
        raise ValueError("Perfil/timing de exportación no soportado")
    return result
