"""Backup privado del estado necesario, acreditado por hash sin registrar contenido."""

from pathlib import Path
import os

from .filesystem import ConflictError, check_fingerprint, durable_copy, fingerprint, same_content
from .provenance import digest
from .state import atomic_json


def inventory_state(root):
    root=Path(root)
    if root.resolve()!=root or not root.is_dir():raise ConflictError("Estado uploader ausente o enlazado")
    files=[]
    for base,directories,names in os.walk(root,followlinks=False):
        for name in directories+names:
            if (Path(base)/name).is_symlink():raise ConflictError("Estado uploader contiene enlaces: revisión necesaria")
        for name in sorted(names):
            path=Path(base)/name
            files.append({"relative":path.relative_to(root).as_posix(),"expected":fingerprint(path)})
    return sorted(files,key=lambda f:f["relative"])


def backup_state(pipeline,job,settings):
    if job.get("backup",{}).get("verified"):
        root=Path(job["backup"]["root"])
        for item in job["state_snapshot"]:
            if not same_content(root/"files"/item["relative"],item["expected"]["sha256"]):raise ConflictError("Backup acreditado cambió; entrega no se repite")
        return
    if job.get("backup")=={"enabled":False}:return
    if not settings["state_dir"]:
        job["backup"]={"enabled":False};pipeline.save();return
    source=Path(settings["state_dir"])
    if "state_snapshot" not in job:
        job["state_snapshot"]=inventory_state(source)
        job["backup_root"]=str(Path(settings["backup_dir"])/pipeline.store.manifest.run_id/job["job_id"])
        pipeline.save()
    snapshot=job["state_snapshot"]
    if inventory_state(source)!=snapshot:raise ConflictError("Estado uploader cambió durante su backup; no se repite la entrega")
    root=Path(job["backup_root"])
    if root.resolve()!=root:raise ConflictError("Backup uploader enlazado")
    root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
    for item in snapshot:
        src=source/item["relative"];target=root/"files"/item["relative"]
        check_fingerprint(src,item["expected"])
        if target.exists():
            if not same_content(target,item["expected"]["sha256"]):raise ConflictError("Backup uploader parcial/ajeno: conservar para revisión")
        else:durable_copy(src,target,item["expected"]["sha256"],reserve=pipeline.store.config.reserve_bytes)
        target.chmod(0o600)
        parent=target.parent
        while parent!=root:
            parent.chmod(0o700);parent=parent.parent
    for item in snapshot:
        if not same_content(root/"files"/item["relative"],item["expected"]["sha256"]):raise ConflictError("Backup de estado cambió antes de confirmarlo")
    receipt={"job_id":job["job_id"],"files":len(snapshot),"tree_sha256":digest([{ "relative":i["relative"],"sha256":i["expected"]["sha256"]} for i in snapshot])}
    atomic_json(root/"state-receipt.json",receipt);(root/"state-receipt.json").chmod(0o600)
    job["backup"]={"enabled":True,"verified":True,"root":str(root),**receipt}
    pipeline.save()
