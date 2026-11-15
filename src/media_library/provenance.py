"""Procedencia registrada: no deducir una identidad ni una entrega por basename."""

from pathlib import Path
import hashlib
import json
import stat

from .filesystem import ConflictError, fingerprint, regular_reader, same_content
from .models import Manifest


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


class HistoryUnavailable(ValueError):
    def __init__(self, path, cause):
        super().__init__(f"Historial no acreditable: {path} ({type(cause).__name__}). "
            "Recuperar acceso o restaurar una copia verificada; si el journal está adelantado, "
            "reanudar su ejecución antes de continuar. El error no autoriza otro envío")


def checked_snapshot(path):
    """Lectura estricta para entrega. No reparar ni omitir antecedentes inciertos."""
    try:
        if path.resolve() != path:
            raise ValueError("Historial enlazado")
        with regular_reader(path) as handle:
            manifest = Manifest.from_dict(json.load(handle))
        if (manifest.run_id != path.parent.name or not isinstance(manifest.config, dict)
            or any(not isinstance(manifest.config.get(k), str) for k in ("source", "archive"))
            or type(manifest.sequence) is not int or manifest.sequence < 0
            or not isinstance(manifest.events, list) or len(manifest.events) != manifest.sequence):
            raise ValueError("Identidad/configuración/secuencia de historial inválidas")
        for sequence, event in enumerate(manifest.events, 1):
            if (not isinstance(event, dict) or event.get("sequence") != sequence
                or not isinstance(event.get("evidence"), dict)):
                raise ValueError("Evento de historial inválido")
        # Un snapshot atrasado puede ocultar SUBMITTING del journal. Exigir su
        # recuperación mediante RunStore.load, sin escribir aquí otro run.
        journal = path.with_name("journal.jsonl")
        if journal.resolve() != journal:
            raise ValueError("Journal enlazado")
        with regular_reader(journal) as handle:
            last = 0
            for line in handle:
                if not line.endswith(b"\n"):
                    break  # Cola incompleta: ninguna mutación depende de ella.
                record = json.loads(line)
                if type(record["sequence"]) is not int or record["sequence"] != last + 1:
                    raise ValueError("Journal discontinuo")
                if last < len(manifest.events) and record["event"] != manifest.events[last]:
                    raise ValueError("Snapshot no corresponde a su journal")
                last = record["sequence"]
        if last != manifest.sequence:
            raise ValueError("Snapshot y journal requieren recuperación")
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ConflictError) as exc:
        raise HistoryUnavailable(path, exc) from exc


def manifests(store, *, strict=False):
    """Snapshots del mismo origen/archivo, también al elegir otra raíz de exportación."""
    yield store.manifest
    if strict:
        # glob omite directorios ilegibles. Enumerar primero todos los posibles
        # runs: tampoco ausencia de snapshot dentro de un run significa ausencia
        # de intentos. Un antecedente ilegible no permite saber si es relevante.
        try:
            roots = sorted(store.config.workspace.iterdir())
            for root in roots:
                if root == store.root:
                    continue
                mode = root.lstat().st_mode  # No convertir EACCES de stat en False.
                if stat.S_ISLNK(mode):
                    raise HistoryUnavailable(root, ValueError("Run enlazado"))
                if not stat.S_ISDIR(mode):
                    continue
                manifest = checked_snapshot(root / "manifest.json")
                if all(manifest.config[name] == str(getattr(store.config, name)) for name in ("source", "archive")):
                    yield manifest
        except OSError as exc:
            raise HistoryUnavailable(store.config.workspace, exc) from exc
        return
    for path in sorted(store.config.workspace.glob("*/manifest.json")):
        if path == store.path or path.resolve() != path:
            continue
        try:
            with regular_reader(path) as handle:
                manifest = Manifest.from_dict(json.load(handle))
            if all(manifest.config.get(name) == str(getattr(store.config, name)) for name in ("source", "archive")):
                yield manifest
        except (OSError, ValueError, KeyError, TypeError):
            continue


def best_source(store, entry, *, use_archive=True):
    current = fingerprint(entry.current_path)
    chain=[(store.manifest,entry)]
    snapshots=list(manifests(store));seen={(store.manifest.run_id,entry.file_id)}
    while True:
        owner,lineage=chain[-1]
        mutations=[owner.operations[key] for key in lineage.operations if owner.operations[key].state=="COMPLETED" and owner.operations[key].kind in ("replace","rename","substitute")]
        previous_path=lineage.original_path
        previous_sha=mutations[0].expected["sha256"] if mutations else lineage.sha256 or current["sha256"]
        candidates=[(manifest,old) for manifest in snapshots for old in manifest.entries
                    if (manifest.run_id,old.file_id) not in seen and old.current_path==previous_path and old.sha256==previous_sha]
        if not candidates:break
        candidates.sort(key=lambda pair:not any(pair[0].operations[k].kind in ("replace","rename","substitute") for k in pair[1].operations))
        predecessor=candidates[0];chain.append(predecessor);seen.add((predecessor[0].run_id,predecessor[1].file_id))
    owner,lineage=chain[-1]
    relative = Path(lineage.original_path).relative_to(store.config.source).as_posix()
    identity = digest({"source_root": str(store.config.source), "original_relative": relative})
    result = {"identity": identity, "original_relative": relative, "path": entry.current_path,
              "sha256": current["sha256"], "current_sha256": current["sha256"], "quality_source": "current",
              "origin_file_id": lineage.file_id}
    if use_archive:
        for owner,lineage in reversed(chain):
            for key in lineage.operations:
                op = owner.operations[key]
                if op.state != "COMPLETED" or op.kind not in ("replace", "rename", "substitute"):
                    continue
                path = Path(op.backup) if op.backup else None
                if not path or path.resolve() != path or not path.is_relative_to(store.config.archive) or not same_content(path, op.expected["sha256"]):
                    raise ConflictError("Original archivado registrado ausente/cambiado: no recomprimir el derivado")
                return {**result, "path": str(path), "sha256": op.expected["sha256"], "quality_source": "verified_archive",
                        "origin_run_id": owner.run_id, "origin_operation_id": op.operation_id}
    return result


def export_history(store, destination, identity):
    records = []
    for manifest in manifests(store):
        for op in manifest.operations.values():
            recipe = op.evidence.get("validation", {}).get("export_recipe")
            if op.kind == "export" and op.destination == str(destination) and recipe:
                records.append((manifest, op, recipe))
    owned = [r for r in records if r[2]["source"]["identity"] == identity and r[1].state == "COMPLETED"]
    if records and not owned:
        raise ConflictError("Destino asociado a otra identidad o ejecución pendiente; revisar su manifiesto")
    # La salida actual acredita qué generación está presente; no ordenar UUIDs.
    return next((r for r in owned if same_content(destination, r[1].output_sha256)), owned[-1] if owned else None)
