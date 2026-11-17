"""Reserva global de nombres y lotes reanudables mediante operaciones del núcleo."""

from pathlib import Path
import copy
import uuid

from .filesystem import ConflictError, check_fingerprint, fingerprint, portable_key
from .operations import SafeExecutor
from .state import PersistenceError


def reserve_names(entries, desired):
    by_id = {entry.file_id: entry for entry in entries}
    moving = {by_id[key].current_path for key, value in desired.items() if str(value) != by_id[key].current_path}
    reserved = set()
    for path in {Path(value).parent for value in desired.values()}:
        if path.exists():
            reserved.update(portable_key(child) for child in path.iterdir() if str(child) not in moving)
    result = {}
    for file_id in sorted(desired, key=lambda key: (by_id[key].relative_path, key)):
        target = Path(desired[file_id])
        if str(target) == by_id[file_id].current_path:
            result[file_id] = str(target)
            reserved.add(portable_key(target))
            continue
        index = 2
        candidate = target
        while portable_key(candidate) in reserved:
            candidate = target.with_name(f"{target.stem} ({index}){target.suffix}")
            index += 1
        reserved.add(portable_key(candidate))
        result[file_id] = str(candidate)
    return result


class RenameBatch:
    def __init__(self, store, data):
        self.store, self.executor, self.data = store, SafeExecutor(store), copy.deepcopy(data)

    def save(self):
        self.store.commit("rename_batch_checkpoint", evidence={"rename_batch": self.data})

    @classmethod
    def create(cls, store, desired, *, reserve=True, purpose=None):
        store.require()
        entries = store.manifest.entries
        destinations = reserve_names(entries, desired) if reserve else {key: str(value) for key, value in desired.items()}
        keys = [portable_key(path) for path in destinations.values()]
        if len(keys) != len(set(keys)):
            raise ConflictError("Destinos del lote colisionan")
        batch_id = uuid.uuid4().hex
        moves = {}
        sources = {portable_key(store.entry(key).current_path) for key in desired}
        source_paths = {store.entry(key).current_path for key in desired}
        for file_id, target in destinations.items():
            entry = store.entry(file_id)
            source, destination = Path(entry.current_path), Path(target)
            if source == destination:
                continue
            for path in (source, destination):
                if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(store.config.source) or path.parent.resolve() != path.parent:
                    raise ConflictError("Ruta de renombrado fuera de raíz o enlazada")
            if destination.is_symlink():
                raise ConflictError("Destino enlazado")
            if destination.exists() and portable_key(destination) not in sources:
                raise ConflictError("Destino existente fuera del lote")
            if destination.parent.exists() and str(destination) in {str(child) for child in destination.parent.iterdir()} and str(destination) not in source_paths:
                raise ConflictError("Destino existente no participante")
            expected = fingerprint(source)
            if {key: expected[key] for key in entry.stat} != entry.stat:
                raise ConflictError("Entrada cambiada antes de reservar nombres")
            temporary = source.parent / f".media-rename-{batch_id}-{file_id}.tmp"
            if temporary.exists() or temporary.is_symlink():
                raise ConflictError("Temporal de renombrado ocupado")
            moves[file_id] = {"source": str(source), "temporary": str(temporary), "destination": str(destination),
                              "expected": expected, "evacuated": False, "completed": False,
                              "out_operation": None, "in_operation": None}
        value = cls(store, {"version": 1, "batch_id": batch_id, "created_sequence": store.manifest.sequence + 1,
                            "purpose": purpose, "state": "PLANNED", "moves": moves, "destinations": destinations})
        value.save()  # Reservar todo el lote antes de retirar un solo nombre.
        return value

    @classmethod
    def load(cls, store, batch_id):
        store.require()
        for event in reversed(store.manifest.events):
            value = event.get("evidence", {}).get("rename_batch")
            if value and value["batch_id"] == batch_id:
                if value["version"] != 1:
                    raise ValueError("Versión de lote desconocida")
                return cls(store, value)
        raise ValueError("Lote de renombrado no encontrado")

    def _leg(self, file_id, move, source, destination, field):
        operation_id = move[field]
        if not operation_id:
            existing = [op for op in self.store.manifest.operations.values() if op.file_id == file_id and op.kind == "rename"
                        and op.source == source and op.destination == destination and op.output_sha256 == move["expected"]["sha256"]]
            if existing:
                operation_id = existing[-1].operation_id
            else:
                operation_id = self.executor.plan(file_id, "rename", destination=Path(destination)).operation_id
            move[field] = operation_id
            self.save()
        result = self.executor.execute(operation_id)
        if result.state != "COMPLETED":
            raise ConflictError("No se completó la operación de renombrado; conservar lote y recuperar")

    def execute(self):
        self.store.require()
        if self.data["state"] == "COMPLETED":
            for move in self.data["moves"].values():
                self.executor.execute(move["in_operation"])
            return self.data
        if self.data["state"] == "PLANNED":
            for move in self.data["moves"].values():
                check_fingerprint(move["source"], move["expected"])
            self.data["state"] = "RUNNING"
            self.save()
        try:
            for file_id, move in self.data["moves"].items():
                if not move["evacuated"]:
                    self._leg(file_id, move, move["source"], move["temporary"], "out_operation")
                    move["evacuated"] = True
                    self.save()
            for file_id, move in self.data["moves"].items():
                if not move["completed"]:
                    self._leg(file_id, move, move["temporary"], move["destination"], "in_operation")
                    move["completed"] = True
                    self.save()
            self.data["state"] = "COMPLETED"
            self.save()
        except (KeyboardInterrupt, PersistenceError):
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            self.data["error"] = str(exc)
            self.save()
            raise
        return self.data
