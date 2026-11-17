"""Opt-in CLI con protocolo de alcance; no admite credenciales en argumentos."""

from pathlib import Path
import re

DEFAULTS={"mode":"disabled","allow_cli":False,"executable":None,"args":[],
          "capability_args":["--capabilities"],"auth_args":["--auth-check"],
          "state_dir":None,"backup_dir":None,"require_capture_date":True,"target":"manual"}


def parse_delivery_settings(raw,base):
    if not isinstance(raw,dict) or set(raw)-set(DEFAULTS):raise ValueError("Opciones de delivery desconocidas")
    value={**DEFAULTS,**raw}
    if value["mode"] not in ("disabled","manual","configured-cli"):raise ValueError("Modo delivery inválido")
    if not isinstance(value["target"],str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}",value["target"]):raise ValueError("target requiere un alias no secreto")
    for key in ("allow_cli","require_capture_date"):
        if type(value[key]) is not bool:raise ValueError(f"delivery.{key} requiere true/false")
    for key in ("args","capability_args","auth_args"):
        if not isinstance(value[key],list) or any(not isinstance(a,str) or not a or "\0" in a or re.search(r"^--?[^=]*(token|password|secret|authorization|api.key)",a,re.I) for a in value[key]):
            raise ValueError("Argumentos CLI inválidos o credenciales inline; usar autenticación externa")
        for arg in value[key]:
            for placeholder in re.findall(r"\{([^}]+)\}",arg):
                if placeholder not in ("scope","receipts","state","job"):raise ValueError("Placeholder CLI no admitido")
    executable=value["executable"]
    if executable is not None:
        if not isinstance(executable,str) or not executable or "\0" in executable:raise ValueError("Ejecutable delivery inválido")
        if "/" in executable:value["executable"]=str((base/executable).resolve())
    for key in ("state_dir","backup_dir"):
        if value[key] is not None:
            if not isinstance(value[key],str) or not value[key] or "\0" in value[key]:raise ValueError("Ruta delivery inválida")
            value[key]=str((base/Path(value[key]).expanduser()).resolve())
    if bool(value["state_dir"])!=bool(value["backup_dir"]):raise ValueError("Configurar state_dir y backup_dir juntos")
    if value["mode"]=="configured-cli" and (not value["allow_cli"] or not executable or "target" not in raw or "{scope}" not in value["args"] or not value["auth_args"] or not value["capability_args"]):
        raise ValueError("configured-cli exige opt-in, ejecutable, alcance explícito y preflight de capacidades/autenticación")
    return value
