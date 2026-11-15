"""Fixtures exclusivamente sintéticos y herramientas locales reales."""

from pathlib import Path
import json
import shutil

import pytest

from media_library.config import load_config
from media_library.process import run_tool
from metadata_support import exiftool
from pipeline_support import configure, ScriptConsole


@pytest.fixture
def video_tools(exiftool):
    if not shutil.which("HandBrakeCLI"):
        pytest.skip("Falta HandBrakeCLI real; integración de vídeo no ejecutada")
    return exiftool


def make_video(path, *, width=320, height=180, fps="24", sar="1/1", audio=False, codec="rawvideo", rotation=0, duration="0.5", hdr=False, multiple_audio=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    output = path.with_name("unrotated.mov") if rotation else path
    args = ["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r={fps}:d={duration}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    if multiple_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=660:duration={duration}", "-map", "0:v", "-map", "1:a", "-map", "2:a"]
    if audio:
        args += ["-c:a", "aac", "-ac", "2"]
    args += ["-vf", f"setsar={sar}", "-c:v", codec]
    if codec == "rawvideo": args += ["-pix_fmt", "rgb24"]
    if codec == "mpeg4": args += ["-q:v", "1"]
    if codec == "libx264": args += ["-preset", "ultrafast", "-crf", "18"]
    if hdr: args += ["-x264-params", "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc"]
    run_tool([*args, "-metadata", "creation_time=2026-01-02T03:04:05Z", str(output)]).check()
    if rotation:
        run_tool(["ffmpeg", "-v", "error", "-n", "-display_rotation:v:0", str(rotation), "-i", str(output), "-c", "copy", str(path)]).check()
        output.unlink()


def configure_video(config_file, tool, *, manual=False, install=True, reviewed=True, include=None, **settings):
    configure(config_file, modes={"normalize": "manual" if manual else "auto", "compression": "auto",
                                  "installation": "auto" if install else "disabled"}, include=include)
    raw = config_file.read_text() + f'''
[dates]
policy="filename-to-metadata"
timezone="Europe/Madrid"
quicktime_semantics="utc"
[tools.exiftool]
executable={json.dumps(tool.executable)}
version_args=["-ver"]
[video]
'''
    values = {"min_bytes": 0, "quality_reviewed": reviewed, **settings}
    raw += "\n".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "\n"
    config_file.write_text(raw)
    return load_config(config_file)


def manifest(config_file, report):
    return json.loads((load_config(config_file).workspace / report["run_id"] / "manifest.json").read_text())


def run_real(config_file, *flags, console=None):
    from media_library.__main__ import main
    work = load_config(config_file).workspace
    before = set(work.iterdir()) if work.exists() else set()
    code = main(["run", "--config", str(config_file), *flags], console=console or ScriptConsole())
    if "--resume" in flags:
        root = work / flags[flags.index("--resume") + 1]
    else:
        fresh = set(work.iterdir()) - before
        assert len(fresh) == 1
        root = fresh.pop()
    return code, json.loads((root / "report.json").read_text())
