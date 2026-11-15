"""Configuración congelada del perfil de vídeo, sin políticas implícitas de pérdida."""

import math

DEFAULTS = {"min_bytes": 50_000_000, "profile": "archive-720p30", "frame_rate_mode": "pfr",
            "quality": 22, "encoder_preset": "fast", "audio_encoder": "ca_aac",
            "min_savings_bytes": 1, "min_savings_ratio": 0.0, "allow_remux_growth": False,
            "historical_policy": "review", "quality_reviewed": False}


def parse_video_settings(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError("Opciones de video desconocidas")
    result = {**DEFAULTS, **raw}
    for key in ("min_bytes", "min_savings_bytes"):
        if type(result[key]) is not int or result[key] < (1 if key == "min_savings_bytes" else 0):
            raise ValueError(f"video.{key} requiere entero positivo o umbral cero")
    for key, low, high in (("quality", 0, 51), ("min_savings_ratio", 0, 1)):
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not low <= result[key] <= high:
            raise ValueError(f"video.{key} fuera de rango")
    for key, allowed in (("profile", ("archive-720p30", "height-720")), ("frame_rate_mode", ("pfr", "cfr")),
                         ("encoder_preset", ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow")),
                         ("audio_encoder", ("ca_aac", "av_aac")), ("historical_policy", ("review", "keep", "process"))):
        if result[key] not in allowed:
            raise ValueError(f"video.{key} inválido")
    for key in ("allow_remux_growth", "quality_reviewed"):
        if type(result[key]) is not bool:
            raise ValueError(f"video.{key} requiere true/false")
    return result
