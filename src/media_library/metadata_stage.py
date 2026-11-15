"""Servicio real de fechas y nombres para el pipeline; sin conversión de formatos."""

from dataclasses import asdict
from pathlib import Path
import copy
import shutil

from .capture_dates import CaptureDate, parse_name
from .date_audit import audit_date
from .date_settings import effective_decision
from .exiftool import ExifTool, MetadataCapabilityError
from .file_attributes import AttributeCapabilityError, verify_attributes
from .filesystem import ConflictError, fingerprint, same_content
from .inventory import entry_paths
from .models import Issue, StageResult, State
from .naming import RenameBatch, reserve_names
from .operations import Artifact
from .process import ToolError
from .stages import Adapter, associate_outputs
from .state import PersistenceError


class MetadataAdapter(Adapter):
    identity = "metadata-and-naming:v1"

    def __init__(self, tool=None):
        self.tool = tool
        self.attempted = set()

    def driver(self, context):
        if self.tool:
            return self.tool
        config = context.store.config
        def executable(name):
            return config.tools[name].executable if name in config.tools else name
        return ExifTool(executable("exiftool"), timeout=config.timeout_seconds,
                        ffprobe=executable("ffprobe"), ffmpeg=executable("ffmpeg"))

    def decision(self, context):
        return effective_decision(context.store.config.dates, context.entry.relative_path, context.decisions)

    def validate_decisions(self, context, decisions):
        effective_decision(context.store.config.dates, context.entry.relative_path, decisions)

    def analyse(self, context, *, path=None, filename=None):
        tool = self.driver(context)
        tags = tool.read(path or context.entry.current_path)
        decision = self.decision(context)
        audit = audit_date(filename or Path(context.entry.current_path).name, tags, decision)
        return tool, tags, audit

    def preview(self, pipeline):
        # En recuperación, los nombres temporales no sustituyen la identidad original.
        if pipeline.resuming:
            return
        desired = {}
        for entry in pipeline.store.manifest.entries:
            value = pipeline.data["files"][entry.file_id]
            if not value["selected"] or value.get("inventory_failed"):
                continue
            record = value["stages"]["metadata"]
            context = pipeline.context("metadata", entry.file_id, record)
            try:
                _, _, audit = self.analyse(context)
                record["metadata_preview"] = audit
                if audit["target_name"]:
                    desired[entry.file_id] = Path(entry.current_path).with_name(audit["target_name"])
            except (OSError, ValueError, RuntimeError) as exc:
                record["metadata_preview"] = {"state": "WAITING_USER", "error": str(exc)}
        pipeline.data["metadata_name_plan"] = reserve_names(pipeline.store.manifest.entries, desired)

    def instructions(self, context):
        audit = context.record.get("evidence", {}).get("audit") or context.record.get("metadata_preview")
        if audit is None:
            try:
                _, _, audit = self.analyse(context)
            except (OSError, ValueError, RuntimeError) as exc:
                audit = {"state": "WAITING_USER", "error": str(exc)}
        destination = context.pipeline.data.get("metadata_name_plan", {}).get(context.file_id)
        return {"tool": "ExifTool / Attributes / Rename sobre copias por ID", "settings": self.decision(context),
                "expected": "Fechas seleccionadas, campos objetivo y contenido releídos; la confirmación no sustituye validación",
                "audit": audit, "reserved_name": destination}

    def waiting(self, context, code, message):
        return StageResult(State.WAITING_USER, issues=[Issue(code, message, context.entry.current_path, context.file_id)])

    def remember(self, context, audit):
        context.record["metadata_audit"] = audit
        entries = copy.deepcopy(context.store.manifest.entries)
        entry = next(entry for entry in entries if entry.file_id == context.file_id)
        entry.temporal_decision = {"selected": audit["selected"], "policy": audit["decision"],
                                   "comparisons": audit["comparisons"], "historical_prefixes": audit["historical_prefixes"]}
        context.pipeline.save(entries=entries)

    def evidence(self, context, audit, *, applied=False):
        target = Path(context.entry.current_path).with_name(audit["target_name"])
        planned = context.pipeline.data.get("metadata_name_plan", {}).get(context.file_id)
        preview = context.record.get("metadata_preview", {})
        if planned and preview.get("target_name") == audit["target_name"]:
            target = Path(planned)
        return {"audit": audit, "applied": applied, "unchanged": not applied,
                "pending_rename": str(target) if str(target) != context.entry.current_path else None}

    def targets(self, tool, tags, audit, path):
        options = audit["decision"]
        wants_tags = options["policy"] == "filename-to-metadata"
        if wants_tags or options["set_file_modify_date"] or options["set_file_create_date"]:
            targets, attributes = tool.targets(tags, CaptureDate(**audit["selected"]), options, path)
            return targets if wants_tags else {}, attributes
        return {}, {}

    def fields_match(self, tags, targets):
        for key, value in targets.items():
            if str(tags.get(key, "")) != value:
                return False
        return True

    def run(self, context):
        try:
            tool, before, audit = self.analyse(context)
            if audit["problems"]:
                context.record["metadata_audit"] = audit
                return self.waiting(context, "date_decision_required", "; ".join(audit["problems"]))
            self.remember(context, audit)
            targets, attributes = self.targets(tool, before, audit, context.entry.current_path)
            attributes_match = True
            try:
                verify_attributes(context.entry.current_path, attributes)
            except AttributeCapabilityError:
                attributes_match = False
            if self.fields_match(before, targets) and attributes_match:
                return StageResult(State.COMPLETED, evidence=self.evidence(context, audit))
            coded = tool.content(context.entry.current_path, before)
            artifact = None
            for event in reversed(context.store.manifest.events):
                value = event.get("evidence", {})
                validation = value.get("validation", {})
                if event["kind"] == "prepared" and event["sequence"] > context.record["start_sequence"] and value.get("file_id") == context.file_id and validation.get("metadata_decision") == audit["decision"] and validation.get("targets") == targets and validation.get("content") == coded and same_content(value["path"], value["sha256"]):
                    artifact = Artifact(context.file_id, value["path"], value["sha256"], validation)
                    break
            if artifact is None:
                def produce(path):
                    shutil.copy2(context.entry.current_path, path)
                    tool.write(path, before, targets, attributes)
                def validate(path):
                    value = tool.verify(path, before, targets, coded, attributes)
                    value["metadata_decision"] = audit["decision"]
                    return value
                artifact = context.executor.prepare(context.file_id, produce, validate)
            context.record["metadata_artifact"] = asdict(artifact)
            context.pipeline.save()
            operation = context.executor.plan(context.file_id, "replace", artifact=artifact)
            return StageResult(State.COMPLETED, [operation], evidence=self.evidence(context, audit, applied=True))
        except ToolError as exc:
            if exc.result.returncode is None:
                context.record["manual_service_required"] = True
                return self.waiting(context, "metadata_tool_unavailable", str(exc))
            raise
        except (MetadataCapabilityError, AttributeCapabilityError) as exc:
            context.record["manual_service_required"] = True
            return self.waiting(context, "metadata_manual_required", str(exc))

    def validate(self, context):
        try:
            if context.record.get("operations"):
                audit = context.record["metadata_audit"]
                tool = self.driver(context)
                operations = [context.store.manifest.operations[key] for key in context.record["operations"]]
                for op in operations:
                    proof = op.evidence.get("validation", {})
                    if op.kind != "replace" or proof.get("metadata_decision") != self.decision(context):
                        return self.waiting(context, "decision_changed_after_plan", "Las operaciones recuperadas requieren la decisión original o un plan nuevo")
                    source = op.backup if op.backup and Path(op.backup).is_file() else op.source
                    tool.verify(op.candidate, tool.read(source), proof["targets"], proof["content"], proof["file_attributes"])
                return StageResult(State.COMPLETED, operations, evidence=self.evidence(context, audit, applied=True))
            if context.pipeline.mode("metadata") == "auto" and not context.record.get("manual_service_required") and not context.decisions.get("output"):
                return self.run(context)
            if not context.pause:
                return self.run(context)
            tool = self.driver(context)
            temporary, _, _ = entry_paths(context.store.config, context.store.manifest.run_id, context.entry)
            chosen = context.decisions.get("output")
            input_path = Path(context.pause["inputs"][context.file_id])
            output_path = Path(context.pause["outputs"][context.file_id])
            path = Path(chosen) if chosen else output_path if output_path.exists() else input_path
            if not path.exists():
                paths = [candidate for candidate in input_path.parent.iterdir() if candidate.is_file() and not candidate.is_symlink()]
                selection = associate_outputs({context.file_id: context.record["copy_sha256"]}, paths)
                path = Path(selection[context.file_id])
            if path.resolve() != path or not path.is_relative_to(temporary) or path.is_symlink():
                return self.waiting(context, "manual_identity_conflict", "La copia debe pertenecer al directorio de este ID")
            before = tool.read(context.entry.current_path)
            after = tool.read(path)
            name = path.name if parse_name(path.name).date.complete else Path(context.entry.current_path).name
            audit = audit_date(name, after, self.decision(context))
            if audit["problems"]:
                return self.waiting(context, "manual_date_invalid", "; ".join(audit["problems"]))
            targets, attributes = self.targets(tool, after, audit, path)
            if audit["decision"]["policy"] == "review":
                targets, attributes = tool.targets(after, CaptureDate(**audit["selected"]), audit["decision"], path)
            coded = tool.content(context.entry.current_path, before)
            proof = tool.verify(path, before, targets, coded, attributes)
            self.remember(context, audit)
            if fingerprint(path)["sha256"] == fingerprint(context.entry.current_path)["sha256"] and not attributes:
                return StageResult(State.COMPLETED, evidence=self.evidence(context, audit))
            def produce(output):
                shutil.copy2(path, output)
                if attributes:
                    from .file_attributes import apply_attributes
                    apply_attributes(output, attributes, timeout=context.store.config.timeout_seconds)
            def validate(output):
                evidence = tool.verify(output, before, targets, coded, attributes)
                evidence["metadata_decision"] = audit["decision"]
                return evidence
            artifact = context.executor.prepare(context.file_id, produce, validate)
            operation = context.executor.plan(context.file_id, "replace", artifact=artifact)
            return StageResult(State.COMPLETED, [operation], evidence=self.evidence(context, audit, applied=True))
        except (MetadataCapabilityError, AttributeCapabilityError, ConflictError) as exc:
            return self.waiting(context, "manual_validation_failed", str(exc))
        except ToolError as exc:
            return self.waiting(context, "manual_tool_failed", str(exc))

    def finalize(self, pipeline, *, recover_only=False):
        purpose = "metadata:" + pipeline.store.manifest.run_id
        batches = {}
        for event in pipeline.store.manifest.events:
            value = event.get("evidence", {}).get("rename_batch")
            if value and value.get("purpose") == purpose:
                batches[value["batch_id"]] = value
        reconciled = pipeline.data.setdefault("metadata_batches_completed", [])
        active = next((value for key, value in batches.items() if key not in reconciled), None)
        if active is None and not recover_only:
            desired = {key: value["stages"]["metadata"].get("evidence", {}).get("pending_rename")
                       for key, value in pipeline.data["files"].items() if value["selected"] and not value["replan"]
                       and value["stages"]["metadata"]["state"] == "COMPLETED"}
            desired = {key: path for key, path in desired.items() if path}
            if desired:
                active = RenameBatch.create(pipeline.store, desired, purpose=purpose).data
        if active is None or (id(pipeline), active["batch_id"]) in self.attempted:
            return
        self.attempted.add((id(pipeline), active["batch_id"]))
        participants = active.get("destinations", active["moves"])
        for file_id in participants:
            pipeline.data["files"][file_id]["stages"]["metadata"]["batch_pending"] = True
        pipeline.save()
        try:
            result = RenameBatch.load(pipeline.store, active["batch_id"]).execute()
        except (KeyboardInterrupt, PersistenceError):
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            for file_id in participants:
                record = pipeline.data["files"][file_id]["stages"]["metadata"]
                record["state"], record["reason"] = "FAILED", str(exc)
            pipeline.save(state=State.FAILED)
            return
        for file_id in participants:
            value = pipeline.data["files"][file_id]
            if file_id not in result["moves"]:
                from .filesystem import check_fingerprint
                check_fingerprint(pipeline.store.entry(file_id).current_path, value["baseline"])
            record = value["stages"]["metadata"]
            record["state"], record["batch_pending"] = "COMPLETED", False
            record["evidence"]["renamed_to"] = pipeline.store.entry(file_id).current_path
            record["evidence"]["pending_rename"] = None
            value["baseline"] = fingerprint(pipeline.store.entry(file_id).current_path)
        reconciled.append(active["batch_id"])
        pipeline.save()
