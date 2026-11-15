import json
import os
from pathlib import Path
import sys

import pytest

from media_library.models import State
from media_library.process import run_tool
from media_library.state import LockError, PersistenceError, RunStore, SourceLock


def test_lock_rejects_same_source_via_symlink_in_another_process(stored, tmp_path):
    store, _ = stored
    alias = tmp_path / "alias"
    alias.symlink_to(store.config.source, target_is_directory=True)
    before = store.path.read_bytes()
    result = run_tool([sys.executable, "-c", '''
import sys
from media_library.state import SourceLock, LockError
try:
    with SourceLock(sys.argv[1], registry=sys.argv[2], recover_stale=True):
        sys.exit(9)
except LockError:
    sys.exit(0)
''', str(alias), str(store.lock.path.parent)]).check()
    assert store.path.read_bytes() == before


def test_hard_exit_requires_explicit_stale_recovery(config, tmp_path):
    registry = tmp_path / "locks"
    run_tool([sys.executable, "-c", '''
import os, sys
from media_library.state import SourceLock
with SourceLock(sys.argv[1], registry=sys.argv[2]):
    os._exit(0)
''', str(config.source), str(registry)]).check()
    with pytest.raises(LockError, match="obsoleto"):
        with SourceLock(config.source, registry=registry):
            pass
    with SourceLock(config.source, registry=registry, recover_stale=True) as lock:
        assert json.loads(lock.previous_owner)["source"] == str(config.source)
        with pytest.raises(LockError, match="Otro escritor"):
            with SourceLock(config.source, registry=registry, recover_stale=True):
                pass
    with SourceLock(config.source, registry=registry):
        pass


def test_atomic_save_failure_keeps_valid_snapshot_and_replays_journal(stored, monkeypatch):
    store, _ = stored
    before = json.loads(store.path.read_text())
    from media_library import state
    original = state.os.replace

    def fail(source, destination):
        if Path(destination) == store.path:
            raise OSError("synthetic disk failure")
        return original(source, destination)

    monkeypatch.setattr(state.os, "replace", fail)
    with pytest.raises(PersistenceError):
        store.commit("test_intent", state=State.RUNNING)
    assert json.loads(store.path.read_text()) == before
    with pytest.raises(PersistenceError, match="incierta"):
        store.commit("must_not_continue")
    monkeypatch.undo()
    recovered = RunStore.load(store.config, store.lock, store.manifest.run_id)
    assert recovered.manifest.events[-1]["kind"] == "test_intent"
    assert recovered.manifest.state == "RUNNING"
    assert recovered.manifest.sequence == 1


def test_interrupted_after_replace_leaves_complete_new_manifest(stored, monkeypatch):
    store, _ = stored
    from media_library import state
    original = state.fsync_directory

    def interrupt(path):
        raise KeyboardInterrupt

    monkeypatch.setattr(state, "fsync_directory", interrupt)
    with pytest.raises(KeyboardInterrupt):
        store.commit("new_complete_snapshot")
    assert json.loads(store.path.read_text())["sequence"] == 1
    monkeypatch.setattr(state, "fsync_directory", original)
    loaded = RunStore.load(store.config, store.lock, store.manifest.run_id)
    assert loaded.manifest.sequence == 1


def test_torn_journal_tail_is_discarded_but_corrupt_records_are_rejected(stored):
    store, _ = stored
    store.commit("good")
    with store.journal.open("ab") as handle:
        handle.write(b'{"sequence":2,"oper')
    loaded = RunStore.load(store.config, store.lock, store.manifest.run_id)
    assert loaded.manifest.sequence == 1
    assert loaded.journal.read_bytes().endswith(b"\n")
    with store.journal.open("ab") as handle:
        handle.write(b'{bad}\n')
    with pytest.raises(json.JSONDecodeError):
        RunStore.load(store.config, store.lock, store.manifest.run_id)


def test_unknown_manifest_and_unlocked_writes_are_rejected(stored):
    store, _ = stored
    data = json.loads(store.path.read_text())
    data["schema_version"] = 99
    store.path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Versión"):
        RunStore.load(store.config, store.lock, store.manifest.run_id)
    other_lock = SourceLock(store.config.source, registry=store.lock.path.parent)
    with pytest.raises(LockError, match="activo"):
        RunStore.create(store.config, other_lock, [])


def test_linked_journal_cannot_modify_an_unrelated_file(stored, tmp_path):
    store, _ = stored
    outside = tmp_path / "unrelated"
    outside.write_bytes(b"untouched")
    store.journal.unlink()
    store.journal.symlink_to(outside)
    with pytest.raises(PersistenceError, match="enlazado"):
        store.commit("unsafe")
    with pytest.raises(ValueError, match="enlazado"):
        RunStore.load(store.config, store.lock, store.manifest.run_id)
    assert outside.read_bytes() == b"untouched"
