"""Derivados por receta, revalidación de vigencia y auditoría de cobertura."""

from dataclasses import asdict
from pathlib import Path
import copy

from .date_audit import audit_date
from .date_settings import effective_decision
from .export_settings import parse_export_settings
from .filesystem import ConflictError, check_fingerprint, durable_copy, fingerprint, same_content
from .image_export import ImagePolicyError, inspect_image, render_image, validate_image
from .models import Issue, StageResult, State
from .operations import Artifact
from .provenance import best_source, digest, export_history
from .stages import Adapter
from .video_driver import VideoDriver
from .video_plan import plan_video, ratio, VideoPolicyError
from .video_settings import parse_video_settings


class ExportPolicyError(ValueError):
    pass


class ExportAdapter(Adapter):
    identity = "verified-export:v1"
    handles_export_repair = True

    def settings(self, context):
        return parse_export_settings(context.store.config.export_settings)

    def validate_decisions(self, context, decisions):
        values = {k:v for k,v in decisions.items() if k != "export_quality_reviewed"}
        if decisions.get("export_quality_reviewed", "false") not in ("true", "false"):
            raise ValueError("export_quality_reviewed requiere true/false")
        effective_decision(context.store.config.dates, context.entry.relative_path, values)

    def excluded(self, context):
        settings = self.settings(context)
        return ((context.entry.classification == "image" and not settings["images"]) or
                (context.entry.classification == "video" and not settings["videos"]))

    def analyse(self, context):
        settings = self.settings(context)
        source = best_source(context.store, context.entry, use_archive=settings["use_archived_original"])
        driver = VideoDriver(context.store.config)
        supplied = {k:v for k,v in context.decisions.items() if k not in ("export_quality_reviewed","output")}
        decision = effective_decision(context.store.config.dates, context.entry.relative_path, supplied)
        temporal = context.entry.temporal_decision
        selected = temporal.get("selected") if temporal and not supplied else None
        if selected:
            decision = temporal["policy"]
        else:
            audit = audit_date(Path(context.entry.current_path).name, driver.dates.read(context.entry.current_path), decision)
            selected = audit["selected"] if not audit["problems"] else None
        if not selected and settings["require_capture_date"]:
            raise ExportPolicyError("Fecha requerida sin resolver: elegir autoridad, fecha y zona explícitas")
        relative = Path(context.entry.current_path).relative_to(context.store.config.source)
        recipe = {"version": 1, "source": source, "date": selected, "date_options": decision,
                  "settings": {k:v for k,v in settings.items() if k != "video_quality_reviewed"},
                  "kind": context.entry.classification}
        if context.entry.classification == "image":
            recipe["image"] = inspect_image(source["path"], settings["image_max_side"])
            recipe["versions"] = {**recipe["image"]["versions"], **driver.capabilities({"action":"copy"})}
            relative = relative.with_suffix(".jpg")
        elif context.entry.classification == "video":
            video_settings = parse_video_settings({**context.store.config.video, "min_bytes":0,
                "profile":settings["video_profile"], "quality":settings["video_quality"],
                "frame_rate_mode":settings["video_frame_rate_mode"], "historical_policy":"process"})
            plan = plan_video(source["path"], Path(source["path"]).stat().st_size, driver.inspect(source["path"]), video_settings)
            info, g = plan["info"], plan["geometry"]
            compatible = (info["mp4"] and info["video_codec"]=="h264" and info["rotation"]==0 and info["sar"]=="1"
                and (info["width"],info["height"])==(g["width"],g["height"]) and ratio(info["peak_fps"])<=30
                and all(a["codec"]=="aac" for a in info["audio"])
                and (video_settings["frame_rate_mode"]=="pfr" or ratio(info["fps"])==ratio(info["peak_fps"])==30))
            plan.update(action="copy" if compatible else "encode", require_savings=False, stage="export")
            recipe["video_plan"] = plan
            recipe["versions"] = driver.capabilities(plan)
            relative = relative.with_suffix(".mp4")
        else:
            raise ExportPolicyError("Formato no habilitado para derivados")
        recipe["relative"] = relative.as_posix()
        # El ID de inventario cambia entre ejecuciones; la identidad lógica
        # registrada y las huellas sí pertenecen a la receta.
        canonical_source={k:v for k,v in source.items() if k!="origin_file_id"}
        recipe["key"] = digest({**recipe,"source":canonical_source})
        return recipe

    def instructions(self, context):
        try:
            if self.excluded(context):
                return {"tool":"Exportador real", "expected":"Tipo excluido explícitamente por configuración"}
            recipe = self.analyse(context)
            return {"tool":"Pillow / HandBrake / FFmpeg / ExifTool", "recipe":recipe,
                    "input_source":recipe["source"]["path"], "output_suffix":".jpg" if recipe["kind"]=="image" else ".mp4",
                    "destination":str(context.store.config.export/recipe["relative"]),
                    "expected":"Receta/huellas, legibilidad, orientación, dimensiones, color y fechas; revisión visual de vídeo separada"}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"tool":"Exportador real", "expected":str(exc)}

    def validate_derivative(self, context, path, validation):
        recipe = validation["export_recipe"]
        if not same_content(recipe["source"]["path"], recipe["source"]["sha256"]):
            raise ConflictError("Fuente de receta cambiada/ausente")
        driver = VideoDriver(context.store.config)
        dates = validation.get("dates", {})
        if recipe["date"]:
            current = driver.dates.read(path)
            driver.dates.verify(path, current, dates["targets"], dates["content"], dates.get("file_attributes"))
        elif self.settings(context)["require_capture_date"]:
            raise ExportPolicyError("Fecha requerida sin resolver")
        if recipe["kind"] == "image":
            return validate_image(path, recipe["image"])
        return driver.validate(recipe["source"]["path"], path, recipe["video_plan"], dates)

    def evidence(self, recipe, path, sha, validation, **extra):
        return {"export": {"recipe":recipe, "path":str(path), "sha256":sha, "validation":validation, **extra}}

    def execute(self, context, *, manual=False):
        if self.excluded(context):
            return StageResult(State.COMPLETED, evidence={"unchanged":True,"export_excluded":"Tipo deshabilitado explícitamente"})
        try:
            recipe = self.analyse(context)
            destination = context.store.config.export / recipe["relative"]
            operations = [context.store.manifest.operations[key] for key in context.record.get("operations", [])]
            if operations:
                operation = operations[-1]
                validation = operation.evidence["validation"]
                if validation["export_recipe"]["key"] != recipe["key"]:
                    raise ConflictError("Receta cambió con una publicación pendiente: crear un plan nuevo")
                path = operation.destination if same_content(operation.destination, operation.output_sha256) else operation.candidate
                self.validate_derivative(context, path, validation)
                return StageResult(State.COMPLETED,operations,evidence=self.evidence(recipe,operation.destination,operation.output_sha256,validation))
            previous = export_history(context.store,destination,recipe["source"]["identity"])
            if destination.exists() or destination.is_symlink():
                if not previous:
                    raise ExportPolicyError("Destino ajeno al manifiesto; no sobrescribir ni considerar válido por existir")
                manifest, old, validation_recipe = previous
                if validation_recipe["key"] == recipe["key"] and same_content(destination,old.output_sha256):
                    try:
                        self.validate_derivative(context,destination,old.evidence["validation"])
                    except (OSError, ValueError, RuntimeError):
                        pass  # Propio inválido: conservar antes de renovar, nunca omitirlo.
                    else:
                        return StageResult(State.COMPLETED,evidence=self.evidence(recipe,destination,old.output_sha256,old.evidence["validation"],
                            reused=True,origin_run_id=manifest.run_id,origin_operation_id=old.operation_id))
            artifact = None
            for event in reversed(context.store.manifest.events):
                value=event.get("evidence",{})
                if event["kind"]=="prepared" and value.get("file_id")==context.file_id and value.get("validation",{}).get("export_recipe",{}).get("key")==recipe["key"]:
                    if not same_content(value["path"],value["sha256"]):
                        raise ConflictError("Candidato de exportación acreditado cambiado; no repetir automáticamente")
                    artifact=Artifact(context.file_id,value["path"],value["sha256"],value["validation"])
                    break
            if artifact is None:
                driver=VideoDriver(context.store.config)
                source=recipe["source"]["path"]
                source_expected=fingerprint(source)
                tags=driver.dates.read(source)
                dates={}
                manual_path=None
                if manual:
                    manual_path=Path(context.decisions.get("output") or context.pause.get("outputs",{}).get(context.file_id,""))
                    root=context.store.config.workspace/context.store.manifest.run_id/context.file_id/"manual"/"export"
                    if not manual_path.is_absolute() or manual_path.resolve()!=manual_path or not manual_path.is_relative_to(root):
                        raise ExportPolicyError("Salida manual fuera del directorio propio por ID")
                    if not manual_path.is_file():
                        raise ExportPolicyError("Falta derivado manual: confirmar no valida una salida ausente")
                def produce(path):
                    check_fingerprint(source,source_expected)
                    if manual_path:
                        durable_copy(manual_path,path,fingerprint(manual_path)["sha256"],reserve=context.store.config.reserve_bytes)
                    elif recipe["kind"]=="image":
                        render_image(source,path,self.settings(context))
                    elif recipe["video_plan"]["action"]=="copy":
                        durable_copy(source,path,recipe["source"]["sha256"],reserve=context.store.config.reserve_bytes)
                    else:
                        preset=path.parent/(path.name+".preset.json")
                        driver.write_preset(preset,recipe["video_plan"])
                        commands=driver.produce(source,path,recipe["video_plan"],preset)
                        context.store.commit("export_encode_intent",evidence={"file_id":context.file_id,"recipe_key":recipe["key"],"commands":commands})
                        for command in commands:driver.call(command)
                    if recipe["date"]:
                        dates.update(driver.restore_dates(path,recipe["date"],recipe["date_options"],tags))
                    check_fingerprint(source,source_expected)
                def validate(path):
                    validation={"export_recipe":recipe,"dates":dates,"file_attributes":dates.get("file_attributes",{})}
                    validation["technical"]=self.validate_derivative(context,path,validation)
                    return validation
                artifact=context.executor.prepare(context.file_id,produce,validate)
            if recipe["kind"]=="video" and recipe["video_plan"]["action"]=="encode":
                reviewed=context.decisions.get("export_quality_reviewed",str(self.settings(context)["video_quality_reviewed"]).lower())=="true"
                if not reviewed:
                    return StageResult(State.WAITING_USER,issues=[Issue("export_quality_review_pending","Revisar visualmente perfil de carga y declarar export_quality_reviewed=true",file_id=context.file_id)],
                                       evidence={"candidate":artifact.path,"technical_validation":True,"visual_review":"pending_human"})
            previous_fingerprint=fingerprint(destination) if previous and destination.exists() else None
            operation=context.executor.plan(context.file_id,"export",artifact=artifact,destination=destination,previous_destination=previous_fingerprint)
            return StageResult(State.COMPLETED,[operation],evidence=self.evidence(recipe,destination,artifact.sha256,artifact.evidence,reused=False))
        except (ExportPolicyError,ImagePolicyError,VideoPolicyError) as exc:
            return StageResult(State.WAITING_USER,issues=[Issue("export_policy",str(exc),context.entry.current_path,context.file_id)])

    def run(self,context):
        return self.execute(context)

    def validate(self,context):
        return self.execute(context,manual=context.pipeline.mode("export")=="manual")

    def revalidate_completed(self,pipeline):
        for file_id,value in pipeline.data["files"].items():
            record=value["stages"]["export"]
            exported=record.get("evidence",{}).get("export")
            if record["state"]!="COMPLETED" or not exported:
                continue
            try:
                if not same_content(exported["path"],exported["sha256"]):
                    raise ConflictError("Derivado cambiado/ausente")
                self.validate_derivative(pipeline.context("export",file_id,record),exported["path"],exported["validation"])
            except (OSError,ValueError,RuntimeError):
                for stage in ("export","audit","delivery"):
                    old=value["stages"][stage]
                    if old["state"]!="DISABLED":
                        value["stages"][stage]={"state":"PLANNED","decisions":copy.deepcopy(old.get("decisions",{})),
                            "decision_revision":old.get("decision_revision",0),"start_sequence":pipeline.store.manifest.sequence+1}
        pipeline.save()


