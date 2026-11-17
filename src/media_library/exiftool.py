"""Lectura con grupos y escritura selectiva en copias, acreditada por contenido."""

from dataclasses import asdict
from datetime import timezone
from pathlib import Path
import hashlib
import json
import os
import re
from collections import Counter

from .capture_dates import CaptureDate, parse_date, offset_text
from .file_attributes import AttributeCapabilityError, apply_attributes, supports_creation_date
from .filesystem import regular_reader
from .process import run_tool


class MetadataCapabilityError(RuntimeError):
    pass


class ExifTool:
    def __init__(self, executable="exiftool", *, timeout=60, ffprobe="ffprobe", ffmpeg="ffmpeg", runner=None):
        self.executable, self.timeout = str(executable), timeout
        self.ffprobe, self.ffmpeg = ffprobe, ffmpeg
        self.runner = runner or run_tool
        self._version = None

    def version(self):
        if self._version is None:
            self._version = self.runner([self.executable, "-ver"], timeout=self.timeout).check().stdout.strip()
        return self._version

    def read(self, path):
        result = self.runner([self.executable, "-json", "-G1:4", "-a", "-s", "-b", "-api", "QuickTimeUTC=0", "-FileCreateDate", "-all", "--", str(Path(path).absolute())], timeout=self.timeout).check()
        values = json.loads(result.stdout)
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
            raise ValueError("JSON ExifTool inválido")
        data = values[0]
        errors = [str(value) for key, value in data.items() if key.rsplit(":", 1)[-1] == "Error"]
        if errors:
            raise ValueError("; ".join(errors))
        return data

    def content(self, path, tags):
        file_type = tags.get("File:FileType")
        # La decodificación prueba legibilidad; el hash siguiente prueba bytes codificados.
        self.runner([self.ffmpeg, "-v", "error", "-xerror", "-i", str(path), "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"], timeout=self.timeout).check()
        if file_type == "JPEG":
            return {"kind": "jpeg-coded-data", "sha256": jpeg_content_hash(path)}
        if file_type in ("MP4", "MOV", "M4V"):
            output = self.runner([self.ffprobe, "-v", "error", "-show_streams", "-show_packets", "-show_data_hash", "sha256",
                                  "-show_entries", "stream=index,codec_name,codec_type,extradata_hash:packet=stream_index,size,data_hash",
                                  "-of", "json", str(path)], timeout=self.timeout).check()
            data = json.loads(output.stdout)
            if not data.get("packets") or not any(stream.get("codec_type") == "video" for stream in data.get("streams", [])):
                raise MetadataCapabilityError("Vídeo sin streams/paquetes verificables")
            coded = {"streams": [{key: stream.get(key) for key in ("index", "codec_name", "codec_type", "extradata_hash")}
                                  for stream in data["streams"]],
                     "packets": [{key: packet.get(key) for key in ("stream_index", "size", "data_hash")}
                                 for packet in data["packets"]]}
            if any(not packet["data_hash"] for packet in coded["packets"]):
                raise MetadataCapabilityError("No hay hashes de todos los paquetes")
            return {"kind": "encoded-packets", "sha256": hashlib.sha256(json.dumps(coded, sort_keys=True).encode()).hexdigest()}
        raise MetadataCapabilityError(f"Escritura/verificación automática no acreditada para {file_type}")

    def targets(self, tags, selected, decision, path):
        if not selected.complete or not selected.offset:
            raise MetadataCapabilityError("Fecha incompleta o zona no resuelta")
        value = selected.datetime()
        if decision["timezone"]:
            from zoneinfo import ZoneInfo
            value = value.astimezone(ZoneInfo(decision["timezone"]))
        local = value.strftime("%Y:%m:%d %H:%M:%S")
        offset = offset_text(value.utcoffset())
        file_type = tags.get("File:FileType")
        targets = {}
        # Familia 4 numera copias globales: Track2:Copy1 no implica dos fechas
        # dentro de Track2. Solo es ambiguo repetir la misma clave de familia 1.
        grouped = {}
        date_names = ("DateTimeOriginal", "CreateDate", "TrackCreateDate", "MediaCreateDate", "CreationDate")
        for key, item in tags.items():
            normalized = re.sub(r":Copy\d+", "", key)
            if key.rsplit(":", 1)[-1] in date_names and normalized in grouped:
                raise MetadataCapabilityError("Fechas duplicadas en una misma familia: revisión manual necesaria")
            grouped[normalized] = item
        tags = grouped
        if file_type == "JPEG":
            for name, suffix in (("DateTimeOriginal", "Original"), ("CreateDate", "Digitized")):
                targets["ExifIFD:" + name] = local
                targets["ExifIFD:OffsetTime" + suffix] = offset
                fraction = selected.fraction or tags.get("ExifIFD:SubSecTime" + suffix)
                if fraction is not None and str(fraction):
                    targets["ExifIFD:SubSecTime" + suffix] = str(fraction)
        elif file_type in ("MP4", "MOV", "M4V"):
            utc = value.astimezone(timezone.utc).strftime("%Y:%m:%d %H:%M:%S")
            targets["QuickTime:CreateDate"] = utc
            for key in tags:
                group, _, name = key.rpartition(":")
                if group.startswith("Track") and name in ("TrackCreateDate", "MediaCreateDate"):
                    targets[key] = utc
            old = parse_date(tags.get("Keys:CreationDate"), "Keys:CreationDate")
            fraction = selected.fraction or old.fraction
            targets["Keys:CreationDate"] = local + ("." + fraction if fraction else "") + offset
        else:
            raise MetadataCapabilityError(f"Escritura automática no acreditada para {file_type}; usar copia y comprobación manual")
        attributes = {}
        epoch = int(value.timestamp())
        if decision["set_file_modify_date"]:
            if len(selected.fraction) > 9:
                raise AttributeCapabilityError("FileModifyDate no admite esa precisión fraccionaria")
            attributes["mtime_ns"] = epoch * 10**9 + int(selected.fraction.ljust(9, "0") or "0")
        if decision["set_file_create_date"]:
            if not supports_creation_date(path) or selected.fraction:
                raise AttributeCapabilityError("FileCreateDate necesita macOS/SetFile y precisión de segundos; pausa manual")
            attributes.update(birthtime_s=epoch, birthtime_tag=local + offset, exiftool=self.executable)
        return targets, attributes

    def verify(self, path, before, targets, before_content, attributes=None):
        after = self.read(path)
        for key, expected in targets.items():
            values = [value for tag, value in after.items() if re.sub(r":Copy\d+", "", tag) == key]
            if len(values) != 1:
                raise MetadataCapabilityError(f"Campo objetivo ausente o ambiguo: {key}")
            actual = str(values[0])
            if key == "Keys:CreationDate":
                from .capture_dates import compare_dates
                if compare_dates(parse_date(actual, key), parse_date(expected, key)) != "matches":
                    raise MetadataCapabilityError(f"Escritura parcial: {key}")
                if parse_date(actual, key).fraction != parse_date(expected, key).fraction:
                    raise MetadataCapabilityError(f"Fracción alterada: {key}")
            elif actual != expected:
                raise MetadataCapabilityError(f"Escritura parcial: {key}: {actual!r} != {expected!r}")
        def foreign(data):
            values = Counter()
            for key, value in data.items():
                group, _, name = key.rpartition(":")
                normalized = re.sub(r":Copy\d+", "", key)
                if group.split(":")[0] in ("System", "MacOS", "ExifTool", "Composite") or key == "SourceFile" or normalized in targets or name in ("MediaDataOffset", "MediaDataSize"):
                    continue
                values[(normalized, json.dumps(value, sort_keys=True))] += 1
            return values
        missing = foreign(before) - foreign(after)
        if missing:
            raise MetadataCapabilityError(f"Metadato ajeno alterado: {next(iter(missing))[0]}")
        if self.content(path, after) != before_content:
            raise MetadataCapabilityError("El contenido codificado ha cambiado")
        if attributes:
            from .file_attributes import verify_attributes
            verify_attributes(path, attributes)
        return {"tool": "ExifTool", "version": self.version(), "targets": targets, "content": before_content,
                "file_attributes": attributes or {}, "non_target_metadata": "preserved"}

    def write(self, path, before, targets, attributes=None):
        file_type = before.get("File:FileType")
        allowed = {"ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate", "ExifIFD:OffsetTimeOriginal", "ExifIFD:OffsetTimeDigitized",
                   "ExifIFD:SubSecTimeOriginal", "ExifIFD:SubSecTimeDigitized"} if file_type == "JPEG" else {"QuickTime:CreateDate", "Keys:CreationDate"} if file_type in ("MP4", "MOV", "M4V") else set()
        if any(key not in allowed and not (file_type in ("MP4", "MOV", "M4V") and re.fullmatch(r"Track\d+:(TrackCreateDate|MediaCreateDate)", key)) for key in targets):
            raise MetadataCapabilityError("Solo se admiten los tags de fecha acordados para este formato")
        args = [self.executable, "-overwrite_original_in_place", "-P", "-api", "QuickTimeUTC=0"]
        args.extend("-" + key + "=" + value for key, value in targets.items())
        if targets:
            result = self.runner([*args, "--", str(path)], timeout=self.timeout).check()
            if "Warning:" in result.stderr or "Error:" in result.stderr:
                raise MetadataCapabilityError(result.stderr)
        if attributes:
            apply_attributes(path, attributes, timeout=self.timeout)


def jpeg_content_hash(path):
    with regular_reader(path) as handle:
        data = handle.read()
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("JPEG inválido")
    position, kept = 2, bytearray(data[:2])
    while position < len(data):
        start = position
        if data[position] != 255:
            raise ValueError("Segmento JPEG inválido")
        while position < len(data) and data[position] == 255:
            position += 1
        marker = data[position]
        position += 1
        if marker == 0xD9:
            kept.extend(data[start:position])
            return hashlib.sha256(kept).hexdigest()
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            raise ValueError("Longitud JPEG inválida")
        end = position + length
        if not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            kept.extend(data[start:end])
        position = end
        if marker == 0xDA:
            scan = position
            while position < len(data) - 1:
                if data[position] == 255 and data[position + 1] not in (0, *range(0xD0, 0xD8)):
                    break
                position += 1
            kept.extend(data[scan:position])
    raise ValueError("JPEG sin final de imagen")
