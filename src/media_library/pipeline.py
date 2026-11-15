"""Orquestación persistente sobre RunStore y SafeExecutor, sin motores de medios."""

from dataclasses import asdict
from pathlib import Path
import copy
import fnmatch
import json
import shlex
import sys
import uuid

from .filesystem import ConflictError, check_fingerprint, durable_copy, fingerprint, same_content
from .inventory import entry_paths, inventory
from .models import StageResult, State
from .operations import SafeExecutor
from .pipeline_settings import FILE_STAGES, STAGES, parse_settings
from .stages import StageContext, default_adapters
from .state import PersistenceError, atomic_json

DONE = {"COMPLETED", "DISABLED"}
COPY_STAGES = {"metadata", "normalize", "compression", "export"}


class Console:
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout

    def write(self, message):
        print(message, file=self.stdout, flush=True)

    def ask(self, message):
        self.write(message)
        if not self.stdin.isatty():
            return None
        line = self.stdin.readline()  # Bloqueante; EOF nunca confirma.
        return line.strip() if line else None


class Pipeline:
    def __init__(self, store, *, config_path, dry_run=False, adapters=None, console=None, resume=False):
        self.store, self.executor = store, SafeExecutor(store)
        self.config_path = str(Path(config_path).resolve())
        self.console = console or Console()
        self.adapters = default_adapters()
        self.adapters.update(adapters or {})
        self.settings = parse_settings(store.config.pipeline)
        identities = {stage: {"identity": adapter.identity, "simulated": adapter.simulated, "human": adapter.human}
                      for stage, adapter in self.adapters.items()}
        previous = next((event["evidence"]["pipeline"] for event in reversed(store.manifest.events)
                         if "pipeline" in event.get("evidence", {})), None)
        if resume:
            if not previous or previous.get("version") != 1:
                raise ValueError("Esta ejecución no contiene un pipeline compatible")
            self.data = copy.deepcopy(previous)
            if self.data["dry_run"] != dry_run or self.data["settings"] != self.settings.effective() or self.data["adapters"] != identities:
                raise ValueError("Modo, alcance o adaptadores distintos: crear un plan nuevo")
        else:
            if previous:
                raise ValueError("La ejecución ya tiene pipeline; usar resume")
            self.data = {"version": 1, "settings": self.settings.effective(), "adapters": identities,
                         "dry_run": dry_run, "approved": False, "files": {}, "global_issues": [],
                         "globals": {stage: {"state": "PLANNED"} for stage in ("preflight", "import_review", "inventory", "plan", "close")}}
            self.data["globals"]["preflight"] = {"state": "COMPLETED", "evidence": store.manifest.versions}
        self.resuming = resume
        self.deferred = set()
        self.current = None

    def save(self, *, state=State.RUNNING, entries=None):
        self.store.commit("pipeline_checkpoint", state=state, evidence={"pipeline": self.data}, entries=entries)

    def mode(self, stage):
        return self.settings.modes.get(stage, "auto")

    def context(self, stage, file_id, record):
        return StageContext(self, stage, file_id, record)

    def initialize_inventory(self):
        entries, result = inventory(self.store.config)
        files = {}
        for entry in entries:
            selected = any(fnmatch.fnmatchcase(entry.relative_path, pattern) for pattern in self.settings.include)
            value = {"selected": selected, "reason": "" if selected else "Fuera del alcance seleccionado",
                     "baseline": None, "replan": False, "stages": {}}
            for stage in FILE_STAGES:
                value["stages"][stage] = {"state": "DISABLED" if self.mode(stage) == "disabled" else "PLANNED"}
            if selected:
                if entry.issues:
                    value["reason"] = "; ".join(issue.message for issue in entry.issues)
                    value["inventory_failed"] = True
                else:
                    value["baseline"] = fingerprint(entry.current_path)
                    if {key: value["baseline"][key] for key in entry.stat} != entry.stat:
                        raise ConflictError("Entrada cambiada durante el inventario; crear nuevo plan")
            files[entry.file_id] = value
        self.data["files"] = files
        self.data["global_issues"] = [asdict(issue) for issue in result.issues if issue.file_id is None]
        self.data["globals"]["inventory"] = {"state": "COMPLETED", "evidence": {"entries": len(entries)}}
        self.save(entries=entries)

    def show_plan(self):
        lines = [f"Ejecución: {self.store.manifest.run_id}", f"Simulación: {self.data['dry_run']}"]
        proposals = []
        for stage in STAGES:
            adapter = self.adapters.get(stage)
            detail = f"; {adapter.identity}" if adapter else "; núcleo real"
            if adapter and adapter.simulated:
                detail += "; SIMULADO"
            lines.append(f"- {stage}: {self.mode(stage)}{detail}")
        for entry in self.store.manifest.entries:
            value = self.data["files"][entry.file_id]
            stages = [stage for stage in FILE_STAGES if self.mode(stage) != "disabled"]
            lines.append(f"{entry.file_id} | {entry.current_path} | " + (", ".join(stages) if value["selected"] else value["reason"]))
            if value["selected"]:
                temporary, backup, export = entry_paths(self.store.config, self.store.manifest.run_id, entry)
                for stage in stages:
                    details = self.adapters[stage].instructions(self.context(stage, entry.file_id, value["stages"][stage]))
                    proposal = {"file_id": entry.file_id, "stage": stage, "mode": self.mode(stage),
                                "source": entry.current_path, "working_directory": str(temporary / "manual" / stage),
                                "destination": str(export if stage == "export" else Path(entry.current_path)) if stage in ("installation", "export") else "Candidato por ID; sujeto a validación",
                                "backup": str(backup) if stage == "installation" else None, **details}
                    proposals.append(proposal)
                    lines.append("  " + json.dumps(proposal, ensure_ascii=False))
        lines.append("Los conflictos de fecha requieren fuente/zona explícitas; --apply no los resuelve.")
        self.console.write("\n".join(lines))
        atomic_json(self.store.root / "plan.json", {"run_id": self.store.manifest.run_id, "lines": lines,
                                                  "settings": self.data["settings"], "adapters": self.data["adapters"], "operations": proposals})
        self.data["globals"]["plan"] = {"state": "COMPLETED"}
        self.save()

    def approve(self, apply):
        if self.data["approved"]:
            return True
        if apply:
            self.data["approved"] = True
            self.data["approval_pending"] = False
            self.save()
            return True
        self.data["approval_pending"] = True
        self.save(state=State.WAITING_USER)
        while True:
            answer = self.console.ask("Aprobación única del lote: aprobar / posponer / cancelar")
            if answer is None or answer.casefold() in ("posponer", "cancelar"):
                self.data["approval_reason"] = "Sin entrada/EOF" if answer is None else answer.casefold()
                self.save(state=State.WAITING_USER)
                return False
            if answer.casefold() in ("aprobar", "sí", "si"):
                self.data["approved"], self.data["approval_pending"] = True, False
                self.save()
                return True

    def prepare_pause(self, context):
        record = context.record
        if "pause" not in record:
            instructions = self.adapters[context.stage].instructions(context)
            record["pause"] = {"pause_id": uuid.uuid4().hex, "stage": context.stage,
                               "file_ids": [context.file_id] if context.file_id else [],
                               "inputs": {}, "outputs": {}, "decisions": record.get("decisions", {}),
                               **instructions, "resume_condition": "Revalidar evidencia; una confirmación no basta"}
            record["state"] = "WAITING_USER"
            record["start_sequence"] = self.store.manifest.sequence + 1
            if context.file_id:
                temporary, _, _ = entry_paths(self.store.config, self.store.manifest.run_id, context.entry)
                folder = temporary / "manual" / context.stage
                source = folder / ("input" + Path(context.entry.current_path).suffix)
                output = folder / ("output" + (".mp4" if context.stage in ("normalize", "compression") else Path(context.entry.current_path).suffix))
                if context.stage not in COPY_STAGES:
                    source = Path(context.entry.current_path)
                    if context.stage == "installation":
                        artifact = context.artifact()
                        if artifact:
                            source = Path(artifact.path)
                        output = Path(context.entry.current_path)
                    if context.stage == "delivery":
                        exports = [op for op in self.store.manifest.operations.values() if op.file_id == context.file_id and op.kind == "export" and op.state == "COMPLETED"]
                        if exports:
                            source = Path(exports[-1].destination)
                record["pause"]["inputs"] = {context.file_id: str(source)}
                record["pause"]["outputs"] = {} if context.stage in ("audit", "delivery") else {context.file_id: str(output)}
                if context.stage in COPY_STAGES:
                    record["copy_sha256"] = fingerprint(context.entry.current_path)["sha256"]
            self.save(state=State.WAITING_USER)  # Intención y rutas antes de preparar copias.
        if context.file_id and context.stage in COPY_STAGES:
            path = Path(record["pause"]["inputs"][context.file_id])
            if not record.get("copy_ready"):
                if not path.exists():
                    durable_copy(context.entry.current_path, path, record["copy_sha256"], reserve=self.store.config.reserve_bytes)
                elif not same_content(path, record["copy_sha256"]):
                    raise ConflictError("Copia de trabajo incompleta o cambiada antes de confirmarse")
                record["copy_ready"] = True
                self.save(state=State.WAITING_USER)

    def operation_ids(self, context):
        ids = list(context.record.get("operations", []))
        start = context.record.get("start_sequence", self.store.manifest.sequence)
        for event in self.store.manifest.events:
            if event["kind"] == "operation_planned" and event["sequence"] > start:
                operation = self.store.manifest.operations[event["operation_id"]]
                if operation.file_id == context.file_id and operation.operation_id not in ids:
                    ids.append(operation.operation_id)
        return ids

    def accept(self, context, result):
        if not isinstance(result, StageResult):
            raise ValueError("El adaptador debe devolver StageResult")
        record = context.record
        record["evidence"] = result.evidence
        record["issues"] = [asdict(issue) for issue in result.issues]
        record["operations"] = list(dict.fromkeys([*record.get("operations", []), *[op.operation_id for op in result.operations]]))
        record["ready"] = result.state == State.COMPLETED
        if result.state == State.COMPLETED and not result.evidence:
            raise ValueError("Una etapa completada requiere evidencia")
        if result.state == State.COMPLETED and context.file_id and not record["operations"]:
            value = self.data["files"][context.file_id]
            try:
                check_fingerprint(context.entry.current_path, value["baseline"])
            except (OSError, ConflictError) as exc:
                value["replan"], value["reason"] = True, f"Nuevo plan requerido: {exc}"
                record["state"] = "WAITING_USER"
                self.save(state=State.WAITING_USER)
                return False
        record["state"] = "RUNNING" if result.state == State.COMPLETED and record["operations"] else str(result.state)
        self.save()
        if result.state == State.COMPLETED:
            record.pop("reason", None)
            record["state"] = "COMPLETED" if not record["operations"] else "RUNNING"
            for operation_id in record["operations"]:
                operation = self.store.manifest.operations[operation_id]
                if operation.file_id != context.file_id:
                    raise ConflictError("Operación de otro archivo en el resultado de etapa")
                outcome = self.executor.execute(operation_id)
                if outcome.state != State.COMPLETED:
                    record["state"] = "FAILED"
                    record["issues"] = [asdict(issue) for issue in outcome.issues]
                    break
            else:
                record["state"] = "COMPLETED"
            if context.file_id and record["state"] == "COMPLETED":
                self.data["files"][context.file_id]["baseline"] = fingerprint(context.entry.current_path)
        self.save()
        return record["state"] == "COMPLETED"

    def manual(self, context, *, recheck=True):
        record, adapter = context.record, self.adapters[context.stage]
        previous_pause = "pause" in record
        self.prepare_pause(context)
        if self.resuming and previous_pause and not adapter.human and recheck:
            if self.accept(context, adapter.validate(context)):
                return
            if record["state"] == "FAILED":
                return
            if context.file_id and self.data["files"][context.file_id]["replan"]:
                return
        self.console.write(json.dumps(record["pause"], ensure_ascii=False, indent=2))
        while True:
            record["state"] = "WAITING_USER"
            self.save(state=State.WAITING_USER)
            answer = self.console.ask("comprobar / posponer / cancelar / decidir authority=… timezone=… output=…")
            if answer is None or answer.casefold() in ("posponer", "cancelar"):
                record["reason"] = "Sin terminal/EOF" if answer is None else answer.casefold()
                record["cancelled"] = answer is not None and answer.casefold() == "cancelar"
                self.deferred.add((context.stage, context.file_id))
                self.save(state=State.WAITING_USER)
                return
            try:
                words = shlex.split(answer)
            except ValueError:
                self.console.write("Decisión inválida")
                continue
            if words and words[0] == "decidir":
                decisions = dict(word.split("=", 1) for word in words[1:] if "=" in word)
                if not decisions or any(key not in ("authority", "timezone", "output") or not value for key, value in decisions.items()):
                    self.console.write("Decisión inválida")
                    continue
                record.setdefault("decisions", {}).update(decisions)
                record["pause"]["decisions"] = record["decisions"]
                self.save(state=State.WAITING_USER)
            elif words and words[0].casefold() in ("comprobar", "check"):
                if adapter.human:
                    record["human_confirmed"] = True
                if self.accept(context, adapter.validate(context)):
                    return
                if record["state"] == "FAILED":
                    return
                if context.file_id and self.data["files"][context.file_id]["replan"]:
                    return
                self.console.write("Validación pendiente: " + json.dumps(record.get("issues", []), ensure_ascii=False))

    def check_sources(self):
        for entry in self.store.manifest.entries:
            value = self.data["files"][entry.file_id]
            if not value["selected"] or value.get("inventory_failed"):
                continue
            try:
                operations = [op for op in self.store.manifest.operations.values() if op.file_id == entry.file_id]
                pending = [op for op in operations if op.state not in ("COMPLETED", "RESTORED")]
                if any(self.executor.inspect(op.operation_id).output_matches and "continue" in self.executor.inspect(op.operation_id).actions for op in pending):
                    continue  # La etapa recuperará la publicación antes de comprobar su nueva huella.
                for index, op in enumerate(operations):
                    if op.backup and op.state == "COMPLETED" and not same_content(op.backup, op.expected["sha256"]):
                        raise ConflictError("Backup completado alterado")
                    later = any(other.destination == op.destination and other.state == "COMPLETED" for other in operations[index + 1:])
                    if op.state == "COMPLETED" and not later and not same_content(op.destination, op.output_sha256):
                        raise ConflictError("Salida completada alterada")
                expected = value["baseline"]
                if any(op.kind in ("replace", "rename") and op.state == "COMPLETED" for op in operations):
                    expected = {**entry.stat, "sha256": entry.sha256}
                check_fingerprint(entry.current_path, expected)
            except (OSError, ConflictError) as exc:
                value["replan"], value["reason"] = True, f"Nuevo plan requerido: {exc}"
        self.save()

    def process_file(self, stage, file_id):
        value = self.data["files"][file_id]
        record = value["stages"][stage]
        if record["state"] in DONE or record.get("cancelled"):
            return
        previous = FILE_STAGES[:FILE_STAGES.index(stage)]
        if any(value["stages"][earlier]["state"] not in DONE for earlier in previous):
            return
        context = self.context(stage, file_id, record)
        self.current = (stage, file_id)
        try:
            ids = self.operation_ids(context) if "start_sequence" in record else []
            if ids:
                record["operations"] = ids
                if record.get("ready"):
                    self.accept(context, StageResult(State.COMPLETED,
                                [self.store.manifest.operations[key] for key in ids],
                                evidence=record.get("evidence") or {"recovered_operations": ids}))
                else:
                    self.accept(context, self.adapters[stage].validate(context))
                    if record["state"] == "WAITING_USER":
                        self.manual(context, recheck=False)
                return
            if self.mode(stage) == "manual" or "pause" in record:
                self.manual(context)
            else:
                record["state"] = "RUNNING"
                record["start_sequence"] = self.store.manifest.sequence + 1
                self.save()
                result = self.adapters[stage].run(context)
                if not self.accept(context, result) and result.state == State.WAITING_USER:
                    self.manual(context)
        except PersistenceError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            record["state"], record["reason"] = "FAILED", str(exc)
            self.save(state=State.FAILED)

    def pending(self):
        result = []
        if not self.data["approved"] and self.data["globals"]["plan"]["state"] == "COMPLETED":
            result.append({"stage": "approval", "reason": self.data.get("approval_reason", "Aprobación pendiente")})
        if self.data["globals"]["import_review"]["state"] not in DONE:
            result.append({"stage": "import_review", "reason": self.data["globals"]["import_review"].get("reason", "Revisión humana pendiente")})
        for file_id, value in self.data["files"].items():
            if not value["selected"]:
                continue
            if value["replan"] or value.get("inventory_failed"):
                result.append({"file_id": file_id, "reason": value["reason"]})
            else:
                for stage, record in value["stages"].items():
                    if record["state"] not in DONE:
                        result.append({"file_id": file_id, "stage": stage, "state": record["state"],
                                       "reason": record.get("reason") or record.get("issues") or "Etapa pendiente"})
        return result

    def finish(self, override=None):
        failed = bool(self.data["global_issues"]) or any(record["state"] == "FAILED" for stage, record in self.data["globals"].items() if stage != "close") or any(value.get("inventory_failed") or any(record["state"] == "FAILED" for record in value["stages"].values())
                      for value in self.data["files"].values() if value["selected"])
        pending = self.pending()
        for op in self.store.manifest.operations.values():
            if op.state not in ("COMPLETED", "RESTORED"):
                pending.append({"file_id": op.file_id, "operation_id": op.operation_id, "state": op.state})
        code = override if override is not None else (3 if failed else 2 if pending else 0)
        state = State.COMPLETED if code == 0 else State.FAILED if code == 3 else State.WAITING_USER
        self.data["globals"]["close"] = {"state": str(state)}
        self.data["exit_code"] = code
        if not self.store.poisoned:
            self.save(state=State.PLANNED if self.data["dry_run"] and code != 3 else state)
        from .reports import write_report
        report = write_report(self, code, pending)
        for stage in report["stages"]:
            label = " (SIMULADO)" if stage["adapter"].get("simulated") else ""
            self.console.write(f"{stage['stage']} [{stage['mode']}]{label}: {json.dumps(stage['results'])}")
        self.console.write(f"Cambiados: {len(report['changed'])}; conservados: {len(report['unchanged'])}; "
                           f"omitidos: {len(report['omitted'])}; pendientes: {len(pending)}; fallos: {len(report['failures'])}")
        self.console.write("Entrega: " + report["remote_delivery"])
        self.console.write(f"Estado: {state}; código {code}. Informe: {self.store.root / 'report.json'}")
        self.console.write("Siguiente orden: " + report["resume_command"])
        return code

    def run(self, *, apply=False):
        try:
            self.data.pop("fatal_error", None)
            self.data.pop("interrupted", None)
            self.save()
            review = self.data["globals"]["import_review"]
            if self.mode("import_review") == "disabled":
                review["state"] = "DISABLED"
            elif review["state"] not in DONE and not self.data["dry_run"]:
                self.current = ("import_review", "")
                self.manual(self.context("import_review", "", review))
                if review["state"] not in DONE:
                    return self.finish()
            if self.data["globals"]["inventory"]["state"] != "COMPLETED":
                self.initialize_inventory()
            self.show_plan()
            if self.data["dry_run"]:
                return self.finish()
            if not self.approve(apply):
                return self.finish()
            self.check_sources()
            for stage in FILE_STAGES:
                for file_id, value in self.data["files"].items():
                    if value["selected"] and not value["replan"] and not value.get("inventory_failed"):
                        self.process_file(stage, file_id)
            return self.finish()
        except KeyboardInterrupt:
            self.data["interrupted"] = {"at": self.current, "reason": "Ctrl+C o señal de interrupción"}
            return self.finish(130)
        except (OSError, ValueError, RuntimeError) as exc:
            self.data["fatal_error"] = str(exc)
            return self.finish(3)
