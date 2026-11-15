"""Adaptadores reales de normalización/compresión y publicación por ID."""

from dataclasses import asdict
from pathlib import Path
import json

from .date_audit import audit_date
from .date_settings import effective_decision
from .filesystem import (ConflictError, assert_destination, check_fingerprint, durable_copy,
                         fingerprint, fsync_directory, regular_reader, same_content)
from .inventory import entry_paths
from .models import Issue, Manifest, StageResult, State
from .operations import Artifact
from .process import ToolError
from .stages import Adapter
from .video_driver import VideoDriver
from .video_plan import VideoPolicyError, plan_video, profile_hash
from .video_settings import parse_video_settings

VIDEO_DECISIONS = {"historical_policy", "allow_remux_growth", "quality_reviewed"}


def options(context, decisions=None):
    supplied = context.decisions if decisions is None else decisions
    raw = dict(context.store.config.video)
    for key in VIDEO_DECISIONS & supplied.keys():
        value = supplied[key]
        raw[key] = {"true": True, "false": False}.get(value, value) if key != "historical_policy" else value
    return parse_video_settings(raw)


def prior_output(config, path, signature):
    """Solo reutilizar publicaciones completas cuyo resultado y original siguen íntegros."""
    if not config.workspace.exists():
        return None
    for manifest_path in sorted(config.workspace.glob("*/manifest.json")):
        try:
            if manifest_path.resolve() != manifest_path:
                continue
            with regular_reader(manifest_path) as handle:
                manifest = Manifest.from_dict(json.load(handle))
            if manifest.config.get("source") != str(config.source):
                continue
            for op in manifest.operations.values():
                video = op.evidence.get("validation", {}).get("video", {})
                if (op.kind == "substitute" and op.state == "COMPLETED" and op.destination == str(path)
                        and video.get("profile_hash") == signature and same_content(path, op.output_sha256)
                        and op.backup and same_content(op.backup, op.expected["sha256"])):
                    return {"run_id": manifest.run_id, "operation_id": op.operation_id, "sha256": op.output_sha256}
        except (OSError, ValueError, KeyError, TypeError):
            continue  # Un manifiesto ajeno/no compatible nunca acredita una salida.
    return None


