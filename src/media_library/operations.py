"""Publicación local recuperable. Las transformaciones escriben solo candidatos."""

from dataclasses import dataclass
from pathlib import Path
import copy
import os
import uuid

from .config import ConfigError, require_space, validate_paths
from .filesystem import (ConflictError, assert_destination, check_fingerprint, durable_copy,
                         fingerprint, fsync_directory, portable_key, same_content, stat_record)
from .inventory import entry_paths
from .models import Issue, Operation, StageResult, State
from .process import ProcessResult, ToolError
from .file_attributes import AttributeCapabilityError


@dataclass(frozen=True)
class Artifact:
    file_id: str
    path: str
    sha256: str
    evidence: dict


@dataclass(frozen=True)
class Recovery:
    operation_id: str
    actions: tuple[str, ...]
    source_matches: bool
    output_matches: bool
    backup_verified: bool
    explanation: str


def backup_hash(operation):
    return operation.evidence.get("previous_destination", operation.expected)["sha256"]


class SafeExecutor:
    def __init__(self, store):
        self.store = store
        self.config = store.config

    def _require(self):
        self.store.require()
        validate_paths(self.config)

    def prepare(self, file_id, producer, validator):
        """producer(path) -> ProcessResult o None; validator(path) -> evidencia JSON.

        El llamador aporta la validación del contenido propia de su etapa.
        Un subproceso fallido nunca produce un Artifact publicable.
        """
        self._require()
        entry = self.store.entry(file_id)
        temporary, _, _ = entry_paths(self.config, self.store.manifest.run_id, entry)
        path = temporary / "candidates" / (uuid.uuid4().hex + ".result")
        assert_destination(path)
        self.store.commit("prepare_intent", evidence={"file_id": file_id, "path": str(path)})
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = producer(path)
            if isinstance(result, ProcessResult):
                result.check()
            elif result is not None:
                raise ValueError("producer debe devolver ProcessResult o None")
            evidence = validator(path)
            if not isinstance(evidence, dict) or not evidence:
                raise ValueError("El validador debe aportar evidencia no vacía")
            sha = fingerprint(path)["sha256"]
        except (Exception, KeyboardInterrupt) as exc:
            self.store.commit("prepare_failed", state=State.FAILED,
                              evidence={"file_id": file_id, "path": str(path), "error": str(exc) or type(exc).__name__})
            raise
        self.store.commit("prepared", evidence={"file_id": file_id, "path": str(path), "sha256": sha, "validation": evidence})
        return Artifact(file_id, str(path), sha, evidence)

    def plan(self, file_id, kind, *, artifact=None, destination=None, previous_destination=None):
        self._require()
        entry = self.store.entry(file_id)
        if entry.issues:
            raise ConflictError("Resolver las incidencias de la entrada antes de modificarla")
        source = Path(entry.current_path)
        if source.resolve() != source or not source.is_relative_to(self.config.source):
            raise ConflictError("Origen fuera de la biblioteca o enlazado")
        expected = fingerprint(source)
        if {k: expected[k] for k in entry.stat} != entry.stat:
            raise ConflictError("Entrada cambiada después del inventario; replantear")
        previous = [self.store.manifest.operations[key] for key in entry.operations]
        if any(op.state not in ("COMPLETED", "RESTORED") for op in previous):
            raise ConflictError("Resolver la operación pendiente de esta entrada")
        temporary, backup, export = entry_paths(self.config, self.store.manifest.run_id, entry)
        operation_id = uuid.uuid4().hex
        if kind == "rename":
            candidate, output_sha = source, expected["sha256"]
            if destination is None:
                raise ValueError("rename requiere destino")
        elif kind in ("replace", "export", "substitute"):
            if artifact is None or artifact.file_id != file_id:
                raise ValueError("Se requiere un Artifact validado para esta entrada")
            candidate, output_sha = Path(artifact.path), artifact.sha256
            if candidate.resolve() != candidate or not candidate.is_relative_to(temporary):
                raise ConflictError("Candidato fuera del temporal de esta entrada")
            if not same_content(candidate, output_sha):
                raise ConflictError("Candidato cambiado desde su validación")
            if not any(event["kind"] == "prepared" and event["evidence"].get("path") == str(candidate)
                       and event["evidence"].get("sha256") == output_sha for event in self.store.manifest.events):
                raise ConflictError("Candidato sin evidencia de preparación")
        else:
            raise ValueError("Tipos admitidos: replace, rename, export, substitute")
        destination = Path(destination) if destination is not None else (source if kind == "replace" else export)
        if not destination.is_absolute() or ".." in destination.parts:
            raise ConflictError("Destino debe ser absoluto y normalizado")
        if kind == "replace" and destination != source:
            raise ConflictError("replace solo sustituye la entrada planificada")
        allowed = self.config.export if kind == "export" else self.config.source
        if not destination.is_relative_to(allowed) or destination == allowed:
            raise ConflictError("Destino fuera de su raíz")
        if previous_destination is not None:
            if kind != "export":
                raise ValueError("Solo export admite renovar un derivado propio")
            check_fingerprint(destination, previous_destination)
        assert_destination(destination, allow_exact=kind == "replace" or previous_destination is not None)
        for other in self.store.manifest.operations.values():
            if other.file_id != file_id and other.state not in ("COMPLETED", "RESTORED") and portable_key(other.destination) == portable_key(destination):
                raise ConflictError("Destino reservado por otra operación")
        if any(op.kind in ("replace", "rename", "substitute") for op in previous):
            backup = self.config.archive / self.store.manifest.run_id / ".operations" / operation_id / entry.relative_path
        op = Operation(operation_id, file_id, kind, str(source), str(destination), expected,
                       str(candidate), output_sha, str(backup) if kind != "export" else None,
                       str(destination.parent / (".media-" + operation_id + ".part")),
                       evidence={"validation": artifact.evidence if artifact else {"rename": True}})
        if kind == "rename" and previous:
            attributes = previous[-1].evidence.get("validation", {}).get("file_attributes", {})
            if attributes:
                op.evidence["validation"]["file_attributes"] = attributes
        if previous_destination is not None:
            op.evidence["previous_destination"] = dict(previous_destination)
            op.backup = str(self.config.archive / self.store.manifest.run_id / ".exports" / operation_id / destination.relative_to(self.config.export))
        self.store.commit("operation_planned", op)
        return op

    def _operation(self, operation_id):
        self._require()
        op = copy.deepcopy(self.store.manifest.operations[operation_id])
        source, destination = Path(op.source), Path(op.destination)
        if source.resolve() != source or not source.is_relative_to(self.config.source):
            raise ConflictError("Origen de operación fuera de raíz o enlazado")
        root = self.config.export if op.kind == "export" else self.config.source
        if not destination.is_relative_to(root) or destination.resolve() != destination:
            raise ConflictError("Destino de operación fuera de raíz o enlazado")
        if op.kind not in ("replace", "export", "rename", "substitute") or (op.kind == "replace" and destination != source):
            raise ConflictError("Tipo/destino de operación inválido")
        for name, path_root in (("backup", self.config.archive), ("local_part", destination.parent)):
            value = getattr(op, name)
            if value and (not Path(value).is_relative_to(path_root) or Path(value).resolve() != Path(value)):
                raise ConflictError(f"Ruta de {name} fuera de raíz o enlazada")
        return op

    def inspect(self, operation_id):
        op = self._operation(operation_id)
        source_matches = False
        try:
            source_matches = fingerprint(op.source) == op.expected
        except (OSError, ConflictError):
            pass
        output = same_content(op.destination, op.output_sha256)
        backup = bool(op.backup and same_content(op.backup, backup_hash(op)))
        candidate = same_content(op.candidate, op.output_sha256)
        source_exists = Path(op.source).exists() or Path(op.source).is_symlink()
        actions = []
        if op.state == "RESTORED":
            explanation = "Restauración registrada; conservar evidencia y replantear"
        elif op.state == "RESTORING" and same_content(op.source, op.expected["sha256"]):
            actions.append("restore")
            explanation = "Restauración presente pendiente de confirmar"
        elif op.state == "COMPLETED":
            intact = output and (not op.backup or backup)
            explanation = "Operación completada" if intact else "La salida o el backup completados cambiaron; replantear"
        else:
            published = op.state in ("PUBLISHING", "PUBLISHED", "FAILED") and self._owns_publication(op)
            if published and (op.kind not in ("rename", "substitute") or not source_exists or source_matches):
                actions.append("continue")
            elif source_matches and candidate:
                actions.append("continue")
            if op.kind != "export" and backup and (not source_exists or same_content(op.source, op.output_sha256)):
                actions.append("restore")
            explanation = "Comparación por huellas; elegir acción explícita" if actions else "Conflicto o contenido externo: replantear sin modificarlo"
        return Recovery(operation_id, tuple(actions), source_matches, output, backup, explanation)

    def _owns_publication(self, op):
        if op.evidence.get("publication_rejected") or not same_content(op.destination, op.output_sha256):
            return False
        try:
            identity = op.evidence.get("publication_identity")
            if identity:
                actual = fingerprint(op.destination)
                return all(actual[key] == identity[key] for key in ("dev", "ino"))
            # Recuperación de hardlinks anteriores a publication_identity. Una
            # mera coincidencia de bytes nunca acredita quién publicó el destino.
            part = Path(op.local_part)
            return not part.is_symlink() and part.samefile(op.destination)
        except (OSError, ConflictError):
            return False

    def _complete(self, op):
        if not same_content(op.destination, op.output_sha256):
            raise ConflictError("La publicación no coincide con la salida validada")
        if op.backup and not same_content(op.backup, backup_hash(op)):
            raise ConflictError("No se puede confirmar sin backup verificado")
        from .file_attributes import verify_attributes
        verify_attributes(op.destination, op.evidence.get("validation", {}).get("file_attributes", {}))
        self._cleanup_part(op)
        op.state = "COMPLETED"
        op.error = None
        op.evidence["published_stat"] = stat_record(Path(op.destination).stat())
        op.evidence["published_sha256"] = op.output_sha256
        self.store.commit("operation_completed", op, state=State.RUNNING)
        return StageResult(State.COMPLETED, [op], evidence=op.evidence)

    def _cleanup_part(self, op):
        part = Path(op.local_part)
        if not part.exists() and not part.is_symlink():
            return
        if part.is_symlink() or not part.samefile(op.destination):
            raise ConflictError("Temporal de publicación ajeno: revisar antes de limpiar")
        part.unlink()
        fsync_directory(part.parent)

    def execute(self, operation_id):
        op = self._operation(operation_id)
        if op.state == "COMPLETED":
            if not same_content(op.destination, op.output_sha256):
                raise ConflictError("La salida completada cambió; no repetir")
            if op.backup and not same_content(op.backup, backup_hash(op)):
                raise ConflictError("Backup completado ausente o cambiado; no repetir")
            from .file_attributes import verify_attributes
            verify_attributes(op.destination, op.evidence.get("validation", {}).get("file_attributes", {}))
            return StageResult(State.COMPLETED, [op], evidence=op.evidence)
        recovery = self.inspect(operation_id)
        if "continue" not in recovery.actions:
            raise ConflictError(recovery.explanation)
        published_here = op.state in ("PUBLISHING", "PUBLISHED", "FAILED") and self._owns_publication(op)
        try:
            # Publicación ya acreditada: confirmar, sin repetir la transformación.
            if published_here:
                if op.kind in ("rename", "substitute") and Path(op.source).exists():
                    check_fingerprint(op.source, op.expected)
                    if not recovery.backup_verified:
                        raise ConflictError("Falta backup verificado para terminar rename")
                    Path(op.source).unlink()
                    fsync_directory(Path(op.source).parent)
                return self._complete(op)
            check_fingerprint(op.source, op.expected)
            previous_destination = op.evidence.get("previous_destination")
            if previous_destination:
                check_fingerprint(op.destination, previous_destination)
            op.state = "STARTED"
            self.store.commit("operation_intent", op, state=State.RUNNING)
            if op.backup:
                if Path(op.backup).exists():
                    if not same_content(op.backup, backup_hash(op)):
                        raise ConflictError("Backup existente diferente")
                else:
                    durable_copy(op.destination if previous_destination else op.source, op.backup, backup_hash(op), reserve=self.config.reserve_bytes)
                check_fingerprint(op.source, op.expected)
                op.state = "BACKED_UP"
                op.evidence["backup_sha256"] = fingerprint(op.backup)["sha256"]
                self.store.commit("backup_verified", op)
            if not same_content(op.candidate, op.output_sha256):
                raise ConflictError("Candidato modificado")
            assert_destination(op.destination, allow_exact=op.kind == "replace" or bool(previous_destination))
            if Path(op.local_part).exists():
                if not same_content(op.local_part, op.output_sha256):
                    raise ConflictError("Temporal local incompleto: revisar sin sobrescribir")
            else:
                durable_copy(op.candidate, op.local_part, op.output_sha256, reserve=self.config.reserve_bytes)
            attributes = op.evidence.get("validation", {}).get("file_attributes", {})
            if attributes:
                from .file_attributes import apply_attributes
                apply_attributes(op.local_part, attributes, timeout=self.config.timeout_seconds)
            check_fingerprint(op.source, op.expected)
            if op.backup and not same_content(op.backup, backup_hash(op)):
                raise ConflictError("Backup cambiado antes de publicar")
            part = fingerprint(op.local_part)
            if part["sha256"] != op.output_sha256:
                raise ConflictError("Temporal local cambiado antes de publicar")
            op.evidence["publication_identity"] = {key: part[key] for key in ("dev", "ino")}
            op.evidence.pop("publication_rejected", None)
            op.state = "PUBLISHING"
            self.store.commit("publish_intent", op)
            assert_destination(op.destination, allow_exact=op.kind == "replace" or bool(previous_destination))
            check_fingerprint(op.source, op.expected)
            if previous_destination:
                check_fingerprint(op.destination, previous_destination)
            if op.kind == "replace" or previous_destination:
                os.replace(op.local_part, op.destination)
            else:
                os.link(op.local_part, op.destination, follow_symlinks=False)
            published_here = True
            op.evidence.pop("publication_rejected", None)
            fsync_directory(Path(op.destination).parent)
            op.state = "PUBLISHED"
            self.store.commit("published", op)
            if op.kind in ("rename", "substitute"):
                if not same_content(op.backup, op.expected["sha256"]):
                    raise ConflictError("Backup cambiado antes de retirar el original")
                check_fingerprint(op.source, op.expected)
                Path(op.source).unlink()
                fsync_directory(Path(op.source).parent)
                if op.kind == "substitute":
                    self.store.commit("source_retired", op)
            return self._complete(op)
        except (OSError, ConfigError, ConflictError, ToolError, AttributeCapabilityError) as exc:
            if not published_here:
                op.evidence["publication_rejected"] = True
            op.error, op.state = str(exc), "FAILED"
            self.store.commit("operation_failed", op, state=State.FAILED)
            return StageResult(State.FAILED, [op], [Issue("operation_failed", str(exc), op.source, op.file_id)])

    def restore(self, operation_id):
        """Restauración explícita; conserva también la salida publicada si existe."""
        op = self._operation(operation_id)
        recovery = self.inspect(operation_id)
        if "restore" not in recovery.actions:
            raise ConflictError("Restauración no segura: " + recovery.explanation)
        if not recovery.backup_verified:
            raise ConflictError("Backup no verificado")
        if op.state == "RESTORING" and same_content(op.source, op.expected["sha256"]):
            pass
        else:
            preserved = Path(op.backup).parent / (".preserved-" + op.operation_id)
            if Path(op.source).exists():
                op.evidence["preserved_output"] = str(preserved)
            op.state = "RESTORING"
            self.store.commit("restore_intent", op)
            if Path(op.source).exists():
                current = fingerprint(op.source)
                if current["sha256"] != op.output_sha256:
                    raise ConflictError("Contenido externo: no se restaura encima")
                if not preserved.exists():
                    durable_copy(op.source, preserved, op.output_sha256, reserve=self.config.reserve_bytes)
                elif not same_content(preserved, op.output_sha256):
                    raise ConflictError("La copia de salida conservada no coincide")
                restored = Path(op.local_part + ".restore")
                if not restored.exists():
                    durable_copy(op.backup, restored, op.expected["sha256"], reserve=self.config.reserve_bytes)
                if not same_content(restored, op.expected["sha256"]):
                    raise ConflictError("Temporal de restauración no verificado")
                check_fingerprint(op.source, current)
                os.replace(restored, op.source)
                fsync_directory(Path(op.source).parent)
            else:
                durable_copy(op.backup, op.source, op.expected["sha256"], reserve=self.config.reserve_bytes)
        op.state = "RESTORED"
        op.evidence["restored_stat"] = stat_record(Path(op.source).stat())
        self.store.commit("operation_restored", op, state=State.WAITING_USER)
        return StageResult(State.WAITING_USER, [op], evidence={"restored": op.source})
