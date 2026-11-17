"""Herramientas reales y contenido sintético: nunca medios personales."""

from pathlib import Path
from dataclasses import replace
import os
import shutil

import pytest

from media_library.capture_dates import parse_date
from media_library.date_settings import parse_date_settings
from media_library.exiftool import ExifTool
from media_library.file_attributes import supports_creation_date, verify_attributes
from media_library.inventory import inventory
from media_library.operations import SafeExecutor
from media_library.process import run_tool
from media_library.state import RunStore, SourceLock

pytestmark = pytest.mark.integration


@pytest.fixture
def exiftool():
    executable = os.environ.get("MEDIA_LIBRARY_EXIFTOOL") or shutil.which("exiftool")
    if not executable or not Path(executable).is_file():
        pytest.skip("Falta ExifTool real; instalarlo o indicar MEDIA_LIBRARY_EXIFTOOL")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Se requieren FFmpeg y ffprobe reales para verificar contenido")
    return ExifTool(executable)


def make_media(path):
    args = ["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", "color=c=red:s=32x32:r=24:d=0.25"]
    args += ["-frames:v", "1"] if path.suffix.lower() in (".jpg", ".jpeg") else ["-c:v", "mpeg4"]
    run_tool([*args, str(path)]).check()


def configure_real(config_file, exiftool, *, policy="filename-to-metadata", manual=False, remove=False, discard=False):
    from pipeline_support import configure
    configure(config_file, modes={"metadata": "manual" if manual else "auto", "installation": "auto"})
    config_file.write_text(config_file.read_text() + f'''
[dates]
policy = "{policy}"
timezone = "Europe/Madrid"
quicktime_semantics = "utc"
remove_historical = {str(remove).lower()}
discard_description = {str(discard).lower()}
[tools.exiftool]
executable = "{exiftool.executable}"
version_args = ["-ver"]
''')


def run_real(config_file, *flags, console=None):
    from media_library.__main__ import main
    from pipeline_support import ScriptConsole
    import json
    work = config_file.parent / "work"
    before = set(work.iterdir()) if work.exists() else set()
    code = main(["run", "--config", str(config_file), *flags], console=console or ScriptConsole())
    if "--resume" in flags:
        root = work / flags[flags.index("--resume") + 1]
    else:
        fresh = set(work.iterdir()) - before
        assert len(fresh) == 1
        root = fresh.pop()
    return code, json.loads((root / "report.json").read_text())
