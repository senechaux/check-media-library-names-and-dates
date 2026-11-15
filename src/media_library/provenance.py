"""Procedencia registrada: no deducir una identidad ni una entrega por basename."""

from pathlib import Path
import hashlib
import json

from .filesystem import ConflictError, fingerprint, regular_reader, same_content
from .models import Manifest


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def manifests(store):
    """Snapshots compatibles del mismo origen y raíces; jamás seguir enlaces."""
    yield store.manifest
    for path in sorted(store.config.workspace.glob("*/manifest.json")):
        if path == store.path or path.resolve() != path:
            continue
        try:
            with regular_reader(path) as handle:
                manifest = Manifest.from_dict(json.load(handle))
            if all(manifest.config.get(name) == str(getattr(store.config, name)) for name in ("source", "archive", "export")):
                yield manifest
        except (OSError, ValueError, KeyError, TypeError):
            continue


def best_source(store, entry, *, use_archive=True):
    current = fingerprint(entry.current_path)
    lineage, owner = entry, store.manifest
    if not entry.operations:
        for manifest in manifests(store):
            found = next((e for e in manifest.entries if e.current_path == entry.current_path and e.sha256 == current["sha256"]), None)
            if found and found.operations:
                lineage, owner = found, manifest
                break
    relative = Path(lineage.original_path).relative_to(store.config.source).as_posix()
    identity = digest({"source_root": str(store.config.source), "original_relative": relative})
    result = {"identity": identity, "original_relative": relative, "path": entry.current_path,
              "sha256": current["sha256"], "current_sha256": current["sha256"], "quality_source": "current",
              "origin_file_id": lineage.file_id}
    if use_archive:
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
