"""HandBrake/FFmpeg reales sobre candidatos; la publicación pertenece al núcleo."""

from dataclasses import replace
from pathlib import Path
import hashlib
import json
import math

from .capture_dates import CaptureDate, compare_dates, parse_date
from .exiftool import ExifTool
from .inventory import probe_media
from .process import run_tool
from .state import atomic_json
from .video_plan import VideoPolicyError, preset, ratio, video_info


class VideoValidationError(ValueError):
    pass


class VideoDriver:
    def __init__(self, config, *, runner=None):
        self.config, self.runner = config, runner or run_tool
        def executable(name):
            return config.tools[name].executable if name in config.tools else name
        self.handbrake, self.ffmpeg, self.ffprobe = map(executable, ("HandBrakeCLI", "ffmpeg", "ffprobe"))
        self.dates = ExifTool(executable("exiftool"), timeout=config.timeout_seconds, ffprobe=self.ffprobe, ffmpeg=self.ffmpeg, runner=self.runner)
        self.versions = None

    def call(self, args):
        return self.runner(args, timeout=self.config.timeout_seconds).check()

    def capabilities(self, plan):
        if self.versions is None:
            self.versions = {"ExifTool": self.dates.version(),
                             "ffmpeg": self.call([self.ffmpeg, "-version"]).stdout.splitlines()[0],
                             "ffprobe": self.call([self.ffprobe, "-version"]).stdout.splitlines()[0]}
            if plan["action"] == "encode":
                self.versions["HandBrakeCLI"] = self.call([self.handbrake, "--version"]).stdout.strip()
        if plan["action"] == "encode":
            help_text = self.call([self.handbrake, "--help"]).stdout
            required = ["--preset-import-file", "--crop-mode", "--non-anamorphic", "--keep-metadata", "--align-av"]
            if plan["settings"]["audio_encoder"] != "ffmpeg_aac":
                required.append(plan["settings"]["audio_encoder"])
            if any(flag not in help_text for flag in required):
                raise VideoPolicyError("Capacidades HandBrake insuficientes para el perfil congelado")
        return self.versions

    def inspect(self, path):
        return probe_media(path, self.config, runner=self.runner)

    def frame_times(self, path):
        data = json.loads(self.call([self.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames",
                                    "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)]).stdout)
        try:
            times = [float(frame["best_effort_timestamp_time"]) for frame in data["frames"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise VideoValidationError("No se acreditan timestamps de todos los frames") from exc
        if not times or any(not math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
            raise VideoValidationError("Timestamps de frames ausentes o no crecientes")
        return [time - times[0] for time in times]

    def packets(self, path):
        data = json.loads(self.call([self.ffprobe, "-v", "error", "-show_packets", "-show_data_hash", "sha256",
                                    "-show_entries", "packet=stream_index,data_hash", "-of", "json", str(path)]).stdout)
        packets = [(p["stream_index"], p["data_hash"]) for p in data.get("packets", [])]
        if not packets:
            raise VideoValidationError("Remux sin paquetes verificables")
        return hashlib.sha256(json.dumps(packets).encode()).hexdigest()

    def restore_dates(self, path, selected, decision, source_tags):
        before = self.dates.read(path)
        content = self.dates.content(path, before)
        date = CaptureDate(**selected)
        old = parse_date(source_tags.get("Keys:CreationDate"), "Keys:CreationDate")
        if not date.fraction and old.fraction and compare_dates(date, old) == "matches":
            date = replace(date, value=date.value + "." + old.fraction, precision="fraction")
        targets, attributes = self.dates.targets(before, date, decision, path)
        self.dates.write(path, before, targets, attributes)
        return self.dates.verify(path, before, targets, content, attributes)

    def produce(self, source, path, plan, preset_path):
        separate_audio = plan["action"] == "encode" and plan["info"]["audio"] and plan["settings"]["audio_encoder"] == "ffmpeg_aac"
        encoded = Path(str(path) + ".video.mp4") if separate_audio else path
        if plan["action"] == "remux":
            args = [self.ffmpeg, "-v", "error", "-n", "-i", str(source), "-map", "0", "-c", "copy",
                    "-map_metadata", "0", "-f", "mp4", str(path)]
        else:
            g, options = plan["geometry"], plan["settings"]
            args = [self.handbrake, "-i", str(source), "-o", str(encoded), "--preset-import-file", str(preset_path),
                    "--preset", options["profile"], "--format", "av_mp4", "--encoder", "x264",
                    "--encoder-preset", options["encoder_preset"], "--quality", str(options["quality"]),
                    "--width", str(g["width"]), "--height", str(g["height"]),
                    "--maxWidth", str(g["width"]), "--maxHeight", str(g["height"]),
                    "--non-anamorphic", "--crop-mode", "none", "--crop", "0:0:0:0", "--modulus", "2",
                    "--rate", "30", "--" + options["frame_rate_mode"], "--keep-metadata", "--align-av",
                    "--no-comb-detect", "--no-decomb", "--no-detelecine", "--subtitle", "none", "--no-markers"]
            args += (["--audio", "1", "--aencoder", options["audio_encoder"], "--ab", "160", "--mixdown", "stereo"]
                     if plan["info"]["audio"] and not separate_audio else ["--audio", "none"])
        commands = [args]
        if separate_audio:
            commands.append([self.ffmpeg, "-v", "error", "-n", "-i", str(encoded), "-i", str(source),
                             "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "0", "-c:v", "copy",
                             "-c:a", "aac", "-ac", "2", "-b:a", "160k", "-af", "aresample=async=1:first_pts=0",
                             "-f", "mp4", str(path)])
        return commands

    def write_preset(self, path, plan):
        data = preset(plan["settings"])
        if path.exists():
            if path.is_symlink() or json.loads(path.read_text()) != data:
                raise VideoPolicyError("Preset propio cambiado: no sobrescribir")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(path, data)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def validate(self, source, path, plan, date_evidence):
        output = self.inspect(path)
        actual, original, target = video_info(output), plan["info"], plan["geometry"]
        if not actual["mp4"] or actual["video_codec"] != "h264":
            raise VideoValidationError("Salida no es MP4/H.264 real")
        if actual["sar"] != "1" or actual["rotation"] != 0:
            raise VideoValidationError("SAR/rotación de salida no resueltos")
        if (actual["width"], actual["height"]) != (target["width"], target["height"]):
            raise VideoValidationError("Geometría distinta del plan; no publicar")
        dar = original["visible_width"] / original["visible_height"]
        if abs(actual["width"] / actual["height"] / dar - 1) > .005 or actual["width"] > original["visible_width"] or actual["height"] > original["visible_height"]:
            raise VideoValidationError("Deformación, recorte o ampliación detectados")
        fps = float(ratio(actual["fps"]))
        tolerance = max(.1, 2 / fps)
        if abs(actual["duration"] - original["duration"]) > tolerance:
            raise VideoValidationError("Duración fuera de tolerancia")
        if len(actual["audio"]) != len(original["audio"]) or any(a["codec"] != "aac" for a in actual["audio"]):
            raise VideoValidationError("Política de pistas/audio incumplida")
        if plan["action"] == "encode" and any(a["channels"] != 2 for a in actual["audio"]):
            raise VideoValidationError("Audio distinto del estéreo solicitado")
        for before, after in zip(original["audio"], actual["audio"]):
            if before["duration"] and after["duration"] and abs(float(before["duration"]) - float(after["duration"])) > tolerance:
                raise VideoValidationError("Duración de audio alterada")
        self.call([self.ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-map", "0:v", "-map", "0:a?", "-f", "null", "-"])
        times = self.frame_times(path)
        deltas = [b - a for a, b in zip(times, times[1:])]
        mode = plan["settings"]["frame_rate_mode"]
        if fps > 30.01 or any(delta < 1 / 30 - .00005 for delta in deltas):
            raise VideoValidationError("La salida supera 30 FPS")
        if mode == "cfr" and (abs(fps - 30) > .01 or any(abs(delta - 1 / 30) > .00005 for delta in deltas)):
            raise VideoValidationError("No es CFR 30 verificado")
        if mode == "pfr" and ratio(original["peak_fps"]) <= 30:
            before_times = self.frame_times(source)
            if len(before_times) != len(times) or any(abs(a - b) > .0005 for a, b in zip(before_times, times)):
                raise VideoValidationError("PFR no ha conservado el timing original bajo 30 FPS")
        if mode == "pfr" and ratio(original["peak_fps"]) == ratio(original["fps"]) and abs(fps - min(30, float(ratio(original["fps"])))) > .01:
            raise VideoValidationError("PFR alteró la tasa constante fuera del límite solicitado")
        if plan["action"] == "remux" and self.packets(source) != self.packets(path):
            raise VideoValidationError("El remux alteró los paquetes codificados")
        # La fecha ya se ha releído con ExifTool después de escribir y decodificado.
        if not date_evidence.get("targets"):
            raise VideoValidationError("No hay evidencia de fecha restaurada")
        size = Path(path).stat().st_size
        saved = plan["source_bytes"] - size
        beneficial = (0 < size < plan["source_bytes"] and saved >= plan["settings"]["min_savings_bytes"]
                      and saved / plan["source_bytes"] >= plan["settings"]["min_savings_ratio"])
        return {"video": {"plan": plan, "profile_hash": plan["profile_hash"], "output": actual, "output_bytes": size,
                          "saved_bytes": saved, "beneficial": beneficial, "decode": "complete", "frames": len(times),
                          "timing_sha256": hashlib.sha256(json.dumps(times).encode()).hexdigest(), "dates": date_evidence},
                "file_attributes": date_evidence.get("file_attributes", {})}
