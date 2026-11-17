"""Fechas con procedencia y precisión; ninguna zona procede del reloj del host."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PRECISIONS = ("year", "month", "day", "second", "fraction")
STAMP = re.compile(r"^(\d{4})(?:[-:](\d{2})(?:[-:](\d{2})(?:[ T](\d{2})[:.](\d{2})[:.](\d{2})(?:[.,](\d+))?(Z|[+-]\d{2}:?\d{2})?)?)?)?$")
PREFIXES = ("diff_datetime ", "exif_getting_error ")


@dataclass(frozen=True)
class CaptureDate:
    original: str
    source: str
    value: str | None
    precision: str | None
    offset: str | None = None
    zone: str | None = None
    fold: int | None = None
    confidence: str = "observed"
    assumptions: tuple[str, ...] = ()
    issue: str | None = None

    @property
    def complete(self):
        return self.value is not None and self.precision in ("second", "fraction") and not self.issue

    @property
    def fraction(self):
        if not self.value or "." not in self.value:
            return ""
        return self.value.split(".", 1)[1].split("+")[0].split("-")[0]

    def datetime(self):
        if not self.complete:
            raise ValueError(self.issue or "Fecha incompleta")
        # La fracción se conserva aparte, incluso si tiene más de seis dígitos.
        result = datetime.fromisoformat(self.value.split(".", 1)[0])
        if self.offset:
            result = result.replace(tzinfo=fixed_offset(self.offset))
        return result


@dataclass(frozen=True)
class NameDate:
    date: CaptureDate
    description: str
    extension: str
    prefixes: tuple[str, ...] = ()


def fixed_offset(value):
    if value == "Z":
        return timezone.utc
    if not re.fullmatch(r"[+-]\d{2}:\d{2}", value):
        raise ValueError("Offset inválido")
    hours, minutes = map(int, value[1:].split(":"))
    if hours > 23 or minutes > 59:
        raise ValueError("Offset inválido")
    return timezone((1 if value[0] == "+" else -1) * timedelta(hours=hours, minutes=minutes))


def offset_text(delta):
    seconds = int(delta.total_seconds())
    if seconds % 60:
        raise ValueError("Offset histórico con segundos: requiere revisión")
    minutes = abs(seconds) // 60
    return f"{'+' if seconds >= 0 else '-'}{minutes // 60:02d}:{minutes % 60:02d}"


def parse_date(value, source):
    original = str(value) if value is not None else ""
    match = STAMP.fullmatch(original.strip())
    if not match:
        return CaptureDate(original, source, None, None, issue="missing" if not original else "invalid")
    year, month, day, hour, minute, second, fraction, offset = match.groups()
    try:
        # Validar no introduce estos valores auxiliares en el dato conservado.
        datetime(int(year), int(month or 1), int(day or 1), int(hour or 0), int(minute or 0), int(second or 0))
        if offset:
            if offset != "Z":
                offset = offset[:3] + ":" + offset[-2:]
            fixed_offset(offset)
    except ValueError:
        return CaptureDate(original, source, None, None, issue="invalid")
    precision = "fraction" if fraction else "second" if second else "day" if day else "month" if month else "year"
    normalized = year + ("-" + month if month else "") + ("-" + day if day else "")
    if second is not None:
        normalized += f"T{hour}:{minute}:{second}"
    if fraction:
        normalized += "." + fraction
    return CaptureDate(original, source, normalized, precision, offset)


def parse_name(filename):
    from pathlib import Path
    path = Path(filename)
    stem = path.stem
    prefixes = []
    while True:
        prefix = next((p for p in PREFIXES if stem.startswith(p)), None)
        if prefix is None:
            break
        prefixes.append(prefix)
        stem = stem[len(prefix):]
    match = re.match(r"^(\d{4}(?:-\d{2}(?:-\d{2}(?: \d{2}\.\d{2}\.\d{2}(?:\.\d+)?)?)?)?)(?: (.*))?$", stem)
    if not match:
        return NameDate(parse_date(None, "filename"), stem, path.suffix, tuple(prefixes))
    date = parse_date(match[1], "filename")
    return NameDate(date, match[2] or "", path.suffix, tuple(prefixes))


def resolve_zone(date, zone=None, *, fold=None, offset=None):
    if date.value and not date.issue and not date.complete and not date.offset:
        try:
            if zone:
                ZoneInfo(zone)
                return replace(date, zone=zone, confidence="assumed", assumptions=(f"configured_zone={zone}",))
            if offset:
                fixed_offset(offset)
                return replace(date, offset=offset, confidence="assumed", assumptions=(f"explicit_offset={offset}",))
        except (ValueError, ZoneInfoNotFoundError):
            return replace(date, issue="invalid_zone_or_offset")
        return date
    if not date.complete or date.offset:
        return date
    if fold not in (None, 0, 1):
        return replace(date, issue="invalid_fold")
    local = date.datetime()
    try:
        if not zone:
            if not offset:
                return replace(date, issue="zone_required")
            fixed_offset(offset)
            return replace(date, offset=offset, confidence="assumed", assumptions=(f"explicit_offset={offset}",))
        tz = ZoneInfo(zone)
        candidates = {}
        for choice in (0, 1):
            aware = local.replace(tzinfo=tz, fold=choice)
            back = aware.astimezone(timezone.utc).astimezone(tz)
            if back.replace(tzinfo=None) == local:
                candidates.setdefault(offset_text(aware.utcoffset()), (choice, aware))
        if not candidates:
            return replace(date, zone=zone, issue="nonexistent_local_time")
        if offset:
            chosen = candidates.get(offset)
            if chosen is None:
                return replace(date, zone=zone, issue="offset_zone_mismatch")
        elif len(candidates) > 1 and fold is None:
            return replace(date, zone=zone, issue="ambiguous_local_time")
        else:
            chosen = next((value for value in candidates.values() if value[0] == fold), None) if fold is not None else next(iter(candidates.values()))
            if chosen is None and len(candidates) == 1:
                chosen = next(iter(candidates.values()))
        selected_fold, aware = chosen
        return replace(date, offset=offset_text(aware.utcoffset()), zone=zone, fold=selected_fold,
                       confidence="assumed", assumptions=(f"configured_zone={zone}",))
    except (ValueError, ZoneInfoNotFoundError) as exc:
        return replace(date, zone=zone, issue="invalid_zone_or_offset")


def compare_dates(left, right):
    if left.issue or right.issue or not left.value or not right.value:
        return "unresolved"
    precision = PRECISIONS[min(PRECISIONS.index(left.precision), PRECISIONS.index(right.precision))]
    if precision in ("year", "month", "day"):
        length = {"year": 4, "month": 7, "day": 10}[precision]
        def calendar_value(date, partial):
            if date.complete and date.offset and (partial.zone or partial.offset):
                target = ZoneInfo(partial.zone) if partial.zone else fixed_offset(partial.offset)
                return date.datetime().astimezone(target).isoformat()[:length]
            return date.value[:length]
        return "matches" if calendar_value(left, right) == calendar_value(right, left) else "different"
    if not left.offset or not right.offset:
        return "unresolved"
    def whole(date):
        delta = date.datetime().astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        return delta.days * 86400 + delta.seconds
    if whole(left) != whole(right):
        return "different"
    if precision == "fraction":
        count = min(len(left.fraction), len(right.fraction))
        if left.fraction[:count] != right.fraction[:count]:
            return "different"
    return "matches"


def canonical_name(date, parsed, *, zone=None, discard_description=False):
    if not date.complete or not date.offset:
        raise ValueError("Se requiere fecha completa con zona/offset resueltos")
    value = date.datetime()
    if zone:
        value = value.astimezone(ZoneInfo(zone))
    description = "" if discard_description else parsed.description
    return value.strftime("%Y-%m-%d %H.%M.%S") + (" " + description if description else "") + parsed.extension
