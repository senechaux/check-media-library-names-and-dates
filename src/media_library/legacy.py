"""Adaptadores de lectura; el núcleo nunca importa el main de los scripts."""

from pathlib import Path
import json
import os

from .process import run_tool


def count_extension(source_dir, extension):
    source = Path(source_dir)
    if not source.is_dir():
        raise NotADirectoryError(source)
    count = 0

    def fail(error):
        raise error

    for root, _, names in os.walk(source, followlinks=False, onerror=fail):
        for name in names:
            path = Path(root) / name
            if path.is_file() and not path.is_symlink() and path.suffix.casefold() == "." + extension.casefold().lstrip("."):
                count += 1
    return count


def video_tags(video_path, *, timeout=60):
    result = run_tool(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-print_format", "json", str(video_path)],
                      timeout=timeout).check()
    data = json.loads(result.stdout)
    tags = data.get("format", {}).get("tags", {})
    if not isinstance(tags, dict):
        raise ValueError("Tags ffprobe inválidos")
    return tags
