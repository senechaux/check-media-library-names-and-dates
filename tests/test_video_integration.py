"""Compatibilidad real: HandBrake, ffprobe, FFmpeg y ExifTool sobre temporales."""

from pathlib import Path
import json

import pytest

from media_library.filesystem import fingerprint
from media_library.video_driver import VideoDriver
from media_library.video_plan import plan_video
from video_support import configure_video, make_video, manifest, run_real, video_tools, exiftool

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("width,height,sar,rotation,fps,mode,audio,expected", [
    (1920, 1080, "1/1", 0, "24", "pfr", True, (1280, 720)),
    (1080, 1920, "1/1", 0, "24", "pfr", False, (720, 1280)),
    (320, 180, "1/1", 90, "24", "pfr", False, (180, 320)),
    (320, 240, "4/3", 0, "24", "pfr", False, (426, 240)),
    (320, 180, "1/1", 0, "60", "pfr", False, (320, 180)),
    (320, 180, "1/1", 0, "24", "cfr", False, (320, 180)),
])
def test_real_profile_geometry_timing_dates_and_original(config_file, video_tools, width, height, sar, rotation, fps, mode, audio, expected):
    config = configure_video(config_file, video_tools, frame_rate_mode=mode)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source, width=width, height=height, sar=sar, rotation=rotation, fps=fps, audio=audio)
    original = fingerprint(source)["sha256"]
    code, report = run_real(config_file, "--apply")
    assert code == 0, report
    data = manifest(config_file, report)
    ops = list(data["operations"].values())
    assert len(ops) == 1 and ops[0]["kind"] == "substitute"
    op = ops[0]
    video = op["evidence"]["validation"]["video"]
    assert (video["output"]["width"], video["output"]["height"]) == expected
    assert video["output"]["sar"] == "1" and video["output"]["rotation"] == 0
    assert video["beneficial"] and not source.exists()
    assert fingerprint(op["backup"])["sha256"] == original
    assert video_tools.read(op["destination"])["QuickTime:CreateDate"] == "2026:01:02 03:04:05"
    assert not Path(op["candidate"]).exists()  # Limpieza solo después de completar la publicación.
    assert sum(e["kind"] == "video_encode_intent" for e in data["events"]) == 1
    assert sum(e["kind"] == "video_cleanup_completed" for e in data["events"]) == 1
    assert video["versions"]["HandBrakeCLI"] and video["preset_sha256"]
    if rotation:
        # Comparación técnica de orientación con la matriz aplicada por FFmpeg;
        # no sustituye revisión humana de calidad.
        from media_library.process import run_tool
        backup = Path(op["backup"])
        reference = config_file.parent / "reference.rgb"
        actual = config_file.parent / "actual.rgb"
        wrong = config_file.parent / "wrong.rgb"
        for path, filters, target in ((backup, "scale=32:32", reference), (Path(op["destination"]), "scale=32:32", actual),
                                      (Path(op["destination"]), "hflip,vflip,scale=32:32", wrong)):
            run_tool(["ffmpeg", "-v", "error", "-n", "-i", str(path), "-vf", filters, "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", str(target)]).check()
        def distance(path): return sum((a-b)**2 for a, b in zip(reference.read_bytes(), path.read_bytes()))
        assert distance(actual) < distance(wrong) / 2
    code, resumed = run_real(config_file, "--resume", report["run_id"])
    assert code == 0
    assert len(manifest(config_file, resumed)["operations"]) == 1
    code, fresh = run_real(config_file, "--apply")
    assert code == 0 and not manifest(config_file, fresh)["operations"]
    assert fresh["files"][0]["stages"]["normalize"]["evidence"]["video_plan"]["prior_validation"]


def test_real_small_mov_remux_uses_real_container_and_requires_growth_authorization(config_file, video_tools):
    config = configure_video(config_file, video_tools, min_bytes=50_000_000)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source, codec="libx264")
    code, report = run_real(config_file, "--apply")
    # El plan distingue el remux de la compresión y puede pedir autorización si crece.
    if code == 2:
        from pipeline_support import ScriptConsole
        code, report = run_real(config_file, "--resume", report["run_id"], console=ScriptConsole(["decidir allow_remux_growth=true", "comprobar"]))
    assert code == 0, report
    op = next(iter(manifest(config_file, report)["operations"].values()))
    assert op["evidence"]["validation"]["video"]["plan"]["action"] == "remux"
    assert Path(op["destination"]).suffix == ".mp4"
    assert not any(e["kind"] == "video_encode_intent" and e["evidence"]["command"][0].endswith("HandBrakeCLI") for e in manifest(config_file, report)["events"])


def test_real_bigger_result_retains_source_and_does_not_retry(config_file, video_tools):
    config = configure_video(config_file, video_tools, min_savings_bytes=10_000_000)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source)
    original = source.read_bytes()
    code, report = run_real(config_file, "--apply")
    assert code == 0 and source.read_bytes() == original
    record = report["files"][0]["stages"]["normalize"]["evidence"]
    assert record["reason"] == "not_beneficial" and Path(record["retained_candidate"]["path"]).exists()
    assert not manifest(config_file, report)["operations"]
    code, resumed = run_real(config_file, "--resume", report["run_id"])
    assert code == 0
    assert sum(e["kind"] == "video_encode_intent" for e in manifest(config_file, resumed)["events"]) == 1


def test_real_mp4_compression_reuses_metadata_contract_and_backups(config_file, video_tools):
    config = configure_video(config_file, video_tools)
    config_file.write_text(config_file.read_text().replace('metadata="disabled"', 'metadata="auto"'))
    source = config.source / "2026-01-02 04.04.05.mp4"
    make_video(source, codec="mpeg4", width=640, height=360, duration="1")
    original = fingerprint(source)["sha256"]
    code, report = run_real(config_file, "--apply")
    assert code == 0, report
    data = manifest(config_file, report)
    entry = data["entries"][0]
    operations = [data["operations"][key] for key in entry["operations"]]
    assert [op["kind"] for op in operations] == ["replace", "substitute"]
    assert fingerprint(operations[0]["backup"])["sha256"] == original
    assert entry["temporal_decision"]["selected"]["offset"] == "+01:00"
    assert operations[1]["evidence"]["validation"]["video"]["plan"]["stage"] == "compression"
    assert not source.exists()
    code, resumed = run_real(config_file, "--resume", report["run_id"])
    assert code == 0 and len(manifest(config_file, resumed)["operations"]) == 2
