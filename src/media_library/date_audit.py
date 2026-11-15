"""Auditoría de fuentes y selección explícita, sin mutar medios."""

from dataclasses import asdict, replace
from pathlib import Path
from .capture_dates import canonical_name, compare_dates, parse_date, parse_name, resolve_zone


def metadata_dates(tags, decision):
    dates = []
    for key, value in tags.items():
        group, _, tag = key.rpartition(":")
        base_group = group.split(":")[0]
        if base_group == "ExifIFD" and tag in ("DateTimeOriginal", "CreateDate"):
            text = str(value)
            suffix = "Original" if tag == "DateTimeOriginal" else "Digitized"
            subsecond = tags.get(group + ":SubSecTime" + suffix)
            offset = tags.get(group + ":OffsetTime" + suffix)
            if subsecond and not parse_date(text, key).fraction:
                text += "." + str(subsecond)
            if offset and not parse_date(text, key).offset:
                text += str(offset)
            date = parse_date(text, key)
        elif (base_group == "Keys" and tag == "CreationDate") or (base_group == "QuickTime" and tag == "CreateDate") or (base_group.startswith("Track") and tag in ("TrackCreateDate", "MediaCreateDate")):
            date = parse_date(value, key)
            if base_group != "Keys" and date.complete and not date.offset:
                semantics = decision["quicktime_semantics"]
                if semantics == "utc":
                    date = replace(date, offset="Z", assumptions=("declared_quicktime=utc",))
                elif semantics == "unknown":
                    date = replace(date, issue="unknown_quicktime_semantics")
        elif base_group in ("System", "MacOS") and tag in ("FileModifyDate", "FileCreateDate"):
            date = replace(parse_date(value, key), confidence="filesystem")
        else:
            continue
        if date.complete:
            date = resolve_zone(date, decision["timezone"], fold=decision["fold"], offset=decision["offset"])
        dates.append(date)
    return dates


def audit_date(filename, tags, decision):
    parsed = parse_name(filename)
    name_date = resolve_zone(parsed.date, decision["timezone"], fold=decision["fold"], offset=decision["offset"])
    sources = metadata_dates(tags, decision)
    by_tag = {date.source: date for date in sources}
    metadata = [date for date in sources if date.confidence != "filesystem"]
    eligible = [date for date in metadata if date.complete and date.offset]
    problems = []
    preferred = next((date for tag in ("ExifIFD:DateTimeOriginal", "Keys:CreationDate") for date in eligible if date.source == tag), None)
    if preferred is None:
        preferred = next((date for date in eligible if date.source != "ExifIFD:CreateDate" or decision["allow_create_date_fallback"]), None)
    comparisons = {date.source: compare_dates(name_date, date) for date in metadata}
    conflicts = any(compare_dates(left, right) == "different" for index, left in enumerate(eligible) for right in eligible[index + 1:])
    selected = None
    policy = decision["policy"]
    explicit = resolve_zone(parse_date(decision["date"], "user:date"), decision["timezone"], fold=decision["fold"], offset=decision["offset"]) if decision["date"] else None
    if policy == "filename-to-metadata":
        selected = explicit or name_date
    elif policy == "metadata-to-filename":
        if explicit:
            selected = explicit
        elif decision["source_tag"]:
            selected = by_tag.get(decision["source_tag"])
            if selected is None:
                problems.append("selected_source_missing")
        elif conflicts:
            problems.append("metadata_sources_conflict_choose_source_tag")
        else:
            selected = preferred
    elif preferred and name_date.complete and all(compare_dates(name_date, date) == "matches" for date in eligible) and not conflicts:
        selected = name_date
    else:
        problems.append("authority_required")
    if selected is None:
        problems.append("capture_date_missing_or_conflicting")
    elif not selected.complete or not selected.offset:
        problems.append(selected.issue or "partial_date_requires_decision")
    target = None
    if not problems:
        selected = replace(selected, confidence="selected")
        target = canonical_name(selected, parsed, zone=decision["timezone"], discard_description=decision["discard_description"])
        if parsed.prefixes and not decision["remove_historical"]:
            target = "".join(parsed.prefixes) + target
        if policy == "filename-to-metadata" and not explicit and not decision["remove_historical"] and not decision["discard_description"]:
            target = filename
    return {"filename": asdict(name_date), "sources": [asdict(date) for date in sources],
            "source_diagnostics": [{"source": date.source, "issue": date.issue} for date in sources if date.issue],
            "comparisons": comparisons, "metadata_conflict": conflicts, "problems": problems,
            "selected": asdict(selected) if selected else None, "decision": decision,
            "historical_prefixes": list(parsed.prefixes), "target_name": target,
            "state": "WAITING_USER" if problems else "COMPLETED"}


def audit_entries(entries, reader, decisions):
    """Conservar diagnóstico por archivo aunque otro lector falle."""
    result = []
    for entry in entries:
        try:
            tags = reader.read(entry.current_path)
            result.append({"file_id": entry.file_id, **audit_date(Path(entry.current_path).name, tags, decisions(entry))})
        except (OSError, ValueError, RuntimeError) as exc:
            result.append({"file_id": entry.file_id, "state": "FAILED", "error": str(exc)})
    return result
