"""Atributos solicitados sobre candidatos privados; se verifican tras publicar."""

from pathlib import Path
import os
import shutil
import sys

from .process import run_tool


class AttributeCapabilityError(RuntimeError):
    pass


def supports_creation_date(path):
    return sys.platform == "darwin" and hasattr(Path(path).stat(), "st_birthtime") and shutil.which("SetFile") is not None


def verify_attributes(path, targets):
    info = Path(path).stat()
    if "mtime_ns" in targets and info.st_mtime_ns != targets["mtime_ns"]:
        raise AttributeCapabilityError("FileModifyDate no coincide con el valor solicitado")
    if "birthtime_s" in targets:
        if not hasattr(info, "st_birthtime") or abs(info.st_birthtime - targets["birthtime_s"]) > 0.001:
            raise AttributeCapabilityError("FileCreateDate no coincide con el valor solicitado")


def apply_attributes(path, targets, *, timeout=60):
    if "birthtime_s" in targets:
        if not supports_creation_date(path):
            raise AttributeCapabilityError("FileCreateDate requiere macOS, birthtime y SetFile; continuar manualmente")
        run_tool([targets["exiftool"], "-overwrite_original_in_place", "-FileCreateDate=" + targets["birthtime_tag"], "--", str(path)], timeout=timeout).check()
    if "mtime_ns" in targets:
        info = Path(path).stat()
        os.utime(path, ns=(info.st_atime_ns, targets["mtime_ns"]))
    verify_attributes(path, targets)
