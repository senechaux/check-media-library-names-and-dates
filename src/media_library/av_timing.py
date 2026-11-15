"""Presentación decodificada: edit lists y skip/discard del decoder ya aplicados."""

import math


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("A/V: timestamp o duración no finitos")
    return result


def presentation(data):
    streams = {stream["index"]: stream for stream in data["streams"]}
    tracks = {}
    for kind in ("video", "audio"):
        frames = [frame for frame in data["frames"] if frame["media_type"] == kind]
        if not frames:
            if kind == "video" or any(s.get("codec_type")==kind for s in streams.values()):
                raise ValueError("A/V: faltan frames de presentación de " + kind)
            continue
        stream = streams[frames[0]["stream_index"]]
        rate = number(stream["sample_rate"]) if kind == "audio" else None
        if rate is not None and rate <= 0:
            raise ValueError("A/V: sample rate inválido")
        intervals = []
        for frame in frames:
            start = number(frame["best_effort_timestamp_time"])
            raw = frame.get("duration_time", frame.get("pkt_duration_time"))
            duration = number(raw) if raw is not None else None
            if kind == "audio":
                samples = number(frame["nb_samples"]) / rate
                duration = min(duration, samples) if duration is not None else samples
            if duration is None or duration <= 0:
                raise ValueError("A/V: duración de frame no acreditada")
            if intervals and start <= intervals[-1][0]:
                raise ValueError("A/V: timestamps no crecientes")
            intervals.append((start, start + duration))
        segments = []
        for start, end in intervals:
            if segments and start <= segments[-1][1] + (2 / rate if rate else .000002):
                segments[-1] = (segments[-1][0], max(segments[-1][1], end))
            else:
                segments.append((start, end))
        tracks[kind] = {"start": intervals[0][0], "end": max(end for _, end in intervals),
                        "segments": segments, "sample_rate": rate,
                        "times": [start - intervals[0][0] for start, _ in intervals] if kind == "video" else []}
    tracks["span"] = max(track["end"] for track in tracks.values()) - min(track["start"] for track in tracks.values())
    return tracks


def uncovered(intervals, covered, tolerance):
    """Porciones presentadas de un lado sin cobertura equivalente en el otro."""
    for start, end in intervals:
        cursor = start
        for left, right in covered:
            left -= tolerance; right += tolerance
            if right <= cursor:
                continue
            if left >= end:
                break
            if left > cursor:
                yield cursor, min(left, end)
            cursor = max(cursor, right)
            if cursor >= end:
                break
        if cursor < end:
            yield cursor, end


def validate_video_coverage(source, output, tolerance):
    """Acreditar imagen sin usar el audio como sustituto de frames ausentes."""
    tracks = {}
    for side, timeline in (("source", source), ("output", output)):
        video = timeline["video"]
        origin = video["start"]
        tracks[side] = {"duration_seconds": video["end"] - origin,
                        "segments_relative": [[s-origin, e-origin] for s, e in video["segments"]]}
    # ffprobe serializa PTS/duraciones con precisión de microsegundos.
    epsilon = .000002
    if abs(tracks["source"]["duration_seconds"] - tracks["output"]["duration_seconds"]) > tolerance + epsilon:
        raise ValueError("Vídeo: duración de presentación fuera de tolerancia")
    for side, other in (("source", "output"), ("output", "source")):
        if next(uncovered(tracks[side]["segments_relative"], tracks[other]["segments_relative"],
                          tolerance + epsilon), None) is not None:
            raise ValueError("Vídeo: cobertura de presentación no conservada")
    return {"verified": True, "method": "decoded-video-coverage:v1", "tolerance_seconds": tolerance,
            "timestamp_epsilon_seconds": epsilon, **tracks}


def validate_alignment(source, output, silence):
    if ("audio" in source) != ("audio" in output):
        raise ValueError("A/V: pistas de audio distintas")
    if "audio" not in source:
        return {"verified": True, "audio": False, "method": "decoded-presentation:v1"}
    # Admitir priming/redondeo de hasta dos bloques AAC; no usar la duración
    # de un frame de vídeo lento como permiso para desplazar audio perceptible.
    tolerance = max(.05, 2048 / min(source["audio"]["sample_rate"], output["audio"]["sample_rate"]))
    timelines = {}
    for side, timeline in (("source", source), ("output", output)):
        origin = timeline["video"]["start"]
        timelines[side] = [(start - origin, end - origin) for start, end in timeline["audio"]["segments"]]
    checks = []
    for side, other in (("source", "output"), ("output", "source")):
        timeline = source if side == "source" else output
        origin = timeline["video"]["start"]
        for start, end in uncovered(timelines[side], timelines[other], tolerance):
            evidence = silence(side, start + origin, end + origin)
            if not evidence["silent"]:
                raise ValueError("A/V: audio desplazado o hueco de presentación no conservado")
            checks.append({"side": side, "relative_start": start, "relative_end": end, **evidence})
    return {"verified": True, "method": "decoded-presentation:v1", "tolerance_seconds": tolerance,
            "source_audio_relative": [[s,e] for s,e in timelines["source"]],
            "output_audio_relative": [[s,e] for s,e in timelines["output"]], "silence_checks": checks}
