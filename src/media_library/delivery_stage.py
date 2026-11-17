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
from .provenance import HistoryUnavailable, digest, manifests
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

    def record_decisions(self,context,supplied):
        if "delivery_resolution" not in supplied:return
        job=context.pipeline.data.get("delivery_job")
        if not job or job["state"] not in ("SUBMITTING","UNCERTAIN"):
            raise ValueError("La reconciliación exige un intento de entrega incierto")
        context.record["delivery_authorization"]={"id":uuid.uuid4().hex,"job_id":job["job_id"],
            "attempt":job["attempts"],"resolution":supplied["delivery_resolution"]}

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

    def historical_job(self,context,manifest):
        try:
            job=None
            for event in manifest.events:
                pipeline=event["evidence"].get("pipeline",{})
                if not isinstance(pipeline,dict):raise ValueError("Checkpoint inválido")
                candidate=pipeline.get("delivery_job")
                if candidate is None:continue
                if (not isinstance(candidate,dict) or not isinstance(candidate["job_id"],str)
                    or candidate["state"] not in ("PREPARING","READY","SUBMITTING","UNCERTAIN","COMMAND_SUCCEEDED","DELIVERED")
                    or type(candidate["attempts"]) is not int or candidate["attempts"]<0
                    or type(candidate.get("revision",0)) is not int
                    or not isinstance(candidate["payload_hash"],str)
                    or not isinstance(candidate["delivery_signature"],str)
                    or not isinstance(candidate["scope"]["files"],list)):
                    raise ValueError("Job histórico inválido")
                for item in candidate["scope"]["files"]:
                    if any(not isinstance(item[k],str) for k in ("identity","sha256","recipe_key")):
                        raise ValueError("Alcance histórico inválido")
                if (candidate["scope"]["job_id"]!=candidate["job_id"]
                    or self.payload(candidate["scope"]["files"])!=candidate["payload_hash"]):
                    raise ValueError("Identidad/huella del alcance histórico inválida")
                job=candidate
            return context.pipeline.data.get("delivery_job") if manifest.run_id==context.store.manifest.run_id else job
        except (ValueError,KeyError,TypeError) as exc:
            raise HistoryUnavailable(context.store.config.workspace/manifest.run_id/"manifest.json",exc) from exc

    def historical_settings(self,context,manifest,job):
        """La huella del checkpoint acredita toda la configuración, antes del target."""
        try:
            if "delivery" in manifest.config:
                settings=manifest.config["delivery"]
            else:
                # Contrato antiguo: sin tabla explícita, settings() usaba estos
                # defaults. También deben satisfacer el compromiso persistido.
                mode=manifest.config.get("pipeline",{}).get("modes",{}).get("delivery","disabled")
                settings={**DEFAULTS,"mode":"manual" if mode=="manual" else "disabled"}
            if (not isinstance(settings,dict) or set(settings)!=set(DEFAULTS)
                or not isinstance(settings["target"],str) or digest(settings)!=job["delivery_signature"]):
                raise ValueError("Configuración histórica no acreditada")
            return settings
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            raise HistoryUnavailable(context.store.config.workspace/manifest.run_id/"manifest.json",exc,
                reason="la configuración de entrega no concuerda con la huella persistida del job") from exc

    def prior(self,context,files,settings):
        payload=self.payload(files);identities={(f["identity"],f["sha256"]) for f in files}
        compatible=[]
        active={"SUBMITTING","UNCERTAIN","COMMAND_SUCCEEDED","DELIVERED"}
        for manifest in manifests(context.store,strict=True):
            job=self.historical_job(context,manifest)
            if not job:continue
            old={(f["identity"],f["sha256"]) for f in job["scope"]["files"]}
            if not old.intersection(identities):continue
            # Primero acreditar el alcance; solo una configuración vinculada al
            # job puede probar que su destino es distinto. Nunca usar rutas de
            # cabecera ni un target aislado para descartar un posible envío.
            previous=self.historical_settings(context,manifest,job)
            if previous["target"]!=settings["target"]:continue
            if job["payload_hash"]==payload and job.get("delivery_signature")==digest(settings):
                compatible.append((manifest.run_id,job))
            elif job["state"] in active:
                raise DeliveryPending("Solapamiento con entrega anterior: reconciliarla y elegir un alcance sin duplicados")
        if not compatible:return None
        active_jobs={job["job_id"] for _,job in compatible if job["state"] in active}
        if len(active_jobs)>1:
            raise DeliveryPending("Varios jobs con entrega posible para el mismo alcance: reconciliar antes de continuar")
        job_id=next(iter(active_jobs)) if active_jobs else min(job["job_id"] for _,job in compatible)
        states={"PREPARING":0,"READY":1,"SUBMITTING":2,"UNCERTAIN":3,"COMMAND_SUCCEEDED":4,"DELIVERED":5}
        # Los intentos nunca retroceden. La revisión duradera ordena decisiones
        # dentro del mismo intento; snapshots antiguos sin revisión se comparan
        # conservadoramente por progreso. Nunca ordenar progreso por UUID de run.
        run_id,job=max(((run,job) for run,job in compatible if job["job_id"]==job_id),
            key=lambda item:(item[1]["attempts"],item[1].get("revision",0),states[item[1]["state"]],
                             bool(item[1].get("backup",{}).get("verified"))))
        if run_id==context.store.manifest.run_id:return job
        result=copy.deepcopy(job);result["adopted_from_run"]=run_id;return result

    def job(self,context,files):
        pipeline=context.pipeline;settings=self.settings(context)
        current=pipeline.data.get("delivery_job")
        if current and current["payload_hash"]!=self.payload(files):raise DeliveryPending("Alcance cambió con entrega registrada; reconciliar antes de crear otra")
        job=self.prior(context,files,settings)
        if job is None:
            job_id=uuid.uuid4().hex
            root=context.store.root/"delivery"/job_id
            scope={"protocol":PROTOCOL,"job_id":job_id,"files":[{**item,"path":str(root/"files"/item["relative"]),"source_export":item["path"]} for item in files]}
            job={"job_id":job_id,"scope":scope,"scope_path":str(root/"scope.json"),"receipts_path":str(root/"receipts.json"),
                 "payload_hash":self.payload(files),"delivery_signature":digest(settings),"state":"PREPARING","attempts":0}
        if job!=current:
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
        except (DeliveryPending,HistoryUnavailable):
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
                resolution=context.decisions.get("delivery_resolution")
                authorization=context.record.get("delivery_authorization",{})
                if (not resolution or authorization.get("job_id")!=job["job_id"]
                    or authorization.get("attempt")!=job["attempts"] or authorization.get("resolution")!=resolution
                    or not authorization.get("id") or job.get("resolution_consumed")==authorization["id"]):
                    return self.pending(context,"Resultado remoto incierto; revisar recibos/cliente y declarar delivery_resolution explícitamente para este intento. No se repite automáticamente")
                job["resolution_consumed"]=authorization["id"]
                job["last_resolution"]=copy.deepcopy(authorization)
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
        except (DeliveryPending,HistoryUnavailable) as exc:return self.pending(context,str(exc))
        except DeliveryClientError as exc:
            return StageResult(State.FAILED,issues=[Issue("delivery_preflight",str(exc),file_id=context.file_id)])

    def completed(self,job):
        return StageResult(State.COMPLETED,evidence={"delivery":job["evidence_kind"],"job_id":job["job_id"],
            "command_succeeded":job.get("command_succeeded"),"remote_presence_verified":False,
            "client_receipts":job.get("receipts",[]),"human_confirmation":job["evidence_kind"]!="client_receipts",
            "technical_verification":False,"backup":job.get("backup",{}),"simulated_remote":job.get("client",{}).get("simulated_client",False)})

    run=execute
    validate=execute
