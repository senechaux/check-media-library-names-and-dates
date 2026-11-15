from pathlib import Path
import errno
import json
import sys

import pytest

from media_library.filesystem import ConflictError, fingerprint
from media_library.operations import SafeExecutor
from media_library.process import ToolError, run_tool
from media_library.state import PersistenceError, RunStore

OUTPUT = b"\x89PNG\r\n\x1a\ntransformed synthetic"


def prepared(executor, file_id):
    def producer(path):
        path.write_bytes(OUTPUT)
    return executor.prepare(file_id, producer, lambda path: {"synthetic_content": path.read_bytes() == OUTPUT})


def reload_executor(executor):
    store = executor.store
    return SafeExecutor(RunStore.load(store.config, store.lock, store.manifest.run_id))


def test_replace_verifies_backup_and_preserves_identity(execution):
    executor, file_id = execution
    entry = executor.store.entry(file_id)
    original = Path(entry.current_path).read_bytes()
    artifact = prepared(executor, file_id)
    op = executor.plan(file_id, "replace", artifact=artifact)
    assert executor.execute(op.operation_id).state == "COMPLETED"
    assert Path(op.destination).read_bytes() == OUTPUT
    assert Path(op.backup).read_bytes() == original
    assert fingerprint(op.backup)["sha256"] == op.expected["sha256"]
    loaded = reload_executor(executor)
    assert loaded.store.entry(file_id).file_id == file_id
    assert loaded.store.entry(file_id).original_path == entry.original_path
    assert loaded.execute(op.operation_id).state == "COMPLETED"
    assert "backup_verified" in loaded.store.readable_log()


@pytest.mark.parametrize("boundary,kind", [(boundary, kind)
    for kind in ("replace", "rename", "export")
    for boundary in ("operation_intent", "backup_verified", "publish_intent", "published", "operation_completed")
    if not (kind == "export" and boundary == "backup_verified")])
def test_interrupt_at_durable_boundaries_resumes_without_repeating_producer(execution, monkeypatch, boundary, kind):
    executor, file_id = execution
    artifact = prepared(executor, file_id) if kind != "rename" else None
    target = executor.config.source / "album" / "renamed.PNG" if kind == "rename" else None
    op = executor.plan(file_id, kind, artifact=artifact, destination=target)
    original_commit = executor.store.commit

    def interrupt(event, *args, **kwargs):
        original_commit(event, *args, **kwargs)
        if event == boundary:
            raise KeyboardInterrupt

    monkeypatch.setattr(executor.store, "commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        executor.execute(op.operation_id)
    loaded = reload_executor(executor)
    before_prepared = sum(e["kind"] == "prepared" for e in loaded.store.manifest.events)
    assert loaded.execute(op.operation_id).state == "COMPLETED"
    assert sum(e["kind"] == "prepared" for e in loaded.store.manifest.events) == before_prepared
    assert Path(op.destination).exists()
    if op.backup:
        assert fingerprint(op.backup)["sha256"] == op.expected["sha256"]
    if kind == "rename":
        assert not Path(op.source).exists()
        assert loaded.store.entry(file_id).current_path == op.destination


def test_external_change_after_plan_never_touches_new_content(execution):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    Path(op.source).write_bytes(b"external content")
    with pytest.raises(ConflictError):
        executor.execute(op.operation_id)
    assert Path(op.source).read_bytes() == b"external content"
    assert not Path(op.backup).exists()
    assert executor.inspect(op.operation_id).actions == ()


@pytest.mark.parametrize("target", ["backup", "destination", "local_part"])
def test_existing_conflicting_files_are_not_overwritten(execution, target):
    executor, file_id = execution
    op = executor.plan(file_id, "export" if target == "destination" else "replace", artifact=prepared(executor, file_id))
    path = Path(getattr(op, target))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"existing different content")
    before = Path(op.source).read_bytes()
    result = executor.execute(op.operation_id)
    assert result.state == "FAILED"
    assert path.read_bytes() == b"existing different content"
    assert Path(op.source).read_bytes() == before