class VideoAdapter(Adapter):
    def __init__(self, stage):
        self.stage = stage
        self.identity = f"validated-video:{stage}:v1"

    def driver(self, context):
        return VideoDriver(context.store.config)

    def validate_decisions(self, context, decisions):
        options(context, decisions)
        dates = {k: v for k, v in decisions.items() if k not in VIDEO_DECISIONS}
        effective_decision(context.store.config.dates, context.entry.relative_path, dates)

    def planning(self, context):
        previous = context.pipeline.data["files"][context.file_id].get("video_work")
        if previous:
            return previous["plan"]
        settings = options(context)
        driver = self.driver(context)
        receipt = prior_output(context.store.config, context.entry.current_path, profile_hash(settings))
        plan = plan_video(context.entry.current_path, Path(context.entry.current_path).stat().st_size,
                          driver.inspect(context.entry.current_path), settings,
                          normalize=context.pipeline.mode("normalize") != "disabled",
                          compression=context.pipeline.mode("compression") != "disabled", already_validated=bool(receipt))
        if receipt:
            plan["prior_validation"] = receipt
        return plan

    def instructions(self, context):
        if context.entry.classification != "video":
            return {"tool": "Servicio de vídeo real", "expected": "Imagen: sin transformación de vídeo"}
        try:
            plan = self.planning(context)
        except (OSError, ValueError, RuntimeError) as exc:
            plan = {"pending": str(exc)}
        return {"tool": "HandBrakeCLI / FFmpeg / ffprobe / ExifTool", "settings": options(context), "video_plan": plan,
                "expected": "MP4, geometría/SAR/FPS/pistas/duración, decodificación completa y fechas verificadas; ahorro antes de instalar"}

    def waiting(self, context, code, message, evidence=None):
        return StageResult(State.WAITING_USER, issues=[Issue(code, message, context.entry.current_path, context.file_id)], evidence=evidence or {})

    def work(self, context, plan):
        value = context.pipeline.data["files"][context.file_id]
        if "video_work" not in value:
            driver = self.driver(context)
            tags = driver.dates.read(context.entry.current_path)
            supplied = {k: v for k, v in context.decisions.items() if k not in VIDEO_DECISIONS}
            decision = effective_decision(context.store.config.dates, context.entry.relative_path, supplied)
            temporal = context.entry.temporal_decision
            selected = temporal.get("selected") if temporal and not supplied else None
            if selected:
                decision = temporal["policy"]
            else:
                audit = audit_date(Path(context.entry.current_path).name, tags, decision)
                if audit["problems"]:
                    raise VideoPolicyError("Fecha de captura no resuelta: " + ", ".join(audit["problems"]))
                selected = audit["selected"]
            value["video_work"] = {"plan": plan, "selected": selected, "decision": decision, "source_tags": tags,
                                   "expected": fingerprint(context.entry.current_path)}
            context.pipeline.save()
        return value["video_work"]

    def recover(self, context, plan):
        for event in reversed(context.store.manifest.events):
            evidence = event.get("evidence", {})
            validation = evidence.get("validation", {})
            video = validation.get("video", {})
            if (event["kind"] == "prepared" and evidence.get("file_id") == context.file_id
                    and video.get("profile_hash") == plan["profile_hash"] and video["plan"]["source"] == plan["source"]):
                if not same_content(evidence["path"], evidence["sha256"]):
                    raise ConflictError("Candidato de vídeo acreditado ausente/cambiado; no recodificar")
                return Artifact(context.file_id, evidence["path"], evidence["sha256"], validation)
        return None

    def result(self, context, artifact, plan):
        technical = artifact.evidence["video"]
        if plan["require_savings"] and not technical["beneficial"]:
            return StageResult(State.COMPLETED, evidence={"unchanged": True, "reason": "not_beneficial", "video": technical,
                                                         "retained_candidate": asdict(artifact)})
        if plan["action"] == "remux" and technical["output_bytes"] > plan["source_bytes"] and not options(context)["allow_remux_growth"]:
            return self.waiting(context, "remux_growth", "Remux válido mayor: exige allow_remux_growth=true explícito", {"video": technical})
        return StageResult(State.COMPLETED, evidence={"artifact": asdict(artifact), "video_plan": plan,
                                                     "technical_validation": True, "visual_review": "pending_human"})

    def execute(self, context, *, manual=False):
        if context.entry.classification != "video":
            return StageResult(State.COMPLETED, evidence={"unchanged": True, "reason": "No es vídeo"})
        try:
            plan = self.planning(context)
            if plan["action"] == "none" or plan["stage"] != self.stage:
                return StageResult(State.COMPLETED, evidence={"unchanged": True, "video_plan": plan,
                                                             "reason": "Trabajo resuelto o reservado a la otra etapa"})
            work = self.work(context, plan)
            artifact = self.recover(context, plan)
            if artifact:
                return self.result(context, artifact, plan)
            driver = self.driver(context)
            versions = driver.capabilities(plan)
            temporary, _, _ = entry_paths(context.store.config, context.store.manifest.run_id, context.entry)
            preset_path = temporary / "video" / "preset.json"
            preset_sha = driver.write_preset(preset_path, plan)
            output = None
            if manual:
                output = Path(context.decisions.get("output") or context.pause.get("outputs", {}).get(context.file_id, ""))
                allowed = temporary / "manual" / self.stage
                if not output.is_absolute() or output.resolve() != output or not output.is_relative_to(allowed):
                    raise VideoPolicyError("Salida manual fuera del directorio propio por ID")
                if not output.is_file():
                    return self.waiting(context, "manual_video_missing", "Falta la salida MP4 en el directorio de trabajo")
            date_evidence = {}
            manual_output = {}
            def produce(path):
                check_fingerprint(plan["source"], work["expected"])
                if manual:
                    manual_output[str(output)] = fingerprint(output)["sha256"]
                    durable_copy(output, path, manual_output[str(output)], reserve=context.store.config.reserve_bytes)
                    command = ["manual-copy", str(output), str(path)]
                else:
                    commands = driver.produce(plan["source"], path, plan, preset_path)
                    context.store.commit("video_encode_intent", evidence={"file_id": context.file_id, "command": commands[0], "commands": commands,
                                         "profile_hash": plan["profile_hash"], "preset_sha256": preset_sha, "versions": versions})
                    for command in commands:
                        driver.call(command)
                date_evidence.update(driver.restore_dates(path, work["selected"], work["decision"], work["source_tags"]))
                check_fingerprint(plan["source"], work["expected"])
            def validate(path):
                result = driver.validate(plan["source"], path, plan, date_evidence)
                result["video"].update(versions=versions, preset_sha256=preset_sha, manual=manual,
                                       source_sha256=work["expected"]["sha256"], manual_output=manual_output)
                intermediate = Path(str(path) + ".video.mp4")
                if intermediate.exists():
                    result["video"]["intermediates"] = {str(intermediate): fingerprint(intermediate)["sha256"]}
                return result
            artifact = context.executor.prepare(context.file_id, produce, validate)
            return self.result(context, artifact, plan)
        except VideoPolicyError as exc:
            return self.waiting(context, "video_policy", str(exc))
        except ToolError as exc:
            if exc.result.returncode is None:
                return self.waiting(context, "video_tool_missing", str(exc))
            raise

    def run(self, context):
        return self.execute(context)

    def validate(self, context):
        return self.execute(context, manual=context.pipeline.mode(self.stage) == "manual")


