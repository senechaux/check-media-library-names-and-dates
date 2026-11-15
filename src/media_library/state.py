"""Manifiesto atómico y journal duradero, bajo un único escritor por origen."""

from dataclasses import asdict
from pathlib import Path
import copy
import fcntl
import hashlib
import json
import os
import socket
import tempfile
import uuid

from .config import preflight
from .filesystem import fsync_directory
from .inventory import entry_paths
from .models import Manifest, Operation


class LockError(RuntimeError):
    pass


class PersistenceError(RuntimeError):
    pass


class SourceLock:
    """flock local + propietario persistido. Nunca se elimina el inode del lock."""

    def __init__(self, source, *, registry=None, recover_stale=False):
        self.source = Path(source).resolve(strict=True)
        root = Path(registry) if registry else Path(tempfile.gettempdir()) / f"media-library-locks-{os.getuid()}"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if root.is_symlink() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
            raise LockError("El registro de bloqueos debe ser privado y pertenecer al usuario")
        key = hashlib.sha256(os.fsencode(self.source)).hexdigest()
        self.path = root / (key + ".lock")
        self.recover_stale = recover_stale
        self.handle = None

    def __enter__(self):
        if self.handle:
            raise LockError("Bloqueo ya adquirido")
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        handle = os.fdopen(descriptor, "r+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LockError("Otro escritor mantiene el bloqueo del origen") from exc
            previous = handle.read()
            if previous and not self.recover_stale:
                raise LockError("Bloqueo obsoleto: revisar propietario y usar recover_stale=True explícitamente")
            self.previous_owner = previous or None
            handle.seek(0)
            handle.truncate()
            json.dump({"source": str(self.source), "pid": os.getpid(), "host": socket.gethostname(),
                       "token": uuid.uuid4().hex}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            raise
        self.handle = handle
        return self

    def __exit__(self, *_):
        try:
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.flush()
            os.fsync(self.handle.fileno())
        finally:
            self.handle.close()
            self.handle = None

    def require(self, source):
        if not self.handle or self.handle.closed or Path(source).resolve() != self.source:
            raise LockError("Se requiere el bloqueo activo de este origen")


def atomic_json(path, value):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".manifest-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


class RunStore:
    def __init__(self, config, lock, root, manifest):
        self.config, self.lock, self.root, self.manifest = config, lock, root, manifest
        self.poisoned = False
        self.path = root / "manifest.json"
        self.journal = root / "journal.jsonl"

    def require(self):
        self.lock.require(self.config.source)
        if self.poisoned:
            raise PersistenceError("Persistencia incierta: cerrar y recuperar la ejecución")
        if self.root.resolve() != self.root or self.path.is_symlink() or self.journal.is_symlink():
            raise PersistenceError("El almacenamiento de estado ha sido enlazado externamente")

    @classmethod
    def create(cls, config, lock, entries, *, versions=None):
        lock.require(config.source)
        detected = preflight(config)
        run_id = uuid.uuid4().hex
        root = config.workspace / run_id
        for entry in entries:
            entry_paths(config, run_id, entry)
        root.mkdir(parents=True, exist_ok=False)
        manifest = Manifest(run_id, config.effective(), {**detected, **(versions or {})}, entries)
        store = cls(config, lock, root, manifest)
        atomic_json(store.path, manifest.to_dict())
        with store.journal.open("xb") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(root)
        return store

    @classmethod
    def load(cls, config, lock, run_id):
        lock.require(config.source)
        preflight(config)
        if not run_id or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("run_id inválido")
        root = config.workspace / run_id
        if root.is_symlink() or root.resolve() != root or (root / "manifest.json").is_symlink() or (root / "journal.jsonl").is_symlink():
            raise ValueError("Estado enlazado")
        with (root / "manifest.json").open(encoding="utf-8") as handle:
            manifest = Manifest.from_dict(json.load(handle))
        if manifest.run_id != run_id or json.dumps(manifest.config, sort_keys=True) != json.dumps(config.effective(), sort_keys=True):
            raise ValueError("Configuración o identidad diferente; no se reinterpreta el estado")
        store = cls(config, lock, root, manifest)
        raw = store.journal.read_bytes()
        lines = raw.splitlines(keepends=True)
        complete_bytes = 0
        last_seq = 0
        for index, line in enumerate(lines):
            if not line.endswith(b"\n") and index == len(lines) - 1:
                break  # Cola incompleta: ninguna mutación puede depender de ella.
            record = json.loads(line)
            if record["sequence"] != last_seq + 1:
                raise PersistenceError("Journal discontinuo")
            last_seq = record["sequence"]
            if last_seq > manifest.sequence:
                store._replay(manifest, record)
            complete_bytes += len(line)
        if last_seq < manifest.sequence:
            raise PersistenceError("El manifiesto está por delante del journal")
        if complete_bytes < len(raw):
            with store.journal.open("r+b") as handle:
                handle.truncate(complete_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        atomic_json(store.path, manifest.to_dict())
        return store

    @staticmethod
    def _replay(manifest, record):
        if "entries" in record:
            snapshot = manifest.to_dict()
            snapshot["entries"] = record["entries"]
            manifest.entries = Manifest.from_dict(snapshot).entries
        operation = record.get("operation")
        if operation:
            op = Operation(**operation)
            manifest.operations[op.operation_id] = op
            entry = next(entry for entry in manifest.entries if entry.file_id == op.file_id)
            if op.operation_id not in entry.operations:
                entry.operations.append(op.operation_id)
            entry.sha256 = op.expected["sha256"]
            if op.state == "COMPLETED" and op.kind == "rename":
                entry.current_path = op.destination
            if op.state == "COMPLETED" and op.kind in ("rename", "replace"):
                entry.stat = op.evidence["published_stat"]
                entry.sha256 = op.output_sha256
            if op.state == "RESTORED":
                entry.current_path = op.source
                entry.stat = op.evidence["restored_stat"]
                entry.sha256 = op.expected["sha256"]
        manifest.events.append(copy.deepcopy(record["event"]))
        manifest.state = record["state"]
        manifest.sequence = record["sequence"]

    def commit(self, kind, operation=None, *, state=None, evidence=None, entries=None):
        self.require()
        sequence = self.manifest.sequence + 1
        event = {"sequence": sequence, "kind": kind, "operation_id": operation.operation_id if operation else None,
                 "evidence": evidence or {}}
        record = {"sequence": sequence, "event": event, "operation": asdict(operation) if operation else None,
                  "state": state or self.manifest.state}
        if entries is not None:
            record["entries"] = [asdict(entry) for entry in entries]
        updated = copy.deepcopy(self.manifest)
        self._replay(updated, record)
        try:
            with self.journal.open("ab") as handle:
                handle.write((json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n").encode())
                handle.flush()
                os.fsync(handle.fileno())
            atomic_json(self.path, updated.to_dict())
        except BaseException as exc:
            self.poisoned = True
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise PersistenceError("No se pudo confirmar el estado; recuperar antes de continuar") from exc
        self.manifest = updated

    def entry(self, file_id):
        return next(entry for entry in self.manifest.entries if entry.file_id == file_id)

    def readable_log(self):
        return "\n".join(f"{event['sequence']}: {event['kind']} {event['operation_id'] or ''}" for event in self.manifest.events)
