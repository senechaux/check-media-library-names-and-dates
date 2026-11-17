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


from metadata_support import exiftool, make_media


@pytest.mark.parametrize("extension", ["JPG", "mp4", "mov"])
def test_real_selective_roundtrip_and_encoded_content(exiftool, tmp_path, extension):
    original = tmp_path / ("2026-11-10 18.59.08 ' $(literal)." + extension)
    make_media(original)
    seed = ["-IFD0:Artist=synthetic fixture", "-ExifIFD:DateTimeOriginal=2020:02:03 04:05:06", "-ExifIFD:SubSecTimeOriginal=123456789",
            "-ExifIFD:CreateDate=2020:02:03 04:05:06", "-ExifIFD:SubSecTimeDigitized=987654321"] if extension == "JPG" else ["-Keys:Author=synthetic fixture", "-Keys:CreationDate=2020:02:03 04:05:06.123+05:00"]
    run_tool([exiftool.executable, "-overwrite_original_in_place", *seed, "--", str(original)]).check()
    before = exiftool.read(original)
    content = exiftool.content(original, before)
    candidate = tmp_path / ("candidate." + extension)
    shutil.copy2(original, candidate)
    selected = parse_date("2026-11-10T18:59:08+01:00", "explicit")
    targets, attributes = exiftool.targets(before, selected, parse_date_settings({}), original)
    exiftool.write(candidate, before, targets, attributes)
    evidence = exiftool.verify(candidate, before, targets, content, attributes)
    assert evidence["content"] == content and evidence["non_target_metadata"] == "preserved"
    after = exiftool.read(candidate)
    if extension == "JPG":
        assert str(after["ExifIFD:SubSecTimeOriginal"]) == "123456789"
        assert str(after["ExifIFD:SubSecTimeDigitized"]) == "987654321"
        assert after["IFD0:Artist"] == "synthetic fixture"
    else:
        assert after["Keys:Author"] == "synthetic fixture"
        assert after["QuickTime:CreateDate"] == "2026:11:10 17:59:08"
        assert after["Keys:CreationDate"].endswith("+01:00")
        assert parse_date(after["Keys:CreationDate"], "Keys:CreationDate").fraction == "123"


@pytest.mark.parametrize("creation_requested", [False, True])
def test_requested_filesystem_dates_survive_safe_publication(exiftool, config, tmp_path, creation_requested):
    path = config.source / "2026-11-10 18.59.08.jpg"
    make_media(path)
    entries, _ = inventory(config)
    before = exiftool.read(path)
    coded = exiftool.content(path, before)
    options = {"set_file_modify_date": True}
    if creation_requested:
        if not supports_creation_date(path):
            pytest.skip("FileCreateDate requiere macOS, birthtime y SetFile reales")
        options["set_file_create_date"] = True
    targets, attributes = exiftool.targets(before, parse_date("2026-11-10T18:59:08+01:00", "user"), parse_date_settings(options), path)
    original_bytes = path.read_bytes()
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        store = RunStore.create(config, lock, entries)
        executor = SafeExecutor(store)
        def produce(output):
            shutil.copy2(path, output)
            exiftool.write(output, before, targets, attributes)
        artifact = executor.prepare(entries[0].file_id, produce,
                    lambda output: exiftool.verify(output, before, targets, coded, attributes))
        operation = executor.plan(entries[0].file_id, "replace", artifact=artifact)
        assert executor.execute(operation.operation_id).state == "COMPLETED"
        verify_attributes(path, attributes)
        assert Path(operation.backup).read_bytes() == original_bytes
        from media_library.naming import RenameBatch
        renamed = path.with_name("renamed.jpg")
        RenameBatch.create(store, {entries[0].file_id: renamed}).execute()
        verify_attributes(renamed, attributes)
