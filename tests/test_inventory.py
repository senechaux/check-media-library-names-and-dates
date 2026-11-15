from dataclasses import replace
import json
from pathlib import Path

from media_library.inventory import entry_paths, inventory
from media_library.process import ProcessResult

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic"


def fake_probe(args, **kwargs):
    return ProcessResult(tuple(args), 0, json.dumps({"format": {"format_name": "avi"},
                                                   "streams": [{"codec_type": "video", "codec_name": "mpeg4"}]}))


def test_inventory_irregular_names_png_avi_depth_and_exclusions(config):
    for relative in ["IMG_0001.JPG", "anything.PNG", "a/b/c/photo.png", "a/clip.AVI"]:
        path = config.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"avi" if path.suffix == ".AVI" else PNG)
    (config.source / ".DS_Store").write_bytes(b"ignored")
    ignored = config.source / "skip" / "photo.png"
    ignored.parent.mkdir()
    ignored.write_bytes(PNG)
    config = replace(config, exclude=(*config.exclude, "skip"))
    entries, result = inventory(config, runner=fake_probe)
    assert len(entries) == 4
    assert result.state == "COMPLETED"
    assert sorted(e.classification for e in entries) == ["image", "image", "image", "video"]
    assert next(e for e in entries if e.classification == "video").media["format"]["format_name"] == "avi"
    again, _ = inventory(config, previous=entries, runner=fake_probe)
    assert {e.current_path: e.file_id for e in entries} == {e.current_path: e.file_id for e in again}


def test_unreadable_unsupported_and_symlinks_are_reported(config, tmp_path, monkeypatch):
    (config.source / "broken.JPG").write_bytes(b"not-a-jpeg")
    (config.source / "unreadable.JPG").write_bytes(PNG)
    (config.source / "IMG_0001.JPG").write_bytes(PNG)
    (config.source / "clip.MOV").write_bytes(b"mov")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "personal.JPG").write_bytes(PNG)
    (config.source / "linked").symlink_to(outside, target_is_directory=True)
    (config.source / "link.JPG").symlink_to(outside / "personal.JPG")
    from media_library import inventory as module
    original = module.regular_reader

    def reader(path):
        if Path(path).name == "unreadable.JPG":
            raise PermissionError("synthetic unreadable")
        return original(path)

    monkeypatch.setattr(module, "regular_reader", reader)

    def probe(args, **kwargs):
        return ProcessResult(tuple(args), 3, stderr="invalid container")

    entries, result = inventory(config, runner=probe)
    assert len(entries) == 5
    assert {i.code for i in result.issues} >= {"unsupported", "unreadable_file", "probe_failed", "symlink_file", "symlink_directory"}
    assert result.state == "FAILED"
    assert not any("personal" in e.current_path for e in entries)


def test_same_basename_and_same_bytes_have_distinct_id_and_paths(config):
    for album in ("a", "b"):
        path = config.source / album / "2026-01-01 00.00.00.png"
        path.parent.mkdir()
        path.write_bytes(PNG)
    entries, _ = inventory(config)
    assert entries[0].file_id != entries[1].file_id
    paths = [entry_paths(config, "run-1", entry) for entry in entries]
    assert all(left != right for left, right in zip(*paths))
    assert paths[0][1].relative_to(config.archive).parts[1] == "a"


def test_portable_collisions_are_reported_without_destination_writes(config):
    # Aunque el host no admita ambos nombres, probar las claves en un inventario sintético.
    from media_library.filesystem import portable_key, assert_destination, ConflictError
    import pytest
    assert portable_key("Á/PHOTO.JPG") == portable_key("A\u0301/photo.jpg")
    config.export.mkdir()
    (config.export / "PHOTO.JPG").write_bytes(PNG)
    with pytest.raises(ConflictError, match="Colisión"):
        assert_destination(config.export / "photo.jpg")
    (config.export / "é.png").write_bytes(PNG)
    with pytest.raises(ConflictError):
        assert_destination(config.export / "e\u0301.png")
    assert not config.workspace.exists()


def test_archive_detects_case_and_unicode_in_ancestor_components():
    from media_library.inventory import archive_collisions
    from media_library.models import Entry
    entries = [Entry(str(index), path, path, path) for index, path in enumerate(
        ["A/one.jpg", "a/two.jpg", "é/one.jpg", "e\u0301/two.jpg", "b/one.jpg"])]
    assert {e.file_id for e in archive_collisions(entries)} == {"0", "1", "2", "3"}
