"""Fallos simulados del contrato; la compatibilidad real se prueba por separado."""

import copy
import pytest

from media_library.capture_dates import parse_date
from media_library.date_settings import parse_date_settings
from media_library.exiftool import ExifTool, MetadataCapabilityError
from media_library.file_attributes import AttributeCapabilityError


def test_selective_jpeg_targets_preserve_fraction_and_never_use_all_dates(tmp_path):
    selected = parse_date("2026-11-10T18:59:08+01:00", "filename")
    before = {"File:FileType": "JPEG", "ExifIFD:SubSecTimeOriginal": "001234567", "ExifIFD:SubSecTimeDigitized": "987654321"}
    targets, attrs = ExifTool().targets(before, selected, parse_date_settings({}), tmp_path)
    assert targets["ExifIFD:DateTimeOriginal"] == targets["ExifIFD:CreateDate"] == "2026:11:10 18:59:08"
    assert targets["ExifIFD:OffsetTimeOriginal"] == "+01:00"
    assert targets["ExifIFD:SubSecTimeOriginal"] == "001234567"
    assert targets["ExifIFD:SubSecTimeDigitized"] == "987654321"
    assert "ExifIFD:ModifyDate" not in targets and attrs == {}


def test_quicktime_utc_and_local_targets_are_explicit(tmp_path):
    selected = parse_date("2026-07-10T18:59:08+02:00", "user")
    tags = {"File:FileType": "MP4", "Track1:TrackCreateDate": "0000:00:00 00:00:00", "Track2:MediaCreateDate": "0000:00:00 00:00:00",
            "Keys:CreationDate": "2020:01:01 12:00:00.123+05:00"}
    targets, _ = ExifTool().targets(tags, selected, parse_date_settings({}), tmp_path)
    assert targets["QuickTime:CreateDate"] == targets["Track1:TrackCreateDate"] == "2026:07:10 16:59:08"
    assert targets["Keys:CreationDate"] == "2026:07:10 18:59:08.123+02:00"


@pytest.mark.parametrize("fault", ["partial", "foreign", "content"])
def test_partial_write_and_unrelated_metadata_or_content_change_are_rejected(fault, tmp_path):
    before = {"File:FileType": "JPEG", "ExifIFD:DateTimeOriginal": "2020:01:01 12:00:00", "IFD0:Artist": "keep"}
    after = {**before, "ExifIFD:DateTimeOriginal": "2026:01:01 12:00:00"}
    coded = {"kind": "synthetic", "sha256": "unchanged"}
    if fault == "partial":
        after["ExifIFD:DateTimeOriginal"] = before["ExifIFD:DateTimeOriginal"]
    if fault == "foreign":
        after["IFD0:Artist"] = "changed"
    class SimulatedTool(ExifTool):
        def read(self, path):
            return after
        def content(self, path, tags):
            return {**coded, "sha256": "changed"} if fault == "content" else coded
        def version(self):
            return "simulated-only"
    with pytest.raises(MetadataCapabilityError):
        SimulatedTool().verify(tmp_path, before, {"ExifIFD:DateTimeOriginal": "2026:01:01 12:00:00"}, coded)


def test_unsupported_creation_date_and_image_formats_request_manual_work(tmp_path, monkeypatch):
    tool = ExifTool()
    selected = parse_date("2026-01-01T12:00:00Z", "user")
    monkeypatch.setattr("media_library.exiftool.supports_creation_date", lambda path: False)
    with pytest.raises(AttributeCapabilityError):
        tool.targets({"File:FileType": "JPEG"}, selected, parse_date_settings({"set_file_create_date": True}), tmp_path)
    with pytest.raises(MetadataCapabilityError):
        tool.targets({"File:FileType": "HEIC"}, selected, parse_date_settings({}), tmp_path)


def test_non_date_writes_are_refused_before_running_a_process(tmp_path):
    target = tmp_path / "copy.jpg"
    target.write_bytes(b"synthetic untouched")
    tool = ExifTool(runner=lambda *a, **k: pytest.fail("No debe lanzar una escritura no autorizada"))
    with pytest.raises(MetadataCapabilityError):
        tool.write(target, {"File:FileType": "JPEG"}, {"AllDates": "2026:01:01 12:00:00"})
    assert target.read_bytes() == b"synthetic untouched"


def test_family4_copy_numbers_across_tracks_are_not_duplicate_dates(tmp_path):
    tags = {"File:FileType": "MP4", "Track1:TrackCreateDate": "2026:01:01 00:00:00",
            "Track2:Copy1:TrackCreateDate": "2026:01:01 00:00:00"}
    tool = ExifTool()
    date = parse_date("2026-01-02T03:04:05Z", "user")
    targets, _ = tool.targets(tags, date, parse_date_settings({}), tmp_path)
    assert targets["Track1:TrackCreateDate"] == targets["Track2:TrackCreateDate"] == "2026:01:02 03:04:05"
    tags["Track1:Copy2:TrackCreateDate"] = "2025:01:01 00:00:00"
    with pytest.raises(MetadataCapabilityError, match="duplicadas"):
        tool.targets(tags, date, parse_date_settings({}), tmp_path)
