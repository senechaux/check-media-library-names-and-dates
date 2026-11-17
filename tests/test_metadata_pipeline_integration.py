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


from metadata_support import exiftool, make_media, configure_real, run_real


def test_real_pipeline_prefix_write_resume_and_idempotence(exiftool, config_file):
    configure_real(config_file, exiftool, remove=True)
    source = config_file.parent / "source/diff_datetime 2026-11-10 18.59.08 descripción.JPG"
    make_media(source)
    original_bytes = source.read_bytes()
    code, result = run_real(config_file, "--apply")
    assert code == 0, result
    entry = result["files"][0]
    destination = Path(entry["current"])
    assert destination.name == "2026-11-10 18.59.08 descripción.JPG"
    assert entry["original"] == str(source) and not source.exists()
    assert exiftool.read(destination)["ExifIFD:DateTimeOriginal"] == "2026:11:10 18:59:08"
    assert Path(result["preserved"][0]["backup"]).read_bytes() == original_bytes
    assert entry["stages"]["metadata"]["state"] == "COMPLETED"
    assert run_real(config_file, "--resume", result["run_id"])[0] == 0
    code, second = run_real(config_file, "--apply")
    assert code == 0 and second["changed"] == [] and second["preserved"] == []


def test_real_pipeline_metadata_to_name_reserves_collisions(exiftool, config_file):
    configure_real(config_file, exiftool, policy="metadata-to-filename", discard=True)
    for name in ("a.JPG", "b.JPG"):
        source = config_file.parent / "source" / name
        make_media(source)
        run_tool([exiftool.executable, "-overwrite_original_in_place", "-ExifIFD:DateTimeOriginal=2026:11:10 18:59:08",
                  "-ExifIFD:OffsetTimeOriginal=+01:00", "--", str(source)]).check()
    code, result = run_real(config_file, "--apply")
    assert code == 0, result
    assert {Path(entry["current"]).name for entry in result["files"]} == {"2026-11-10 18.59.08.JPG", "2026-11-10 18.59.08 (2).JPG"}
    code, second = run_real(config_file, "--apply")
    assert code == 0 and second["changed"] == []


def test_real_conflict_requires_explicit_decision_then_reaudits(exiftool, config_file):
    from pipeline_support import ScriptConsole
    configure_real(config_file, exiftool, policy="review")
    source = config_file.parent / "source/2026-11-10 18.59.08.JPG"
    make_media(source)
    run_tool([exiftool.executable, "-overwrite_original_in_place", "-ExifIFD:DateTimeOriginal=2020:02:03 04:05:06",
              "-ExifIFD:OffsetTimeOriginal=+01:00", "--", str(source)]).check()
    code, pending = run_real(config_file, "--apply")
    assert code == 2
    assert exiftool.read(source)["ExifIFD:DateTimeOriginal"] == "2020:02:03 04:05:06"
    console = ScriptConsole(["decidir authority=filename-to-metadata", "comprobar"])
    code, result = run_real(config_file, "--resume", pending["run_id"], console=console)
    assert code == 0, result
    assert exiftool.read(source)["ExifIFD:DateTimeOriginal"] == "2026:11:10 18:59:08"
    assert result["files"][0]["stages"]["metadata"]["decisions"]["authority"] == "filename-to-metadata"


def test_real_manual_working_copy_is_validated_before_installation(exiftool, config_file):
    configure_real(config_file, exiftool, manual=True)
    source = config_file.parent / "source/2026-11-10 18.59.08.JPG"
    make_media(source)
    original_bytes = source.read_bytes()
    code, pending = run_real(config_file, "--apply")
    assert code == 2
    file_id = pending["files"][0]["file_id"]
    working = Path(pending["files"][0]["stages"]["metadata"]["pause"]["inputs"][file_id])
    before = exiftool.read(working)
    targets, attrs = exiftool.targets(before, parse_date("2026-11-10T18:59:08+01:00", "user"), parse_date_settings({}), working)
    exiftool.write(working, before, targets, attrs)
    assert source.read_bytes() == original_bytes
    code, result = run_real(config_file, "--resume", pending["run_id"])
    assert code == 0, result
    assert exiftool.read(source)["ExifIFD:DateTimeOriginal"] == "2026:11:10 18:59:08"


