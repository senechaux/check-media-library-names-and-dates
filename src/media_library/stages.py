"""Puntos de integración: los servicios posteriores se inyectan como adaptadores."""

from dataclasses import dataclass
from pathlib import Path

from .filesystem import ConflictError, fingerprint
from .models import Issue, StageResult, State
from .operations import Artifact


@dataclass
class StageContext:
    pipeline: object
    stage: str
    file_id: str
    record: dict

    @property
    def store(self):
        return self.pipeline.store

    @property
    def executor(self):
        return self.pipeline.executor

    @property
    def entry(self):
        return self.store.entry(self.file_id)

    @property
    def pause(self):
        return self.record.get("pause", {})

    @property
    def decisions(self):
        return self.record.setdefault("decisions", {})

    def artifact(self):
        records = self.pipeline.data["files"][self.file_id]["stages"]
        from .pipeline_settings import FILE_STAGES
        for stage in reversed(FILE_STAGES[:FILE_STAGES.index(self.stage)]):
            value = records[stage].get("evidence", {}).get("artifact")
            if value:
                return Artifact(**value)
        return None


class Adapter:
    """run/validate -> StageResult; solo proponen operaciones, no las publican.

    run se llama tras aprobación; validate después de comprobar o al reanudar una
    pausa local. Un adaptador es responsable de validar su dominio y aportar
    evidencia JSON. Los efectos sobre originales pasan por SafeExecutor.
    """
    identity = "adapter-v1"
    simulated = False
    human = False

    def instructions(self, context):
        return {"tool": "Servicio pendiente", "settings": {},
                "expected": "Validador técnico del servicio correspondiente"}

    def run(self, context):
        return self.validate(context)

    def validate(self, context):
        return StageResult(State.WAITING_USER, issues=[Issue("validation_missing", "Falta validación de recuperación", file_id=context.file_id)])


class UnavailableAdapter(Adapter):
    def __init__(self, stage):
        self.stage = stage
        self.identity = f"unavailable:{stage}:v1"

    def instructions(self, context):
        tools = {"metadata": "A Better Finder Attributes / Rename",
                 "normalize": "Conversor MP4 externo", "compression": "HandBrake",
                 "export": "Exportador pendiente", "audit": "Auditor de medios pendiente"}
        settings = {"profile": context.pipeline.settings.compression_profile} if self.stage == "compression" else {}
        return {"tool": tools.get(self.stage, "Servicio pendiente"), "settings": settings,
                "expected": "Integrar validador técnico; confirmar por sí solo no valida el resultado"}

    def validate(self, context):
        return StageResult(State.WAITING_USER, issues=[Issue("validator_unavailable",
                           f"{self.stage}: servicio/validador aún no integrado", file_id=context.file_id)])


class HumanAdapter(Adapter):
    identity = "human-declaration:v1"
    human = True

    def instructions(self, context):
        if context.stage == "import_review":
            return {"tool": "Revisión manual de importación", "settings": {},
                    "expected": "Confirmar revisión de copias locales y descarte; este programa no sincroniza cuentas"}
        return {"tool": "Navegador (acción externa)", "settings": {},
                "expected": "Declarar entrega de este archivo; sin comprobación API ni carga desde este programa"}

    def validate(self, context):
        if not context.record.get("human_confirmed"):
            return StageResult(State.WAITING_USER)
        return StageResult(State.COMPLETED, evidence={"human_confirmation": True, "technical_verification": False})


class InstallationAdapter(Adapter):
    identity = "safe-installation:v1"

    def instructions(self, context):
        return {"tool": "SafeExecutor (núcleo real)", "settings": {},
                "expected": "Candidato validado, huella del original y backup verificado antes de publicar"}

    def run(self, context):
        artifact = context.artifact()
        records = context.pipeline.data["files"][context.file_id]["stages"]
        if artifact:
            existing = context.record.get("operations", [])
            if existing:
                operations = [context.store.manifest.operations[key] for key in existing]
                if any(op.kind != "replace" or op.output_sha256 != artifact.sha256 for op in operations):
                    raise ConflictError("La instalación pendiente no coincide con el candidato validado")
                return StageResult(State.COMPLETED, operations, evidence={"validated_artifact": artifact.sha256})
            operation = context.executor.plan(context.file_id, "replace", artifact=artifact)
            return StageResult(State.COMPLETED, [operation], evidence={"validated_artifact": artifact.sha256})
        if all(records[stage]["state"] == "DISABLED" or records[stage].get("evidence", {}).get("unchanged") or records[stage].get("evidence", {}).get("applied")
               for stage in ("metadata", "normalize", "compression")):
            return StageResult(State.COMPLETED, evidence={"unchanged": True, "reason": "Sin candidato que instalar"})
        return StageResult(State.WAITING_USER, issues=[Issue("missing_artifact", "Falta candidato validado para instalar", file_id=context.file_id)])

    validate = run


def default_adapters():
    from .metadata_stage import MetadataAdapter
    result = {stage: UnavailableAdapter(stage) for stage in ("metadata", "normalize", "compression", "export", "audit")}
    result.update(metadata=MetadataAdapter(), import_review=HumanAdapter(), delivery=HumanAdapter(), installation=InstallationAdapter())
    return result


def associate_outputs(expected_hashes, candidates, decisions=None):
    """Asociar por huella única o selección explícita; nunca por nombre/posición."""
    candidates = [Path(path) for path in candidates]
    hashes = {str(path): fingerprint(path)["sha256"] for path in candidates}
    selected, used = {}, set()
    decisions = decisions or {}
    for file_id, sha in expected_hashes.items():
        if file_id in decisions:
            path = str(Path(decisions[file_id]))
            if path not in hashes:
                raise ConflictError("Selección explícita fuera de los candidatos")
        else:
            matches = [path for path, value in hashes.items() if value == sha]
            owners = [owner for owner, value in expected_hashes.items() if value == sha]
            if len(matches) != 1 or len(owners) != 1:
                raise ConflictError("Asociación ambigua: se requiere decisión explícita por ID")
            path = matches[0]
        if path in used:
            raise ConflictError("Dos IDs no pueden compartir una misma salida")
        selected[file_id] = path
        used.add(path)
    return selected
