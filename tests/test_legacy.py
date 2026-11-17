import importlib.util
import json
from pathlib import Path

import pytest

import common_functions
from media_library.filesystem import ConflictError
from media_library.process import ProcessResult, ToolError


def test_legacy_count_literal_names_and_missing_source(tmp_path):
    folder = tmp_path / '''quote ' " $(touch INJECTED)'''
    folder.mkdir()
    (folder / "A.JPG").write_bytes(b"synthetic")
    (folder / "B.jpg").write_bytes(b"synthetic")
    assert common_functions.count_files_with_the_extension(folder, "jpg") == "2"
    assert not (tmp_path / "INJECTED").exists()
    with pytest.raises(NotADirectoryError):
        common_functions.count_files_with_the_extension(tmp_path / "missing", "jpg")


def test_legacy_metadata_missing_tags_and_failure(monkeypatch):
    monkeypatch.setattr("media_library.legacy.run_tool", lambda *a, **k: ProcessResult(("ffprobe",), 0, '{"format": {}}'))
    assert common_functions.get_video_metadata("synthetic.MOV") == {}
    monkeypatch.setattr("media_library.legacy.run_tool", lambda *a, **k: ProcessResult(("ffprobe",), 7, stderr="synthetic failure"))
    with pytest.raises(ToolError, match="synthetic failure"):
        common_functions.get_video_metadata("synthetic.MOV")


def test_legacy_moves_refuse_collisions_and_raise_errors(tmp_path):
    source = tmp_path / "from"
    source.write_bytes(b"original")
    destination = tmp_path / "to"
    destination.write_bytes(b"existing")
    with pytest.raises(ConflictError):
        common_functions.move_file(source, destination)
    assert source.read_bytes() == b"original" and destination.read_bytes() == b"existing"
    with pytest.raises(FileNotFoundError):
        common_functions.move_file(tmp_path / "missing", tmp_path / "new")


def test_legacy_mediainfo_failure_is_typed_without_success_log(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("find_biggest", Path(__file__).parents[1] / "src/find-biggest-videos.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    video = tmp_path / "2026-clip.mp4"
    video.write_bytes(b"synthetic")
    monkeypatch.setattr(module, "MIN_FILE_SIZE_IN_MB", 0)
    received = []

    def fail(args):
        received.append(args)
        return ProcessResult(tuple(args), 5, stderr="failed process")

    monkeypatch.setattr(module, "run_tool", fail)
    with pytest.raises(ToolError):
        module.find_biggest_videos(tmp_path, tmp_path)
    assert received[0][-1] == str(video)
    assert not (tmp_path / "biggest_videos_by_size.log").exists()
