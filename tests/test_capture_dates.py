from dataclasses import asdict

import pytest

from media_library.capture_dates import canonical_name, compare_dates, parse_date, parse_name, resolve_zone
from media_library.date_settings import effective_decision, parse_date_settings


@pytest.mark.parametrize("stamp", ["2026-11-10T17:59:08Z", "2026-11-10T18:59:08+01:00", "2026-11-10T18:59:08.123456789+0100", "2026:11:10 18:59:08.9+01:00"])
def test_matching_instants_with_offsets_and_fractions(stamp):
    name = resolve_zone(parse_name("2026-11-10 18.59.08.JPG").date, "Europe/Madrid")
    assert compare_dates(name, parse_date(stamp, "tag")) == "matches"
    assert name.assumptions == ("configured_zone=Europe/Madrid",)


def test_arbitrary_two_hours_59_minutes_is_a_real_difference():
    name = resolve_zone(parse_name("2026-11-10 18.59.08.mp4").date, "Etc/UTC")
    assert compare_dates(name, parse_date("2026-11-10T21:58:08Z", "tag")) == "different"


@pytest.mark.parametrize("value", ["2026-02-29", "2026-00-01", "2026-01-00", "2026-01-01T24:00:00", "0000", "2026-01-01T12:00:00+25:00", "not a date"])
def test_invalid_dates_are_reported(value):
    assert parse_date(value, "test").issue == "invalid"


@pytest.mark.parametrize("name,precision", [("1987 vacaciones.jpg", "year"), ("1987-02 vacaciones.jpg", "month"), ("1987-02-10 vacaciones.jpg", "day")])
def test_partial_dates_never_become_complete_timestamps(name, precision):
    date = parse_name(name).date
    assert date.precision == precision and not date.complete
    assert "T" not in date.value
    with pytest.raises(ValueError):
        canonical_name(date, parse_name(name))


def test_dst_gap_fold_and_explicit_offset():
    gap = parse_date("2026-03-29T02:30:00", "filename")
    assert resolve_zone(gap, "Europe/Madrid").issue == "nonexistent_local_time"
    repeated = parse_date("2026-10-25T02:30:00", "filename")
    assert resolve_zone(repeated, "Europe/Madrid").issue == "ambiguous_local_time"
    first = resolve_zone(repeated, "Europe/Madrid", fold=0)
    second = resolve_zone(repeated, "Europe/Madrid", offset="+01:00")
    assert first.offset == "+02:00" and second.offset == "+01:00"
    assert compare_dates(first, second) == "different"
    assert resolve_zone(repeated, "Europe/Madrid", offset="+03:00").issue == "offset_zone_mismatch"
    assert resolve_zone(parse_date("2026-07-10T12:00:00", "test"), "Europe/Madrid").offset == "+02:00"
    assert resolve_zone(parse_date("2026-01-10T12:00:00", "test"), "Europe/Madrid").offset == "+01:00"
    assert resolve_zone(parse_date("2026-01-10T12:00:00", "test"), "Europe/Madrid").fold == 0


def test_no_host_zone_and_fractions_remain_lossless():
    assert resolve_zone(parse_date("2026-01-10T12:00:00", "test")).issue == "zone_required"
    value = parse_date("2026-01-10T12:00:00.123456789+01:00", "test")
    assert value.fraction == "123456789"
    assert compare_dates(value, parse_date("2026-01-10T11:00:00.123456788Z", "test")) == "different"
    assert compare_dates(value, parse_date("2026-01-10T11:00:00.123Z", "test")) == "matches"


def test_historical_prefixes_and_description_only_affect_basename():
    parsed = parse_name("diff_datetime folder/exif_getting_error diff_datetime 2026-11-10 18.59.08 descripción.JPG")
    assert parsed.prefixes == ("exif_getting_error ", "diff_datetime ")
    chosen = resolve_zone(parsed.date, "Europe/Madrid")
    assert canonical_name(chosen, parsed) == "2026-11-10 18.59.08 descripción.JPG"
    assert canonical_name(chosen, parsed, discard_description=True) == "2026-11-10 18.59.08.JPG"


def test_per_file_and_persisted_decisions_override_explicit_batch_settings():
    settings = parse_date_settings({"timezone": "Europe/Madrid", "files": {"album/a.JPG": {"policy": "filename-to-metadata"}}})
    assert effective_decision(settings, "album/a.JPG")["policy"] == "filename-to-metadata"
    assert effective_decision(settings, "album/b.JPG")["policy"] == "review"
    decision = effective_decision(settings, "album/a.JPG", {"authority": "metadata-to-filename", "fold": "1", "remove_historical": "true"})
    assert decision["fold"] == 1 and decision["remove_historical"] is True


def test_sources_conflict_even_with_priority_and_filesystem_is_never_fallback():
    from media_library.date_audit import audit_date
    settings = effective_decision(parse_date_settings({"timezone": "Europe/Madrid"}), "a.JPG")
    tags = {"ExifIFD:DateTimeOriginal": "2026:11:10 18:59:08", "ExifIFD:CreateDate": "2026:11:10 21:58:08",
            "System:FileModifyDate": "2026:11:10 18:59:08+01:00"}
    report = audit_date("2026-11-10 18.59.08.JPG", tags, settings)
    assert report["metadata_conflict"] and report["state"] == "WAITING_USER"
    report = audit_date("1987 vacaciones.JPG", {"System:FileModifyDate": tags["System:FileModifyDate"]}, settings)
    assert report["state"] == "WAITING_USER" and report["filename"]["precision"] == "year"
    assert not report["selected"]


def test_explicit_direction_selects_source_and_preserves_historical_label_until_requested():
    from media_library.date_audit import audit_date
    settings = effective_decision(parse_date_settings({"timezone": "Europe/Madrid", "policy": "filename-to-metadata"}), "a.JPG")
    name = "diff_datetime 2026-11-10 18.59.08 descripción.JPG"
    tags = {"ExifIFD:DateTimeOriginal": "2026:11:10 21:58:08"}
    report = audit_date(name, tags, settings)
    assert report["state"] == "COMPLETED" and report["target_name"] == name
    report = audit_date(name, tags, {**settings, "remove_historical": True})
    assert report["target_name"] == "2026-11-10 18.59.08 descripción.JPG"


def test_bad_reader_isolated_per_file():
    from media_library.date_audit import audit_entries
    from media_library.models import Entry
    entries = [Entry("a", "a.JPG", "a.JPG", "a.JPG"), Entry("b", "2026-01-01 12.00.00.JPG", "2026-01-01 12.00.00.JPG", "b.JPG")]
    class Reader:
        def read(self, path):
            if path == "a.JPG":
                raise ValueError("synthetic read error")
            return {"ExifIFD:DateTimeOriginal": "2026:01:01 12:00:00", "ExifIFD:OffsetTimeOriginal": "+01:00"}
    settings = effective_decision(parse_date_settings({"timezone": "Europe/Madrid"}), "a.JPG")
    reports = audit_entries(entries, Reader(), lambda entry: settings)
    assert reports[0]["state"] == "FAILED" and reports[1]["state"] == "COMPLETED"


def test_grouped_exif_offsets_and_fractions_keep_the_raw_value():
    from media_library.date_audit import metadata_dates
    decision = effective_decision(parse_date_settings({}), "a.JPG")
    raw = "2026:11:10 18:59:08+01:00"
    sources = metadata_dates({"ExifIFD:DateTimeOriginal": raw, "ExifIFD:SubSecTimeOriginal": "001234567"}, decision)
    assert sources[0].original == raw and sources[0].fraction == "001234567"
    assert sources[0].offset == "+01:00"
