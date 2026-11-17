"""Huellas y copias duraderas; no se sigue un enlace al abrir un medio."""

from contextlib import contextmanager
from pathlib import Path
import hashlib
import os
import stat
import unicodedata
import uuid

from .config import require_space


class ConflictError(RuntimeError):
    pass


def stat_record(value):
    return {key: getattr(value, "st_" + key) for key in ("dev", "ino", "size", "mtime_ns", "ctime_ns")}


@contextmanager
def regular_reader(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ConflictError(f"No es archivo regular: {path}")
        yield handle


def fingerprint(path):
    with regular_reader(path) as handle:
        before = stat_record(os.fstat(handle.fileno()))
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
        after = stat_record(os.fstat(handle.fileno()))
    if before != after or stat_record(Path(path).lstat()) != after:
        raise ConflictError(f"Archivo cambiado durante lectura: {path}")
    return {**after, "sha256": digest.hexdigest()}


def check_fingerprint(path, expected):
    actual = fingerprint(path)
    if actual != expected:
        raise ConflictError(f"Entrada modificada; replantear: {path}")
    return actual


def same_content(path, sha256):
    try:
        return fingerprint(path)["sha256"] == sha256
    except (OSError, ConflictError):
        return False


def portable_key(value):
    return unicodedata.normalize("NFD", str(value)).casefold()


def assert_destination(path, *, allow_exact=False):
    """Rechazo conservador de alias case/Unicode, incluso en un volumen sensible."""
    path = Path(path).absolute()
    parent = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        if parent.is_symlink():
            raise ConflictError(f"Destino enlazado: {parent}")
        if parent.exists():
            aliases = [child for child in parent.iterdir() if portable_key(child.name) == portable_key(part)]
            for alias in aliases:
                if alias.name != part:
                    raise ConflictError(f"Colisión de mayúsculas/Unicode: {path}")
        parent = parent / part
        final = index == len(path.parts) - 2
        if parent.is_symlink():
            raise ConflictError(f"Destino enlazado: {parent}")
        if final and parent.exists() and not allow_exact:
            raise ConflictError(f"Destino existente: {path}")
        if not final and parent.exists() and not parent.is_dir():
            raise ConflictError(f"Ancestro no es directorio: {parent}")


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_copy(source, destination, expected_sha256, *, reserve=0):
    """Publicar por enlace exclusivo local; una copia parcial nunca es el destino."""
    destination = Path(destination)
    assert_destination(destination)
    require_space(destination.parent, Path(source).stat().st_size, reserve)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.part"
    try:
        with regular_reader(source) as original, part.open("xb") as output:
            original_stat = os.fstat(original.fileno())
            for block in iter(lambda: original.read(1024 * 1024), b""):
                output.write(block)
            output.flush()
            os.fchmod(output.fileno(), stat.S_IMODE(original_stat.st_mode))
            os.utime(output.fileno(), ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            os.fsync(output.fileno())
        if not same_content(part, expected_sha256):
            raise ConflictError(f"Copia no verificada: {source}")
        assert_destination(destination)
        os.link(part, destination, follow_symlinks=False)
        fsync_directory(destination.parent)
    finally:
        part.unlink(missing_ok=True)
    return fingerprint(destination)
