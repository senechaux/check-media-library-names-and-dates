from contextlib import contextmanager
from pathlib import Path

import pytest

from media_library.filesystem import ConflictError, fingerprint
from media_library.inventory import inventory
from media_library.naming import RenameBatch, reserve_names
from media_library.state import RunStore, SourceLock


@contextmanager
def stored_names(config, tmp_path, names=("a.JPG", "b.JPG")):
    for index, name in enumerate(names):
        path = config.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + str(index).encode())
    entries, result = inventory(config)
    assert result.state == "COMPLETED"
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        yield RunStore.create(config, lock, entries)


def test_stable_suffixes_reserve_existing_case_unicode_and_description(config, tmp_path):
    with stored_names(config, tmp_path, ("b.JPG", "a.JPG", "2026-01-01 12.00.00 descripción.JPG")) as store:
        entries = [entry for entry in store.manifest.entries if entry.relative_path in ("a.JPG", "b.JPG")]
        target = config.source / "2026-01-01 12.00.00 descripción.JPG"
        chosen = reserve_names(store.manifest.entries, {entry.file_id: target for entry in reversed(entries)})
        by_name = {entry.relative_path: chosen[entry.file_id] for entry in entries}
        assert by_name["a.JPG"].endswith("descripción (2).JPG")
        assert by_name["b.JPG"].endswith("descripción (3).JPG")
        (config.source / "É.JPG").write_bytes(b"occupied")
        assert " (2).JPG" in reserve_names(store.manifest.entries, {entries[0].file_id: config.source / "e\u0301.JPG"})[entries[0].file_id]


@pytest.mark.parametrize("case_only", [False, True])
def test_cycles_and_case_only_use_id_temporaries_with_backups(config, tmp_path, case_only):
    with stored_names(config, tmp_path, ("a.JPG",) if case_only else ("a.JPG", "b.JPG")) as store:
        entries = store.manifest.entries
        originals = {entry.file_id: Path(entry.current_path).read_bytes() for entry in entries}
        desired = {entries[0].file_id: config.source / ("A.jpg" if case_only else "b.JPG")}
        if not case_only:
            desired[entries[1].file_id] = config.source / "a.JPG"
        batch = RenameBatch.create(store, desired)
        batch.execute()
        for entry in store.manifest.entries:
            assert Path(entry.current_path).read_bytes() == originals[entry.file_id]
            assert Path(entry.current_path) == desired[entry.file_id]
            assert entry.original_path != entry.current_path
            assert len(entry.operations) == 2
        assert not list(config.source.glob(".media-rename-*"))
        assert not list(config.source.glob(".media-*.part"))
        for op in store.manifest.operations.values():
            assert fingerprint(op.backup)["sha256"] == op.expected["sha256"]
        assert RenameBatch.load(store, batch.data["batch_id"]).execute()["state"] == "COMPLETED"


@pytest.mark.parametrize("kind,occurrence", [("operation_planned", 1), ("published", 1), ("operation_completed", 2), ("operation_planned", 3), ("publish_intent", 4), ("operation_completed", 4)])
def test_interrupted_swap_recovers_both_legs(config, tmp_path, monkeypatch, kind, occurrence):
    with stored_names(config, tmp_path) as store:
        a, b = store.manifest.entries
        before = {entry.file_id: Path(entry.current_path).read_bytes() for entry in (a, b)}
        batch = RenameBatch.create(store, {a.file_id: Path(b.current_path), b.file_id: Path(a.current_path)})
        commit = store.commit
        count = 0
        def interrupt(event, *args, **kwargs):
            nonlocal count
            commit(event, *args, **kwargs)
            if event == kind:
                count += 1
                if count == occurrence:
                    raise KeyboardInterrupt
        monkeypatch.setattr(store, "commit", interrupt)
        with pytest.raises(KeyboardInterrupt):
            batch.execute()
        loaded = RunStore.load(config, store.lock, store.manifest.run_id)
        assert RenameBatch.load(loaded, batch.data["batch_id"]).execute()["state"] == "COMPLETED"
        assert len(loaded.manifest.operations) == 4
        assert all(Path(entry.current_path).read_bytes() == before[entry.file_id] for entry in loaded.manifest.entries)


def test_external_target_after_reservation_is_not_overwritten(config, tmp_path):
    with stored_names(config, tmp_path, ("a.JPG",)) as store:
        entry = store.manifest.entries[0]
        target = config.source / "new.JPG"
        batch = RenameBatch.create(store, {entry.file_id: target})
        target.write_bytes(b"external")
        with pytest.raises(ConflictError):
            batch.execute()
        assert target.read_bytes() == b"external"
        assert Path(store.entry(entry.file_id).current_path).read_bytes().startswith(b"\x89PNG")
        target.unlink()
        assert RenameBatch.load(store, batch.data["batch_id"]).execute()["state"] == "COMPLETED"