def test_nonzero_process_with_partial_output_cannot_be_published(execution):
    executor, file_id = execution
    def fail(path):
        return run_tool([sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b'partial'); sys.exit(9)", str(path)])
    with pytest.raises(ToolError):
        executor.prepare(file_id, fail, lambda path: {"unexpected": True})
    assert executor.store.manifest.operations == {}
    assert executor.store.manifest.state == "FAILED"
    assert executor.store.manifest.events[-1]["kind"] == "prepare_failed"
    assert list(executor.store.root.rglob("*.result"))[0].read_bytes() == b"partial"


def test_partial_backup_on_disk_failure_never_changes_original(execution, monkeypatch):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    from media_library import filesystem
    from contextlib import contextmanager
    real_reader = filesystem.regular_reader

    @contextmanager
    def broken_reader(path):
        with real_reader(path) as handle:
            if str(path) != op.source:
                yield handle
                return
            class Broken:
                calls = 0
                def fileno(self):
                    return handle.fileno()
                def read(self, size):
                    self.calls += 1
                    if self.calls == 1:
                        return b"partial"
                    raise OSError(errno.ENOSPC, "synthetic disk full")
            yield Broken()

    # Inyectar al copiar, conservando la lectura de precondiciones.
    from media_library import operations
    real_copy = operations.durable_copy
    def broken_copy(*args, **kwargs):
        with monkeypatch.context() as context:
            context.setattr(filesystem, "regular_reader", broken_reader)
            return real_copy(*args, **kwargs)
    monkeypatch.setattr(operations, "durable_copy", broken_copy)
    before = Path(op.source).read_bytes()
    result = executor.execute(op.operation_id)
    assert result.state == "FAILED"
    assert Path(op.source).read_bytes() == before
    assert not Path(op.backup).exists()
    assert not list(Path(op.backup).parent.glob("*.part"))


def test_save_failure_after_publication_recovers_from_journal(execution, monkeypatch):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    from media_library import state
    original = state.atomic_json
    def fail_published(path, data):
        if data["operations"][op.operation_id]["state"] == "PUBLISHED":
            raise OSError("synthetic save failure")
        original(path, data)
    monkeypatch.setattr(state, "atomic_json", fail_published)
    with pytest.raises(PersistenceError):
        executor.execute(op.operation_id)
    assert Path(op.source).read_bytes() == OUTPUT
    monkeypatch.undo()
    loaded = reload_executor(executor)
    assert loaded.store.manifest.operations[op.operation_id].state == "PUBLISHED"
    assert loaded.execute(op.operation_id).state == "COMPLETED"


def test_explicit_restore_after_interrupted_publish_preserves_derivative(execution, monkeypatch):
    executor, file_id = execution
    original = Path(executor.store.entry(file_id).current_path).read_bytes()
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    real_commit = executor.store.commit
    def interrupt(kind, *args, **kwargs):
        real_commit(kind, *args, **kwargs)
        if kind == "published":
            raise KeyboardInterrupt
    monkeypatch.setattr(executor.store, "commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        executor.execute(op.operation_id)
    loaded = reload_executor(executor)
    assert loaded.inspect(op.operation_id).actions == ("continue", "restore")
    assert loaded.restore(op.operation_id).state == "WAITING_USER"
    assert Path(op.source).read_bytes() == original
    restored = reload_executor(loaded)
    assert restored.store.manifest.operations[op.operation_id].state == "RESTORED"
    preserved = restored.store.manifest.operations[op.operation_id].evidence["preserved_output"]
    assert Path(preserved).read_bytes() == OUTPUT
    assert restored.store.entry(file_id).stat == {key: fingerprint(op.source)[key] for key in restored.store.entry(file_id).stat}


def test_external_change_immediately_before_publication_is_preserved(execution, monkeypatch):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    commit = executor.store.commit
    def change(kind, *args, **kwargs):
        commit(kind, *args, **kwargs)
        if kind == "publish_intent":
            Path(op.source).write_bytes(b"external edit after backup")
    monkeypatch.setattr(executor.store, "commit", change)
    assert executor.execute(op.operation_id).state == "FAILED"
    assert Path(op.source).read_bytes() == b"external edit after backup"
    assert fingerprint(op.backup)["sha256"] == op.expected["sha256"]
    assert executor.inspect(op.operation_id).actions == ()


def test_candidate_changed_or_completed_backup_deleted_never_repeats(execution):
    executor, file_id = execution
    artifact = prepared(executor, file_id)
    Path(artifact.path).write_bytes(b"unvalidated candidate")
    with pytest.raises(ConflictError, match="Candidato"):
        executor.plan(file_id, "replace", artifact=artifact)
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    assert executor.execute(op.operation_id).state == "COMPLETED"
    Path(op.backup).unlink()
    with pytest.raises(ConflictError, match="Backup"):
        executor.execute(op.operation_id)
    assert Path(op.source).read_bytes() == OUTPUT


def test_real_process_exit_after_replace_requires_stale_recovery(config_file, config, tmp_path):
    from media_library.state import SourceLock, LockError
    source = config.source / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\noriginal")
    registry = tmp_path / "locks"
    result = run_tool([sys.executable, "-c", '''
from pathlib import Path
import os, sys
from media_library.config import load_config
from media_library.inventory import inventory
from media_library.operations import SafeExecutor
from media_library.state import SourceLock, RunStore
from media_library import operations
config = load_config(sys.argv[1])
entries, _ = inventory(config)
with SourceLock(config.source, registry=sys.argv[2]) as lock:
    executor = SafeExecutor(RunStore.create(config, lock, entries))
    def produce(path):
        path.write_bytes(b'new verified bytes')
    artifact = executor.prepare(entries[0].file_id, produce, lambda path: {'synthetic': True})
    operation = executor.plan(entries[0].file_id, 'replace', artifact=artifact)
    original_replace = operations.os.replace
    def hard_exit(source, destination):
        original_replace(source, destination)
        if str(destination) == operation.destination:
            os._exit(71)
    operations.os.replace = hard_exit
    executor.execute(operation.operation_id)
''', str(config_file), str(registry)])
    assert result.returncode == 71
    assert source.read_bytes() == b"new verified bytes"
    with pytest.raises(LockError, match="obsoleto"):
        with SourceLock(config.source, registry=registry):
            pass
    run_id = next(config.workspace.iterdir()).name
    with SourceLock(config.source, registry=registry, recover_stale=True) as lock:
        loaded = SafeExecutor(RunStore.load(config, lock, run_id))
        op = next(iter(loaded.store.manifest.operations.values()))
        assert op.state == "PUBLISHING"
        assert loaded.inspect(op.operation_id).backup_verified
        assert loaded.execute(op.operation_id).state == "COMPLETED"
        assert source.read_bytes() == b"new verified bytes"


def test_same_basename_entries_keep_separate_backups_and_operations(config, tmp_path):
    from media_library.inventory import inventory
    from media_library.state import SourceLock
    for album in ("a", "b"):
        path = config.source / album / "same.PNG"
        path.parent.mkdir()
        path.write_bytes(b"\x89PNG\r\n\x1a\nidentical bytes")
    entries, _ = inventory(config)
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        executor = SafeExecutor(RunStore.create(config, lock, entries))
        operations = [executor.plan(entry.file_id, "replace", artifact=prepared(executor, entry.file_id)) for entry in entries]
        assert operations[0].candidate != operations[1].candidate
        assert operations[0].backup != operations[1].backup
        for operation in operations:
            assert executor.execute(operation.operation_id).state == "COMPLETED"
            assert fingerprint(operation.backup)["sha256"] == operation.expected["sha256"]
        assert len(executor.store.manifest.operations) == 2


def test_restore_can_itself_be_interrupted_and_resumed(execution, monkeypatch):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    real_commit = executor.store.commit
    def interrupt(kind, *args, **kwargs):
        real_commit(kind, *args, **kwargs)
        if kind == "published":
            raise KeyboardInterrupt
    monkeypatch.setattr(executor.store, "commit", interrupt)
    with pytest.raises(KeyboardInterrupt):
        executor.execute(op.operation_id)
    loaded = reload_executor(executor)
    from media_library import operations
    real_replace = operations.os.replace
    def interrupt_restore(source, destination):
        real_replace(source, destination)
        if str(destination) == op.source:
            raise KeyboardInterrupt
    monkeypatch.setattr(operations.os, "replace", interrupt_restore)
    with pytest.raises(KeyboardInterrupt):
        loaded.restore(op.operation_id)
    monkeypatch.undo()
    restored = reload_executor(loaded)
    assert restored.store.manifest.operations[op.operation_id].state == "RESTORING"
    assert restored.inspect(op.operation_id).actions == ("restore",)
    assert restored.restore(op.operation_id).state == "WAITING_USER"
    assert fingerprint(op.source)["sha256"] == op.expected["sha256"]


def test_recheck_space_before_backup_stops_without_mutation(execution, monkeypatch):
    from types import SimpleNamespace
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    before = Path(op.source).read_bytes()
    monkeypatch.setattr("media_library.config.shutil.disk_usage", lambda _: SimpleNamespace(free=0))
    assert executor.execute(op.operation_id).state == "FAILED"
    assert Path(op.source).read_bytes() == before
    assert not Path(op.backup).exists()


@pytest.mark.parametrize("phase", ["STARTED", "BACKED_UP", "PUBLISHING"])
def test_persist_failure_before_publication_stops_then_replays_intent(execution, monkeypatch, phase):
    executor, file_id = execution
    op = executor.plan(file_id, "replace", artifact=prepared(executor, file_id))
    from media_library import state
    original = state.atomic_json
    before = Path(op.source).read_bytes()
    def fail(path, data):
        if data["operations"][op.operation_id]["state"] == phase:
            raise OSError("synthetic state disk full")
        return original(path, data)
    monkeypatch.setattr(state, "atomic_json", fail)
    with pytest.raises(PersistenceError):
        executor.execute(op.operation_id)
    assert Path(op.source).read_bytes() == before
    monkeypatch.undo()
    loaded = reload_executor(executor)
    assert loaded.store.manifest.operations[op.operation_id].state == phase
    assert loaded.execute(op.operation_id).state == "COMPLETED"
