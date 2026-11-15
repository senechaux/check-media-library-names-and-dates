"""Transporte configurado. Nunca persistir stdout/stderr del cliente ni tokens."""

from pathlib import Path
import json
import re

from .filesystem import regular_reader
from .process import run_tool

PROTOCOL="media-library-delivery-v1"


class DeliveryClientError(RuntimeError):
    pass


class DeliveryClient:
    def __init__(self,settings,*,timeout=60,runner=None):
        self.settings,self.timeout,self.runner=settings,timeout,runner or run_tool

    def call(self,args,values):
        command=[self.settings["executable"],*[arg.format_map(values) for arg in args]]
        return self.runner(command,timeout=self.timeout)

    def preflight(self,values):
        caps=self.call(self.settings["capability_args"],values)
        try:
            capabilities=json.loads(caps.stdout) if caps.ok else {}
            valid=(capabilities.get("protocol")==PROTOCOL and capabilities.get("scope")=="manifest-only"
                   and re.fullmatch(r"v?\d+\.\d+(?:\.\d+)?",capabilities.get("version","")))
        except (ValueError,TypeError,AttributeError):valid=False
        if valid:
            auth=self.call(self.settings["auth_args"],values)
            try:
                authenticated=json.loads(auth.stdout) if auth.ok else {}
                valid=(authenticated.get("authenticated") is True and authenticated.get("scope_limited") is True
                       and authenticated.get("target")==self.settings["target"])
            except (ValueError,TypeError,AttributeError):valid=False
        if not valid:raise DeliveryClientError("Preflight CLI no acredita protocolo, alcance y autenticación; usar modo manual")
        return {"protocol":PROTOCOL,"version":capabilities["version"],"scope":"manifest-only",
                "authentication":"reported_by_client","simulated_client":capabilities.get("simulated") is True}

    def submit(self,values):
        result=self.call(self.settings["args"],values)
        return {"command_succeeded":result.ok,"returncode":result.returncode,"timed_out":result.timed_out}


def read_receipts(path,scope):
    """Comprobantes del cliente ligados a job/ID/hash; no prueba API independiente."""
    path=Path(path)
    if not path.exists():return None
    try:
        with regular_reader(path) as handle:
            data=json.loads(handle.read(8*1024*1024+1))
        if not isinstance(data,dict) or data.get("protocol")!=PROTOCOL or data.get("job_id")!=scope["job_id"]:return None
        expected={f["file_id"]:f["sha256"] for f in scope["files"]}
        receipts=data["receipts"]
        if not isinstance(receipts,list) or len(receipts)!=len(expected):return None
        seen=set();result=[]
        for item in receipts:
            file_id=item["file_id"];remote_id=item["remote_id"]
            if file_id in seen or expected.get(file_id)!=item["sha256"] or not isinstance(remote_id,str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}",remote_id):return None
            if set(item)-{"file_id","sha256","remote_id"}:return None
            seen.add(file_id);result.append({"file_id":file_id,"sha256":item["sha256"],"remote_id":remote_id})
        return result
    except (OSError,ValueError,KeyError,TypeError):return None
