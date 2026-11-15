"""Inventario compartido sin requisitos sobre fecha, nombre o profundidad."""

from pathlib import Path
import json
import os
import uuid

from .filesystem import portable_key, regular_reader, stat_record
from .models import Entry, Issue, StageResult, State
from .process import run_tool

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mpg", ".mpeg", ".m4v", ".webm", ".3gp", ".wmv", ".mkv"}


def image_format(header):
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if header.startswith(b"BM"):
        return "bmp"
    if header.startswith((b"II*\0", b"MM\0*")):
        return "tiff"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "webp"
    if header[4:8] == b"ftyp":
        if header[8:12] in (b"heic", b"heix", b"mif1"):
            return "heif"
        if header[8:12] in (b"avif", b"avis"):
            return "avif"
    return None


def probe_media(path, config, runner=run_tool):
    executable = config.tools["ffprobe"].executable if "ffprobe" in config.tools else "ffprobe"
    result = runner([executable, "-v", "error", "-show_format", "-show_streams", "-print_format", "json", str(path)],
                    timeout=config.timeout_seconds).check()
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list) or not isinstance(data.get("format"), dict):
        raise ValueError("Respuesta ffprobe incompleta")
    streams = data["streams"]
    if not streams or any(not isinstance(stream, dict) for stream in streams):
        raise ValueError("Streams ffprobe inválidos")
    return data


def inventory(config, *, previous=(), runner=run_tool):
    entries, issues = [], []
    previous_paths = {entry.current_path: entry for entry in previous}

    def issue(code, message, path, entry=None):
        value = Issue(code, message, str(path), entry.file_id if entry else None)
        issues.append(value)
        if entry:
            entry.issues.append(value)

    def walk_error(error):
        issue("unreadable_directory", str(error), error.filename)

    for root, directories, files in os.walk(config.source, followlinks=False, onerror=walk_error):
        directories.sort()
        files.sort()
        for name in list(directories):
            path = Path(root) / name
            if config.excluded(path.relative_to(config.source)):
                directories.remove(name)
            elif path.is_symlink():
                issue("symlink_directory", "No se sigue el directorio enlazado", path)
                directories.remove(name)
        for name in files:
            path = Path(root) / name
            relative = path.relative_to(config.source)
            if config.excluded(relative):
                continue
            old = previous_paths.get(str(path))
            entry = Entry(old.file_id if old else uuid.uuid4().hex,
                          old.original_path if old else str(path), str(path),
                          old.relative_path if old else relative.as_posix())
            entries.append(entry)
            try:
                if path.is_symlink():
                    issue("symlink_file", "No se sigue un medio enlazado", path, entry)
                    continue
                entry.stat = stat_record(path.stat())
                with regular_reader(path) as handle:
                    header = handle.read(64)
                image = image_format(header)
                if image:
                    entry.classification = "image"
                    entry.media = {"container": image, "detection": "signature"}
                else:
                    # También sondear extensiones desconocidas: un cambio de sufijo no convierte el contenido.
                    try:
                        data = probe_media(path, config, runner)
                        if any(stream.get("codec_type") == "video" for stream in data["streams"]):
                            entry.classification = "video"
                            entry.media = data
                        else:
                            issue("unsupported", "No hay stream de imagen/vídeo soportado", path, entry)
                    except Exception as exc:
                        code = "probe_failed" if path.suffix.lower() in VIDEO_EXTENSIONS else "unsupported"
                        issue(code, str(exc), path, entry)
            except OSError as exc:
                entry.classification = "unreadable"
                issue("unreadable_file", str(exc), path, entry)
    for entry in archive_collisions(entries):
        issue("destination_collision", "Las rutas originales colisionan en el archivo de destino", entry.current_path, entry)
    return entries, StageResult(State.FAILED if issues else State.COMPLETED, issues=issues,
                                evidence={"entries": len(entries)})


def archive_collisions(entries):
    archive_keys, conflicts = {}, {}
    for entry in entries:
        parts = Path(entry.relative_path).parts
        for length in range(1, len(parts) + 1):
            original = Path(*parts[:length]).as_posix()
            key = portable_key(original)
            if key in archive_keys and archive_keys[key][0] != original:
                previous = archive_keys[key][1]
                conflicts[previous.file_id], conflicts[entry.file_id] = previous, entry
            else:
                archive_keys[key] = (original, entry)
    return list(conflicts.values())


def entry_paths(config, run_id, entry):
    # Los IDs solo se generan internamente; rechazar traversal en un manifiesto alterado.
    for identifier in (run_id, entry.file_id):
        if not identifier or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in identifier):
            raise ValueError("ID inválido")
    relative = Path(entry.relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Ruta original inválida")
    return (config.workspace / run_id / entry.file_id,
            config.archive / run_id / relative,
            config.export / run_id / entry.file_id / relative.name)
