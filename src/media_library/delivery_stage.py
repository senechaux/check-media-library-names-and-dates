"""Entrega optativa sobre un alcance auditado; incertidumbre nunca equivale a reintento."""

from pathlib import Path
import copy
import json
import uuid

from .delivery_backup import backup_state
from .delivery_client import DeliveryClient, DeliveryClientError, PROTOCOL, read_receipts
from .delivery_settings import DEFAULTS
from .export_stage import ExportAdapter
from .filesystem import ConflictError, durable_copy, same_content
from .models import Issue, StageResult, State
from .provenance import digest, manifests
from .stages import Adapter
from .state import atomic_json


class DeliveryPending(ValueError):
    pass


class DeliveryAdapter(Adapter):
    identity="verified-delivery:v1"

    def settings(self,context):
        config=context.store.config
        if config.delivery:return config.delivery
        mode="manual" if context.pipeline.mode("delivery")=="manual" else "disabled"
        return {**DEFAULTS,"mode":mode}

    def validate_decisions(self,context,decisions):
        if set(decisions)-{"delivery_confirmed","delivery_resolution"}:raise ValueError("Decisión de entrega desconocida")
        if decisions.get("delivery_confirmed","false") not in ("true","false"):raise ValueError("delivery_confirmed requiere true/false")
        if decisions.get("delivery_resolution","delivered") not in ("delivered","not-delivered"):raise ValueError("Resolución de entrega inválida")

    def coverage(self,context):
        coverage=context.pipeline.data.get("coverage",{})
        if not coverage.get("local_complete"):
            raise DeliveryPending("Auditoría de todo el alcance pendiente: no iniciar entrega parcial")
        files=coverage["exported"]
        if self.settings(context)["require_capture_date"] and any(not f["date_known"] for f in files):
            raise DeliveryPending("Hay fechas requeridas sin resolver antes de entregar")
        for item in files:
            value=context.pipeline.data["files"][item["file_id"]]
            record=value["stages"]["export"];exported=record["evidence"]["export"]
            if value["replan"] or not same_content(item["path"],item["sha256"]):raise DeliveryPending("Derivado auditado cambió antes de entregar")
            ExportAdapter().validate_derivative(context.pipeline.context("export",item["file_id"],record),item["path"],exported["validation"])
        return files

    def payload(self,files):
        return digest(sorted(({"identity":f["identity"],"sha256":f["sha256"],"recipe_key":f["recipe_key"]} for f in files),key=lambda f:f["identity"]))

    def prior(self,context,files,settings):
        payload=self.payload(files);identities={(f["identity"],f["sha256"]) for f in files}
        for manifest in manifests(context.store):
            if manifest.run_id==context.store.manifest.run_id:continue
            job=next((e["evidence"]["pipeline"].get("delivery_job") for e in reversed(manifest.events) if e.get("evidence",{}).get("pipeline",{}).get("delivery_job")),None)
            previous_target=manifest.config.get("delivery",{}).get("target","manual")
            if not job or previous_target!=settings["target"]:continue
            old={(f["identity"],f["sha256"]) for f in job["scope"]["files"]}
            if not old.intersection(identities):continue
            if job["payload_hash"]==payload and job.get("delivery_signature")==digest(settings):
                result=copy.deepcopy(job);result["adopted_from_run"]=manifest.run_id;return result
            if job["state"] in ("SUBMITTING","UNCERTAIN","COMMAND_SUCCEEDED","DELIVERED"):
                raise DeliveryPending("Solapamiento con entrega anterior: reconciliarla y elegir un alcance sin duplicados")
        return None

    def job(self,context,files):
        pipeline=context.pipeline;settings=self.settings(context)
        job=pipeline.data.get("delivery_job")
        if job:
            if job["payload_hash"]!=self.payload(files):raise DeliveryPending("Alcance cambió con entrega registrada; reconciliar antes de crear otra")
            return job
        job=self.prior(context,files,settings)
        if job is None:
            job_id=uuid.uuid4().hex
            root=context.store.root/"delivery"/job_id
            scope={"protocol":PROTOCOL,"job_id":job_id,"files":[{**item,"path":str(root/"files"/item["relative"]),"source_export":item["path"]} for item in files]}
            job={"job_id":job_id,"scope":scope,"scope_path":str(root/"scope.json"),"receipts_path":str(root/"receipts.json"),
                 "payload_hash":self.payload(files),"delivery_signature":digest(settings),"state":"PREPARING","attempts":0}
        pipeline.data["delivery_job"]=job;pipeline.save()
        return job

    def prepare(self,context,job):
        root=Path(job["scope_path"]).parent
        if root.resolve()!=root:raise ConflictError("Directorio de entrega enlazado")
        root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
        for item in job["scope"]["files"]:
            path=Path(item["path"])
            if path.resolve()!=path or not path.is_relative_to(root/"files"):raise ConflictError("Salida de alcance fuera de su directorio")
            if path.exists():
                if not same_content(path,item["sha256"]):raise ConflictError("Copia de entrega cambiada; no cargar")
            else:durable_copy(item["source_export"],path,item["sha256"],reserve=context.store.config.reserve_bytes)
        scope_path=Path(job["scope_path"])
        if scope_path.exists():
            if scope_path.is_symlink() or json.loads(scope_path.read_text())!=job["scope"]:raise ConflictError("Manifiesto de alcance cambiado")
        else:atomic_json(scope_path,job["scope"])
        if job["state"]=="PREPARING":job["state"]="READY";context.pipeline.save()

    def instructions(self,context):
        job=context.pipeline.data.get("delivery_job")
        exported=context.pipeline.data["files"][context.file_id]["stages"]["export"].get("evidence",{}).get("export",{})
        return {"tool":"Entrega manual / CLI de alcance explícito", "mode":self.settings(context)["mode"],
                "input_source":job["scope_path"] if job else exported.get("path",str(context.store.config.export)),
                "scope":job["scope_path"] if job else "Pendiente de auditoría global",
                "expected":"Solo medios de scope.json. Declarar delivery_confirmed=true tras entrega manual; incertidumbre requiere reconciliación. Cero del comando no prueba presencia remota."}

    def prepare_manual(self,context):
        if context.pipeline.data.get("delivery_job",{}).get("state")=="DELIVERED":return
        try:
            files=self.coverage(context)
            if not files:return
            job=self.job(context,files)
            self.prepare(context,job)
        except DeliveryPending:
            return

    def pending(self,context,message):
        return StageResult(State.WAITING_USER,issues=[Issue("delivery_pending",message,file_id=context.file_id)])

    def execute(self,context):
        settings=self.settings(context)
        if settings["mode"]=="disabled":
            return StageResult(State.COMPLETED,evidence={"unchanged":True,"delivery":"disabled","local_only":True})
        try:
            registered=context.pipeline.data.get("delivery_job")
            if registered and registered["state"]=="DELIVERED":
                backup_state(context.pipeline,registered,settings)
                coverage=context.pipeline.data.get("coverage",{})
                if coverage.get("local_complete") and self.payload(coverage["exported"])!=registered["payload_hash"]:
                    raise DeliveryPending("Entrega acreditada pertenece a otro alcance; no se atribuye a derivados nuevos")
                return self.completed(registered)
            files=self.coverage(context)
            if not files:return StageResult(State.COMPLETED,evidence={"unchanged":True,"delivery":"empty-scope","local_only":True})
            job=self.job(context,files)
            self.prepare(context,job)
            if job["state"]=="DELIVERED":
                backup_state(context.pipeline,job,settings)
                return self.completed(job)
            receipts=read_receipts(job["receipts_path"],job["scope"])
            if receipts:
                job.update(state="DELIVERED",evidence_kind="client_receipts",receipts=receipts,remote_presence_verified=False)
                context.pipeline.save()
                backup_state(context.pipeline,job,settings)
                return self.completed(job)
            if settings["mode"]=="manual":
                if context.decisions.get("delivery_confirmed")!="true":return self.pending(context,"Entrega manual pendiente de declaración explícita")
                job.update(state="DELIVERED",evidence_kind="human_declaration",remote_presence_verified=False)
            elif job["state"]=="COMMAND_SUCCEEDED":
                if context.decisions.get("delivery_confirmed")!="true":return self.pending(context,"Comando terminó con cero sin recibos por archivo; falta declaración humana")
                job.update(state="DELIVERED",evidence_kind="command_and_human_declaration",remote_presence_verified=False)
            elif job["state"] in ("SUBMITTING","UNCERTAIN"):
                job["state"]="UNCERTAIN";context.pipeline.save()
                revision=[context.file_id,context.record.get("decision_revision",0)]
                resolution=context.decisions.get("delivery_resolution")
                if not resolution or job.get("resolution_consumed")==revision:
                    return self.pending(context,"Resultado remoto incierto; revisar recibos/cliente. No se repite automáticamente")
                job["resolution_consumed"]=revision
                if resolution=="delivered":
                    job.update(state="DELIVERED",evidence_kind="human_reconciliation",remote_presence_verified=False)
                else:
                    job["state"]="READY"
                context.pipeline.save()
            if job["state"]=="READY" and settings["mode"]=="configured-cli":
                if not settings["allow_cli"]:raise DeliveryPending("Falta opt-in CLI")
                client=DeliveryClient(settings,timeout=context.store.config.timeout_seconds)
                values={"scope":job["scope_path"],"receipts":job["receipts_path"],"state":settings["state_dir"] or "","job":job["job_id"]}
                job["client"]=client.preflight(values)
                self.prepare(context,job)  # Reacreditar copias después del preflight.
                job["attempts"]+=1;job["state"]="SUBMITTING";context.pipeline.save()  # Intención duradera ANTES de invocar.
                job.update(client.submit(values))
                job["state"]="COMMAND_SUCCEEDED" if job["command_succeeded"] else "UNCERTAIN"
                context.pipeline.save()
                return self.execute(context)  # Solo reconcilia el resultado, no repite submit.
            if job["state"]=="DELIVERED":
                context.pipeline.save()  # Acreditar entrega ANTES del backup.
                backup_state(context.pipeline,job,settings)
                return self.completed(job)
            return self.pending(context,"Entrega pendiente")
        except DeliveryPending as exc:return self.pending(context,str(exc))
        except DeliveryClientError as exc:
            return StageResult(State.FAILED,issues=[Issue("delivery_preflight",str(exc),file_id=context.file_id)])

    def completed(self,job):
        return StageResult(State.COMPLETED,evidence={"delivery":job["evidence_kind"],"job_id":job["job_id"],
            "command_succeeded":job.get("command_succeeded"),"remote_presence_verified":False,
            "client_receipts":job.get("receipts",[]),"human_confirmation":job["evidence_kind"]!="client_receipts",
            "technical_verification":False,"backup":job.get("backup",{}),"simulated_remote":job.get("client",{}).get("simulated_client",False)})

    run=execute
    validate=execute