class AuditAdapter(Adapter):
    identity="verified-audit:v1"

    def instructions(self,context):
        return {"tool":"Auditor local real","expected":"Vigencia por receta/huellas, cobertura y pendientes antes de entregar"}

    def run(self,context):
        record=context.pipeline.data["files"][context.file_id]["stages"]["export"]
        if record.get("evidence",{}).get("export_excluded"):
            return StageResult(State.COMPLETED,evidence={"excluded":record["evidence"]["export_excluded"]})
        exported=record.get("evidence",{}).get("export")
        if not exported or not same_content(exported["path"],exported["sha256"]):
            return StageResult(State.WAITING_USER,issues=[Issue("export_missing_or_changed","Falta derivado vigente acreditado",file_id=context.file_id)])
        ExportAdapter().validate_derivative(context,exported["path"],exported["validation"])
        return StageResult(State.COMPLETED,evidence={"local_validation":True,"recipe_key":exported["recipe"]["key"],"sha256":exported["sha256"]})

    validate=run

    def finalize(self,pipeline):
        exported,excluded,pending=[],[],[]
        for file_id,value in pipeline.data["files"].items():
            record=value["stages"]["export"]
            output=record.get("evidence",{}).get("export")
            if not value["selected"]:
                excluded.append({"file_id":file_id,"reason":value["reason"]})
            elif record.get("evidence",{}).get("export_excluded"):
                excluded.append({"file_id":file_id,"reason":record["evidence"]["export_excluded"]})
            elif (not value["replan"] and not value.get("inventory_failed") and value["stages"]["audit"]["state"]=="COMPLETED" and output):
                exported.append({"file_id":file_id,"identity":output["recipe"]["source"]["identity"],"relative":output["recipe"]["relative"],
                                 "path":output["path"],"sha256":output["sha256"],"recipe_key":output["recipe"]["key"],"date_known":bool(output["recipe"]["date"])})
            else:
                pending.append({"file_id":file_id,"reason":value.get("reason") or "Archivo elegible sin exportación/auditoría completa"})
        pending.extend(pipeline.data["global_issues"])
        pipeline.data["coverage"]={"local_complete":not pending,"exported":exported,"excluded":excluded,"pending":pending,
                                   "scope_hash":digest(exported)}
        pipeline.save()