@pytest.mark.parametrize("event,occurrence", [("operation_planned", 1), ("operation_completed", 1), ("operation_completed", 2), ("operation_completed", 3), ("rename_batch_checkpoint", 1)])
def test_real_pipeline_interruption_recovers_dates_and_names(exiftool, config_file, monkeypatch, event, occurrence):
    configure_real(config_file, exiftool, remove=True)
    source = config_file.parent / "source/diff_datetime 2026-11-10 18.59.08.JPG"
    make_media(source)
    original = RunStore.commit
    count = 0
    def interrupt(store, kind, *args, **kwargs):
        nonlocal count
        original(store, kind, *args, **kwargs)
        if kind == event:
            count += 1
            if count == occurrence:
                raise KeyboardInterrupt
    monkeypatch.setattr(RunStore, "commit", interrupt)
    code, interrupted = run_real(config_file, "--apply")
    assert code == 130, interrupted
    monkeypatch.undo()
    code, result = run_real(config_file, "--resume", interrupted["run_id"])
    assert code == 0, result
    path = Path(result["files"][0]["current"])
    assert path.name == "2026-11-10 18.59.08.JPG"
    assert exiftool.read(path)["ExifIFD:DateTimeOriginal"] == "2026:11:10 18:59:08"
    import json
    manifest = json.loads(Path(result["paths"]["manifest.json"]).read_text())
    assert len(manifest["operations"]) == 3
    assert sum(item["kind"] == "prepared" for item in manifest["events"]) == 1


def test_real_pipeline_swaps_two_names_and_can_resume_completed_batch(exiftool, config_file):
    configure_real(config_file, exiftool, policy="metadata-to-filename")
    first = "2026-11-10 18.59.08.JPG"
    second = "2026-11-11 18.59.08.JPG"
    for name, timestamp in ((first, "2026:11:11 18:59:08"), (second, "2026:11:10 18:59:08")):
        path = config_file.parent / "source" / name
        make_media(path)
        run_tool([exiftool.executable, "-overwrite_original_in_place", "-ExifIFD:DateTimeOriginal=" + timestamp,
                  "-ExifIFD:OffsetTimeOriginal=+01:00", "--", str(path)]).check()
    code, result = run_real(config_file, "--apply")
    assert code == 0, result
    assert all(Path(entry["original"]).name != Path(entry["current"]).name for entry in result["files"])
    assert run_real(config_file, "--resume", result["run_id"])[0] == 0


@pytest.mark.parametrize("fold,utc,offset", [(0, "2026:10:25 00:30:00", "+02:00"), (1, "2026:10:25 01:30:00", "+01:00")])
def test_real_dst_fold_requires_choice_before_writing_utc(exiftool, config_file, fold, utc, offset):
    from pipeline_support import ScriptConsole
    configure_real(config_file, exiftool)
    source = config_file.parent / "source/2026-10-25 02.30.00.mp4"
    make_media(source)
    original = source.read_bytes()
    code, pending = run_real(config_file, "--apply")
    assert code == 2 and source.read_bytes() == original
    code, result = run_real(config_file, "--resume", pending["run_id"],
                            console=ScriptConsole([f"decidir fold={fold}", "comprobar"]))
    assert code == 0, result
    tags = exiftool.read(source)
    assert tags["QuickTime:CreateDate"] == utc
    assert tags["Keys:CreationDate"].endswith(offset)


def test_real_dst_gap_is_not_normalized_without_explicit_new_date(exiftool, config_file):
    from pipeline_support import ScriptConsole
    configure_real(config_file, exiftool)
    source = config_file.parent / "source/2026-03-29 02.30.00.jpg"
    make_media(source)
    original = source.read_bytes()
    code, pending = run_real(config_file, "--apply")
    assert code == 2 and source.read_bytes() == original
    code, result = run_real(config_file, "--resume", pending["run_id"],
                            console=ScriptConsole(["decidir date=2026-03-29T03:30:00+02:00", "comprobar"]))
    assert code == 0, result
    current = Path(result["files"][0]["current"])
    assert current.name == "2026-03-29 03.30.00.jpg"
    assert exiftool.read(current)["ExifIFD:DateTimeOriginal"] == "2026:03:29 03:30:00"
