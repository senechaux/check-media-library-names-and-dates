"""Plan puro basado en ffprobe: geometría visual, selección y una sola transformación."""

from fractions import Fraction
from importlib.resources import files
from pathlib import Path
import hashlib
import json
import math

from .video_settings import parse_video_settings


class VideoPolicyError(ValueError):
    pass


def ratio(value, default=None):
    try:
        number = Fraction(str(value).replace(":", "/"))
        if number > 0:
            return number
    except (ValueError, ZeroDivisionError):
        pass
    if default is not None:
        return Fraction(default)
    raise VideoPolicyError(f"Proporción/tasa inválida: {value}")


def video_info(data):
    streams = data["streams"]
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise VideoPolicyError("multiple_video_tracks: elegir política antes de convertir")
    if len(audio) > 1 or any(s.get("channels", 0) > 2 for s in audio):
        raise VideoPolicyError("multiple_audio_tracks_or_surround: política pendiente")
    if any(s.get("codec_type") not in ("video", "audio") for s in streams):
        raise VideoPolicyError("subtitle_or_extra_tracks: política pendiente")
    stream = videos[0]
    if stream.get("color_transfer") in ("smpte2084", "arib-std-b67") or any("dovi" in str(s).lower() or "mastering display" in str(s).lower() for s in stream.get("side_data_list", [])):
        raise VideoPolicyError("hdr: conversión/conservación pendiente de política")
    if stream.get("field_order", "unknown") not in ("progressive", "unknown"):
        raise VideoPolicyError("interlaced: filtros pendientes de aprobación")
    if stream.get("pix_fmt", "yuv420p") not in ("yuv420p", "yuvj420p", "yuv422p", "yuv444p", "yuvj422p", "yuvj444p", "nv12", "rgb24", "bgr24"):
        raise VideoPolicyError("pixel_format: conversión de profundidad/color pendiente")
    rotation = float(stream.get("tags", {}).get("rotate", 0))
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = float(side["rotation"])
        matrix = side.get("displaymatrix", "")
        if matrix:
            rows = [line.split(":", 1)[1].split() for line in matrix.strip().splitlines() if ":" in line]
            if len(rows) >= 2 and int(rows[0][0]) * int(rows[1][1]) - int(rows[0][1]) * int(rows[1][0]) < 0:
                raise VideoPolicyError("mirrored_matrix: política pendiente")
    if rotation % 90:
        raise VideoPolicyError("rotation: solo se acreditan múltiplos de 90 grados")
    rotation = int(rotation) % 360
    width, height = int(stream["width"]), int(stream["height"])
    sar = ratio(stream.get("sample_aspect_ratio", "1:1"))
    visible = (Fraction(width) * sar, Fraction(height))
    if rotation % 180:
        visible = visible[::-1]
    duration = float(data["format"].get("duration", stream.get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0 or min(visible) < 2:
        raise VideoPolicyError("Duración/geometría no acreditada")
    # ffprobe agrupa MOV/MP4: major_brand decide el contenedor real, nunca el sufijo.
    brand = data["format"].get("tags", {}).get("major_brand", "").strip()
    mp4 = brand in ("isom", "iso2", "iso3", "iso4", "iso5", "iso6", "mp41", "mp42", "avc1", "M4V", "M4VH", "MSNV", "dash")
    return {"width": width, "height": height, "visible_width": float(visible[0]), "visible_height": float(visible[1]),
            "sar": str(sar), "rotation": rotation, "duration": duration, "fps": str(ratio(stream.get("avg_frame_rate"))),
            "peak_fps": str(ratio(stream.get("r_frame_rate"))), "video_codec": stream["codec_name"],
            "audio": [{"codec": a["codec_name"], "channels": a.get("channels"), "duration": a.get("duration")} for a in audio],
            "mp4": mp4, "container": data["format"]["format_name"], "major_brand": brand,
            "bit_rate": data["format"].get("bit_rate"), "field_order": stream.get("field_order", "unknown")}


def geometry(info, profile="archive-720p30"):
    width, height = Fraction(str(info["visible_width"])), Fraction(str(info["visible_height"]))
    if profile == "height-720":
        bounds = (width, Fraction(720))
    else:
        bounds = (1280, 720) if width > height else (720, 1280) if height > width else (720, 720)
    scale = min(Fraction(1), Fraction(bounds[0]) / width, Fraction(bounds[1]) / height)
    max_width, max_height = int(width * scale) // 2 * 2, int(height * scale) // 2 * 2
    # Buscar redondeo par que conserve DAR <=0,5%; nunca ampliar para redondear.
    candidates = [(w, h) for w in range(max(2, max_width - 16), max_width + 1, 2)
                  for h in range(max(2, max_height - 16), max_height + 1, 2)
                  if abs(Fraction(w, h) / (width / height) - 1) <= Fraction(5, 1000)]
    if not candidates:
        raise VideoPolicyError("No hay geometría par sin deformación/ampliación; revisión manual")
    w, h = max(candidates, key=lambda pair: pair[0] * pair[1])
    return {"width": w, "height": h, "sar": "1:1", "rotation": 0}


def preset(settings):
    data = json.loads(files("media_library").joinpath("presets/archive-720p30.json").read_text())
    value = data["PresetList"][0]
    value.update(PresetName=settings["profile"], VideoFramerateMode=settings["frame_rate_mode"],
                 VideoQualitySlider=settings["quality"], VideoPreset=settings["encoder_preset"], AudioEncoderFallback=settings["audio_encoder"])
    value["AudioList"][0]["AudioEncoder"] = settings["audio_encoder"]
    return data


def profile_hash(settings):
    technical = {k: settings[k] for k in ("profile", "frame_rate_mode", "quality", "encoder_preset", "audio_encoder")}
    return hashlib.sha256(json.dumps({"options": technical, "preset": preset(settings)}, sort_keys=True).encode()).hexdigest()


def plan_video(path, size, data, raw_settings, *, normalize=True, compression=True, already_validated=False):
    settings = parse_video_settings(raw_settings)
    info = video_info(data)
    target = geometry(info, settings["profile"])
    selected = compression and size >= settings["min_bytes"]
    needs_normalize = normalize and (not info["mp4"] or Path(path).suffix.lower() != ".mp4")
    historical = any(marker in Path(path).stem for marker in (" reduced_size", " reduced_video"))
    result = {"source": str(path), "source_bytes": size, "info": info, "geometry": target,
              "settings": settings, "profile_hash": profile_hash(settings), "selected_by_size": selected,
              "reason": f"bytes={size}; umbral={settings['min_bytes']}; contenedor={info['container']}; marca={info['major_brand']}",
              "action": "none", "stage": None, "destination": None}
    if already_validated:
        return {**result, "reason": "Salida acreditada con el mismo perfil; no recodificar"}
    if historical and settings["historical_policy"] != "process":
        if settings["historical_policy"] == "review":
            raise VideoPolicyError("historical_marker: falta manifiesto o política explícita keep/process")
        return {**result, "reason": "Marcador histórico conservado por política keep"}
    if not selected and not needs_normalize:
        return result
    compatible = (info["video_codec"] == "h264" and info["sar"] == "1" and info["rotation"] == 0
                  and (info["width"], info["height"]) == (target["width"], target["height"])
                  and ratio(info["peak_fps"]) <= 30 and all(a["codec"] == "aac" for a in info["audio"])
                  and (settings["frame_rate_mode"] == "pfr" or ratio(info["fps"]) == ratio(info["peak_fps"]) == 30))
    action = "encode" if selected or not compatible else "remux"
    suffix = " reduced_size.mp4" if action == "encode" else ".mp4"
    stem = Path(path).stem
    destination = str(Path(path).with_name(stem + suffix))
    return {**result, "action": action, "stage": "normalize" if needs_normalize else "compression", "destination": destination,
            "combined": bool(needs_normalize and selected), "require_savings": action == "encode"}
