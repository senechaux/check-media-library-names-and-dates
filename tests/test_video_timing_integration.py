"""Línea temporal efectiva con FFmpeg/ffprobe/ExifTool reales y medios sintéticos."""

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from media_library.capture_dates import parse_date
from media_library.config import Tool
from media_library.date_settings import parse_date_settings
from media_library.process import run_tool
from media_library.video_driver import VideoDriver
from media_library.video_plan import plan_video
from video_support import configure_video, run_real, manifest, video_tools, exiftool

pytestmark = pytest.mark.integration


def av_command(path, *, video_start=0, audio_start=0, codec="rawvideo", fps=24,
               video_duration=2, audio_duration=1):
    return ["ffmpeg", "-v", "error", "-n", "-itsoffset", str(video_start), "-f", "lavfi", "-i",
            f"testsrc2=s=160x90:r={fps}:d={video_duration}", "-itsoffset", str(audio_start), "-f", "lavfi", "-i",
            f"sine=frequency=440:duration={audio_duration}", "-c:v", codec,
            *(["-pix_fmt", "rgb24"] if codec == "rawvideo" else ["-preset", "ultrafast", "-crf", "18"]),
            "-c:a", "aac", "-ac", "2", "-f", "mov" if codec == "rawvideo" else "mp4", str(path)]


@pytest.mark.parametrize("manual", [False, True])
def test_pipeline_rejects_shifted_audio_before_installation(config_file, video_tools, monkeypatch, manual):
    config = configure_video(config_file, video_tools, manual=manual)
    source = config.source / "2026-01-02 04.04.05.MOV"
    run_tool(av_command(source)).check(); original = source.read_bytes()
    if manual:
        code, report = run_real(config_file, "--apply")
        assert code == 2 and source.read_bytes() == original
        output = Path(next(iter(report["files"][0]["stages"]["normalize"]["pause"]["outputs"].values())))
        run_tool(av_command(output, audio_start=.6, codec="libx264")).check()
        code, report = run_real(config_file, "--resume", report["run_id"])
    else:
        # Productor defectuoso con herramientas reales: el validador debe impedir
        # publicar aunque geometría, duración, fechas y decodificación sean válidas.
        monkeypatch.setattr(VideoDriver, "produce", lambda self, src, out, plan, preset:
                            [av_command(out, audio_start=.6, codec="libx264")])
        code, report = run_real(config_file, "--apply")
    assert code == 3 and source.read_bytes() == original, report
    assert "A/V" in str(report["failures"])
    assert not manifest(config_file, report)["operations"]


@pytest.mark.parametrize("mode", ["pfr", "cfr"])
@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("video_duration", [1, 59/30], ids=["truncated", "one-frame-short"])
def test_video_coverage_is_independent_of_complete_audio(config_file, video_tools, monkeypatch,
                                                        mode, manual, video_duration):
    config=configure_video(config_file,video_tools,manual=manual,frame_rate_mode=mode)
    source=config.source/"2026-01-02 04.04.05.MOV"
    run_tool(av_command(source,fps=60,audio_duration=2)).check();original=source.read_bytes()
    def candidate(output):
        return av_command(output,fps=30,video_duration=video_duration,audio_duration=2,codec="libx264")
    if manual:
        code,report=run_real(config_file,"--apply");assert code==2
        output=Path(next(iter(report["files"][0]["stages"]["normalize"]["pause"]["outputs"].values())))
        run_tool(candidate(output)).check()
        code,report=run_real(config_file,"--resume",report["run_id"])
    else:
        monkeypatch.setattr(VideoDriver,"produce",lambda self,src,out,plan,preset:[candidate(out)])
        code,report=run_real(config_file,"--apply")
    operations=manifest(config_file,report)["operations"]
    destination=source.with_name(source.stem+" reduced_size.mp4")
    if video_duration==1:
        assert code==3 and source.exists(),report
        assert source.read_bytes()==original and not destination.exists()
        assert not any(op["state"]=="COMPLETED" for op in operations.values())
        assert "vídeo" in str(report["failures"]).lower()
        assert run_real(config_file,"--resume",report["run_id"])[0]==3
        assert source.read_bytes()==original and not destination.exists()
    else:
        assert code==0 and not source.exists(),report
        operation=next(iter(operations.values()))
        assert operation["state"]=="COMPLETED" and Path(operation["backup"]).read_bytes()==original
        track=VideoDriver(config).timeline(destination)
        assert abs(track["video"]["end"]-video_duration)<.002
        assert abs(track["audio"]["end"]-2)<.002


@pytest.mark.parametrize("v_start,a_start,out_v,out_a", [(0,0,0,0), (2,2,0,0), (0,.6,0,.6), (.5,0,.5,0)])
def test_effective_timeline_accepts_aac_padding_edits_and_common_shift(config, tmp_path, video_tools,
                                                                      v_start, a_start, out_v, out_a):
    source = config.source / "source.MOV"; output = tmp_path / "candidate.mp4"
    run_tool(av_command(source, video_start=v_start, audio_start=a_start)).check()
    run_tool(av_command(output, video_start=out_v, audio_start=out_a, codec="libx264")).check()
    driver = VideoDriver(replace(config, tools={"exiftool": Tool(video_tools.executable)}))
    plan = plan_video(source, source.stat().st_size, driver.inspect(source), {"min_bytes":0})
    dates = driver.restore_dates(output, asdict(parse_date("2026-01-02T03:04:05Z", "user:date")),
                                parse_date_settings({"quicktime_semantics":"utc"}), driver.dates.read(source))
    assert b"elst" in source.read_bytes() and b"elst" in output.read_bytes()
    before, after = driver.timeline(source), driver.timeline(output)
    assert abs((before["video"]["start"]-after["video"]["start"])-(v_start-out_v)) < .05
    evidence = driver.validate(source, output, plan, dates)
    assert evidence["video"]["decode"] == "complete"


def test_real_audio_route_preserves_delayed_audio_with_leading_silence(config_file, video_tools):
    config = configure_video(config_file, video_tools)
    source = config.source / "2026-01-02 04.04.05.MOV"
    run_tool(av_command(source, audio_start=.6)).check()
    code, report = run_real(config_file, "--apply")
    assert code == 0, report
    operation = next(iter(manifest(config_file, report)["operations"].values()))
    assert operation["state"] == "COMPLETED" and Path(operation["backup"]).exists()
    assert operation["evidence"]["validation"]["video"]["av_timing"]["verified"]
