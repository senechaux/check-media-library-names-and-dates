"""Informes regenerables; manifiesto y journal siguen siendo la fuente de estado."""

import shlex

from .pipeline_settings import FILE_STAGES, STAGES
from .state import atomic_json


def write_report(pipeline, code, pending):
    store, data = pipeline.store, pipeline.data
    command = ["python", "-m", "media_library", "run", "--config", pipeline.config_path,
               "--resume", store.manifest.run_id]
    if data["dry_run"]:
        command.append("--dry-run")
    stages = []
    for stage in STAGES:
        records = [value["stages"][stage] for value in data["files"].values() if value["selected"]] if stage in FILE_STAGES else [data["globals"][stage]]
        counts = {}
        for record in records:
            counts[record["state"]] = counts.get(record["state"], 0) + 1
        stages.append({"stage": stage, "mode": pipeline.mode(stage), "results": counts,
                       "adapter": data["adapters"].get(stage, {"identity": "core", "simulated": False})})
    operations = list(store.manifest.operations.values())
    changed = sorted({op.file_id for op in operations if op.state == "COMPLETED" and op.kind in ("replace", "rename")})
    report = {"run_id": store.manifest.run_id, "exit_code": code, "dry_run": data["dry_run"],
              "simulated": any(item["adapter"].get("simulated") and item["mode"] != "disabled" for item in stages),
              "stages": stages, "files": [{"file_id": entry.file_id, "original": entry.original_path,
                         "current": entry.current_path, **data["files"][entry.file_id]} for entry in store.manifest.entries],
              "changed": changed, "preserved": [{"file_id": op.file_id, "backup": op.backup} for op in operations if op.backup],
              "unchanged": [entry.file_id for entry in store.manifest.entries if entry.file_id not in changed],
              "omitted": [{"file_id": key, "reason": value["reason"]} for key, value in data["files"].items() if not value["selected"]],
              "pending": pending, "global_issues": data["global_issues"],
              "fatal_error": data.get("fatal_error"), "interrupted": data.get("interrupted"),
              "failures": [{"file_id": key, "stage": stage, "reason": record.get("reason") or record.get("issues")}
                           for key, value in data["files"].items() if value["selected"]
                           for stage, record in value["stages"].items() if record["state"] == "FAILED"],
              "human_confirmations": [{"stage": stage, "file_id": key, "technical_verification": False}
                   for key, value in data["files"].items() for stage, record in value["stages"].items()
                   if record.get("evidence", {}).get("human_confirmation")],
              "remote_delivery": "disabled" if pipeline.mode("delivery") == "disabled" else "No se realiza carga remota desde este programa; consultar declaraciones humanas o adaptador simulado",
              "resume_command": shlex.join(command),
              "paths": {name: str(store.root / name) for name in ("manifest.json", "journal.jsonl", "plan.json", "report.json")
                        if name != "plan.json" or (store.root / name).exists()}}
    if data["globals"]["import_review"].get("evidence", {}).get("human_confirmation"):
        report["human_confirmations"].append({"stage": "import_review", "file_id": None, "technical_verification": False})
    atomic_json(store.root / "report.json", report)
    return report
