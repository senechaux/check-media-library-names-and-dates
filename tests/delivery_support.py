"""Cliente local simulado: jamás abre sockets ni usa credenciales/cuentas reales."""

from pathlib import Path
import json
import sys

from media_library.delivery_client import PROTOCOL

FAKE_SECRET="SYNTHETIC_CREDENTIAL_MUST_NOT_APPEAR_IN_LOGS"


def write_client(path):
    path.write_text('''import sys,json,hashlib
from pathlib import Path
protocol="media-library-delivery-v1"
command=sys.argv[1]
if command=="caps":
    print(json.dumps({"protocol":protocol,"scope":"manifest-only","version":"1.0.0","simulated":True}));sys.exit()
if command=="auth":
    print(json.dumps({"authenticated":True,"scope_limited":True,"target":"synthetic-target"}));sys.exit()
scope_path,receipts_path,state_path,counter,behavior=sys.argv[2:]
scope=json.loads(Path(scope_path).read_text())
root=Path(scope_path).parent/"files"
for item in scope["files"]:
    file=Path(item["path"])
    assert file.is_relative_to(root)
    assert hashlib.sha256(file.read_bytes()).hexdigest()==item["sha256"]
count=Path(counter);count.write_text(str((int(count.read_text()) if count.exists() else 0)+1))
if state_path:
    state=Path(state_path);state.mkdir(exist_ok=True)
    (state/"client.db").write_text("SYNTHETIC_CREDENTIAL_MUST_NOT_APPEAR_IN_LOGS")
print("SYNTHETIC_CREDENTIAL_MUST_NOT_APPEAR_IN_LOGS",file=sys.stderr)
if behavior=="fail":sys.exit(9)
if behavior in ("receipts","partial"):
    receipts=[{"file_id":i["file_id"],"sha256":i["sha256"],"remote_id":"simulated-"+i["file_id"]} for i in scope["files"]]
    if behavior=="partial":receipts=receipts[:-1]
    Path(receipts_path).write_text(json.dumps({"protocol":protocol,"job_id":scope["job_id"],"receipts":receipts}))
''')
    return path


def delivery_toml(config_file,*,mode="configured-cli",behavior="receipts",backup=True):
    root=config_file.parent
    script=write_client(root/'client-stub.py')
    raw=config_file.read_text().replace('delivery="disabled"','delivery="auto"' if mode=='configured-cli' else 'delivery="manual"')
    settings={"mode":mode,"target":"synthetic-target","require_capture_date":True}
    if mode=='configured-cli':
        settings.update(allow_cli=True,executable=sys.executable,args=[str(script),'submit','{scope}','{receipts}','{state}',str(root/'attempts.txt'),behavior],
                        capability_args=[str(script),'caps'],auth_args=[str(script),'auth'])
    if backup:
        (root/'uploader-state').mkdir(exist_ok=True)
        (root/'uploader-state'/'session.db').write_text(FAKE_SECRET)
        settings.update(state_dir=str(root/'uploader-state'),backup_dir=str(root/'state-backup'))
    raw+='\n[delivery]\n'+'\n'.join(f'{k}={json.dumps(v)}' for k,v in settings.items())+'\n'
    config_file.write_text(raw)
    return root/'attempts.txt'