def video_installation(context, artifact):
    """Devuelve None para candidatos ajenos al servicio de vídeo."""
    if not artifact or "video" not in artifact.evidence:
        return None
    video = artifact.evidence["video"]
    plan = video["plan"]
    if video.get("av_timing", {}).get("method") != "decoded-presentation:v1":
        VideoDriver(context.store.config).validate(plan["source"], artifact.path, plan, video["dates"])
    if not options(context)["quality_reviewed"] and plan["action"] == "encode":
        return StageResult(State.WAITING_USER, issues=[Issue("quality_review_pending",
            "Revisar muestra visual RF propuesto; decidir quality_reviewed=true tras la revisión humana", file_id=context.file_id)],
            evidence={"technical_validation": True, "candidate": artifact.path, "visual_review": "pending_human"})
    existing = context.record.get("operations", [])
    if existing:
        operations = [context.store.manifest.operations[key] for key in existing]
        if any(op.kind != "substitute" or op.output_sha256 != artifact.sha256 or op.destination != plan["destination"] for op in operations):
            raise ConflictError("La sustitución pendiente no coincide con el vídeo acreditado")
    else:
        assert_destination(plan["destination"])
        operation = context.executor.plan(context.file_id, "substitute", artifact=artifact, destination=plan["destination"])
        operations = [operation]
    return StageResult(State.COMPLETED, operations, evidence={"validated_artifact": artifact.sha256,
                        "video_plan": plan, "quality_review": "human_declaration" if plan["action"] == "encode" else "not_lossy"})


def cleanup_completed_videos(pipeline):
    """Solo archivos propios acreditados de una sustitución COMPLETED; nunca backups."""
    for op in list(pipeline.store.manifest.operations.values()):
        if op.kind != "substitute" or op.state != "COMPLETED":
            continue
        if any(event["kind"] == "video_cleanup_completed" and event.get("evidence", {}).get("operation_id") == op.operation_id for event in pipeline.store.manifest.events):
            continue
        pipeline.executor.execute(op.operation_id)  # Reacreditar salida y original antes de limpiar.
        temporary, _, _ = entry_paths(pipeline.store.config, pipeline.store.manifest.run_id, pipeline.store.entry(op.file_id))
        paths = {op.candidate: op.output_sha256}
        paths.update(op.evidence.get("validation", {}).get("video", {}).get("intermediates", {}))
        paths.update(op.evidence.get("validation", {}).get("video", {}).get("manual_output", {}))
        records = pipeline.data["files"][op.file_id]["stages"]
        for stage in ("normalize", "compression"):
            record = records[stage]
            if record["state"] != "COMPLETED":
                continue
            source = record.get("pause", {}).get("inputs", {}).get(op.file_id)
            if source and record.get("copy_sha256"):
                paths[source] = record["copy_sha256"]
        pipeline.store.commit("video_cleanup_intent", evidence={"operation_id": op.operation_id, "paths": paths})
        for raw, sha in paths.items():
            path = Path(raw)
            if path.resolve() != path or not path.is_relative_to(temporary):
                raise ConflictError("Temporal de limpieza fuera de ID o enlazado")
            if path.exists():
                if not same_content(path, sha):
                    raise ConflictError("Temporal cambiado: conservar para revisión")
                path.unlink()
                fsync_directory(path.parent)
        pipeline.store.commit("video_cleanup_completed", evidence={"operation_id": op.operation_id})
