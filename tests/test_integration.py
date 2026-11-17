"""Integraciones del núcleo; no fijan perfiles de los cambios de vídeo/EXIF."""

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from media_library.config import Tool, preflight
from media_library.inventory import inventory, probe_media
from media_library.legacy import video_tags
from media_library.operations import SafeExecutor
from media_library.process import run_tool
from media_library.state import RunStore, SourceLock

pytestmark = pytest.mark.integration


def tool(name):
    executable = shutil.which(name)
    if not executable:
        pytest.skip(f"Falta la herramienta real {name}; integración no ejecutada")
    return executable


def synthetic_video(path):
    ffmpeg = tool("ffmpeg")
    tool("ffprobe")
    run_tool([ffmpeg, "-v", "error", "-n", "-f", "lavfi", "-i", "color=c=blue:s=32x32:r=24:d=0.25",
              "-c:v", "mpeg4", "-metadata", "creation_time=2026-01-02T03:04:05Z", "-f", "mp4", str(path)]).check()


def test_real_preflight_inventory_and_legacy_tags(config):
    path = config.source / '''irregular ' " $(literal).JPG'''
    synthetic_video(path)
    config = replace(config, tools={"ffprobe": Tool(tool("ffprobe"), required_capabilities=("-show_format", "-show_streams", "-print_format"))})
    assert "ffprobe version" in preflight(config)["ffprobe"]
    entries, result = inventory(config)
    assert result.state == "COMPLETED"
    assert len(entries) == 1 and entries[0].classification == "video"
    assert entries[0].media["streams"][0]["codec_name"] == "mpeg4"
    assert video_tags(path)["creation_time"].startswith("2026-01-02T03:04:05")
    assert not config.workspace.exists()


def test_real_handbrake_candidate_and_safe_publication(config, tmp_path):
    handbrake = tool("HandBrakeCLI")
    source = config.source / "sample.MOV"
    synthetic_video(source)
    entries, result = inventory(config)
    assert result.state == "COMPLETED"
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        executor = SafeExecutor(RunStore.create(config, lock, entries))

        def encode(path):
            return run_tool([handbrake, "-i", str(source), "-o", str(path), "--format", "av_mp4",
                             "--encoder", "x264", "--quality", "30", "--width", "32", "--height", "32",
                             "--crop", "0:0:0:0", "--rate", "24", "--pfr"], timeout=60)

        def validate(path):
            data = probe_media(path, config)
            video = next(stream for stream in data["streams"] if stream["codec_type"] == "video")
            assert video["codec_name"] == "h264" and int(video["width"]) > 0
            assert float(data["format"]["duration"]) > 0
            return {"codec": video["codec_name"], "duration": data["format"]["duration"]}

        artifact = executor.prepare(entries[0].file_id, encode, validate)
        operation = executor.plan(entries[0].file_id, "export", artifact=artifact)
        original = source.read_bytes()
        assert executor.execute(operation.operation_id).state == "COMPLETED"
        assert source.read_bytes() == original
        assert operation.backup is None
        assert validate(Path(operation.destination))["codec"] == "h264"
