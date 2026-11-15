from dataclasses import asdict
from io import StringIO
from pathlib import Path
import json
import sys

import pytest

from media_library.__main__ import main
from media_library.models import Issue, StageResult, State
from media_library.pipeline import Console
from media_library.pipeline_settings import DEFAULT_MODES, FILE_STAGES, STAGES
from media_library.stages import Adapter, associate_outputs
from media_library.filesystem import ConflictError, fingerprint
from media_library.state import RunStore

from pipeline_support import PNG, ScriptConsole, SimulatedAdapter, configure, media, run, report, snapshot


def test_real_local_scope_selection_and_installed_cli_from_other_cwd(config_file, tmp_path):
    from media_library.process import run_tool
    configure(config_file, include=["a/*"])
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    result = run_tool([sys.executable, "-m", "media_library", "run", "--config", str(config_file), "--apply"], cwd=tmp_path).check()
    result = report(config_file)
    assert result["exit_code"] == 0 and result["remote_delivery"] == "disabled"
    assert len(result["omitted"]) == 1 and result["omitted"][0]["reason"]
    assert [stage["stage"] for stage in result["stages"]] == list(STAGES)
    assert not result["simulated"]


def test_dry_run_never_waits_or_invokes_mutators_or_validators(config_file):
    configure(config_file, modes={"import_review": "manual", "metadata": "manual", "compression": "auto", "delivery": "manual"})
    media(config_file)
    class MustNotRun(SimulatedAdapter):
        def run(self, context):
            pytest.fail("Un adaptador mutador se invocó en simulación")
        validate = run
    console = ScriptConsole([AssertionError("No debe preguntar")])
    adapter = MustNotRun()
    assert run(config_file, "--dry-run", console=console, adapters={"metadata": adapter, "compression": adapter, "delivery": adapter}) == 2
    value = report(config_file)
    assert value["dry_run"] and value["pending"] and not console.prompts
    assert (config_file.parent / "source/a/same.PNG").read_bytes() == PNG
    assert not list((config_file.parent / "work").rglob("input.PNG"))
    assert not (config_file.parent / "archive").exists()
    assert not (config_file.parent / "export").exists()
    plan = json.loads((Path(value["paths"]["plan.json"])).read_text())
    assert plan["operations"][0]["file_id"]


def test_single_batch_approval_and_frozen_approval_on_resume(config_file):
    configure(config_file, modes={"metadata": "auto", "audit": "auto"})
    media(config_file)
    adapter = SimulatedAdapter()
    console = ScriptConsole(["aprobar"])
    assert run(config_file, console=console, adapters={"metadata": adapter, "audit": adapter}) == 0
    assert len(console.prompts) == 1 and len(adapter.calls) == 2
    value = report(config_file)
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter, "audit": adapter}) == 0
    assert len(adapter.calls) == 2


@pytest.mark.parametrize("answer", [None, "posponer", "cancelar"])
def test_no_batch_approval_never_runs_auto_adapter(config_file, answer):
    configure(config_file, modes={"metadata": "auto"})
    media(config_file)
    adapter = SimulatedAdapter()
    assert run(config_file, console=ScriptConsole([answer]), adapters={"metadata": adapter}) == 2
    assert not adapter.calls
    assert not snapshot(config_file)["approved"]


def test_apply_preserves_unresolved_temporal_conflict_and_dependents(config_file):
    configure(config_file, modes={"metadata": "auto", "installation": "auto", "delivery": "manual"})
    media(config_file)
    assert run(config_file, "--apply") == 2
    value = report(config_file)
    records = value["files"][0]["stages"]
    assert records["metadata"]["state"] == "WAITING_USER"
    assert records["installation"]["state"] == "PLANNED"
    assert records["delivery"]["state"] == "PLANNED"
    assert not records["metadata"].get("decisions")


class ManualCorrection(Adapter):
    identity = "test-manual-correction:v1"
    simulated = True

    def __init__(self):
        self.validations = 0

    def validate(self, context):
        self.validations += 1
        path = Path(context.pause["inputs"][context.file_id])
        if not path.read_bytes().endswith(b"corrected"):
            return StageResult(State.WAITING_USER, issues=[Issue("still_invalid", "La discrepancia sintética persiste")])
        def produce(output):
            output.write_bytes(path.read_bytes())
        artifact = context.executor.prepare(context.file_id, produce, lambda output: {"synthetic_validation": True})
        return StageResult(State.COMPLETED, evidence={"artifact": asdict(artifact), "simulated": True})


def test_confirmation_revalidates_and_does_not_advance_invalid_file(config_file):
    configure(config_file, modes={"metadata": "manual", "installation": "auto"})
    media(config_file)
    adapter = ManualCorrection()
    assert run(config_file, "--apply", console=ScriptConsole(["comprobar", "posponer"]), adapters={"metadata": adapter}) == 2
    value = report(config_file)
    assert adapter.validations == 1
    assert value["files"][0]["stages"]["installation"]["state"] == "PLANNED"
    assert (config_file.parent / "source/a/same.PNG").read_bytes() == PNG
    assert "still_invalid" in json.dumps(value)


def test_manual_resume_with_two_same_basename_files_and_independent_progress(config_file):
    configure(config_file, modes={"metadata": "manual", "installation": "auto"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    adapter = ManualCorrection()
    assert run(config_file, "--apply", adapters={"metadata": adapter}) == 2
    value = report(config_file)
    pauses = [entry["stages"]["metadata"]["pause"] for entry in value["files"]]
    inputs = [Path(next(iter(pause["inputs"].values()))) for pause in pauses]
    assert inputs[0] != inputs[1]
    inputs[1].write_bytes(PNG + b"corrected")
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter}) == 2
    value = report(config_file)
    assert value["files"][0]["stages"]["metadata"]["state"] == "WAITING_USER"
    assert value["files"][1]["stages"]["installation"]["state"] == "COMPLETED"
    calls = adapter.validations
    inputs[0].write_bytes(PNG + b"corrected")
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter}) == 0
    final = report(config_file)
    assert adapter.validations == calls + 1
    assert len(final["changed"]) == 2
    assert len({entry["backup"] for entry in final["preserved"]}) == 2
    assert all(Path(entry["backup"]).read_bytes() == PNG for entry in final["preserved"])


@pytest.mark.parametrize("tty", [False, True])
def test_no_tty_and_eof_are_pending_not_confirmation(config_file, tty):
    configure(config_file, modes={"metadata": "manual"})
    media(config_file)
    stream = StringIO("")
    stream.isatty = lambda: tty
    console = Console(stdin=stream, stdout=StringIO())
    assert run(config_file, "--apply", console=console) == 2
    record = report(config_file)["files"][0]["stages"]["metadata"]
    assert record["state"] == "WAITING_USER" and not record.get("human_confirmed")


def test_ctrl_c_persists_pause_releases_lock_and_returns_130(config_file):
    configure(config_file, modes={"metadata": "manual"})
    media(config_file)
    assert run(config_file, "--apply", console=ScriptConsole([KeyboardInterrupt()])) == 130
    value = report(config_file)
    assert value["pending"]
    assert snapshot(config_file)["interrupted"]["at"][0] == "metadata"
    assert run(config_file, "--resume", value["run_id"]) == 2


def test_changed_config_is_rejected_without_modifying_active_manifest(config_file):
    configure(config_file, modes={"metadata": "manual"})
    media(config_file)
    assert run(config_file, "--apply") == 2
    value = report(config_file)
    manifest = Path(value["paths"]["manifest.json"])
    before = manifest.read_bytes()
    config_file.write_text(config_file.read_text().replace('metadata="manual"', 'metadata="auto"'))
    assert run(config_file, "--resume", value["run_id"]) == 3
    assert manifest.read_bytes() == before


def test_external_original_change_requires_new_plan_only_for_that_file(config_file):
    configure(config_file, modes={"metadata": "auto"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    adapter = SimulatedAdapter()
    assert run(config_file, console=ScriptConsole(["posponer"]), adapters={"metadata": adapter}) == 2
    value = report(config_file)
    changed = config_file.parent / "source/a/same.PNG"
    changed.write_bytes(b"external content")
    assert run(config_file, "--resume", value["run_id"], "--apply", adapters={"metadata": adapter}) == 2
    value = report(config_file)
    assert value["files"][0]["replan"] and len(adapter.calls) == 1
    assert value["files"][1]["stages"]["metadata"]["state"] == "COMPLETED"
    assert changed.read_bytes() == b"external content"


def test_partial_operational_failure_retains_other_successes(config_file):
    configure(config_file, modes={"metadata": "auto", "audit": "auto"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    class FailOne(SimulatedAdapter):
        def run(self, context):
            if context.entry.relative_path.startswith("a/"):
                raise OSError("synthetic service failure")
            return super().run(context)
    adapter = FailOne()
    assert run(config_file, "--apply", adapters={"metadata": adapter, "audit": adapter}) == 3
    value = report(config_file)
    assert value["files"][0]["stages"]["metadata"]["state"] == "FAILED"
    assert value["files"][1]["stages"]["audit"]["state"] == "COMPLETED"


def test_web_confirmation_is_human_and_never_remote_verification(config_file):
    configure(config_file, modes={"delivery": "manual"})
    media(config_file)
    assert run(config_file, "--apply", console=ScriptConsole(["comprobar"])) == 0
    value = report(config_file)
    assert value["human_confirmations"] == [{"stage": "delivery", "file_id": value["files"][0]["file_id"], "technical_verification": False}]
    assert not (config_file.parent / "export").exists()


def test_import_review_precedes_inventory_and_does_not_replace_approval(config_file):
    configure(config_file, modes={"import_review": "manual"})
    def imported():
        media(config_file)
        return "comprobar"
    console = ScriptConsole([imported, "aprobar"])
    assert run(config_file, console=console) == 0
    assert len(report(config_file)["files"]) == 1
    assert len(console.prompts) == 2
    assert report(config_file)["human_confirmations"][0]["stage"] == "import_review"


def test_compression_pause_has_exact_map_profile_and_copies(config_file):
    configure(config_file, modes={"compression": "manual"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    assert run(config_file, "--apply") == 2
    value = report(config_file)
    for entry in value["files"]:
        pause = entry["stages"]["compression"]["pause"]
        assert pause["tool"] == "HandBrake" and pause["settings"]["profile"]
        assert pause["file_ids"] == [entry["file_id"]]
        assert Path(pause["inputs"][entry["file_id"]]).read_bytes() == PNG
        assert pause["outputs"][entry["file_id"]].endswith(".mp4")
        assert pause["resume_condition"]


def test_original_changed_while_waiting_cannot_be_accepted_by_confirmation(config_file):
    configure(config_file, modes={"metadata": "manual", "delivery": "manual"})
    media(config_file)
    def edit_original():
        (config_file.parent / "source/a/same.PNG").write_bytes(b"external edit during pause")
        return "comprobar"
    assert run(config_file, "--apply", console=ScriptConsole([edit_original]), adapters={"metadata": SimulatedAdapter()}) == 2
    value = report(config_file)
    assert value["files"][0]["replan"]
    assert value["files"][0]["stages"]["delivery"]["state"] == "PLANNED"


def test_renamed_working_copies_are_not_regenerated_and_keep_original_identity(config_file):
    configure(config_file, modes={"metadata": "manual"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    class RenameValidator(Adapter):
        identity = "test-rename:v1"
        simulated = True
        def validate(self, context):
            original_copy = Path(context.pause["inputs"][context.file_id])
            selected = associate_outputs({context.file_id: context.record["copy_sha256"]}, list(original_copy.parent.glob("*.renamed")))
            assert not original_copy.exists()
            operation = context.executor.plan(context.file_id, "rename", destination=Path(context.entry.current_path).with_name("renamed.PNG"))
            return StageResult(State.COMPLETED, [operation], evidence={"synthetic_association": selected})
    adapter = RenameValidator()
    assert run(config_file, "--apply", adapters={"metadata": adapter}) == 2
    value = report(config_file)
    for entry in value["files"]:
        source = Path(entry["stages"]["metadata"]["pause"]["inputs"][entry["file_id"]])
        source.rename(source.with_suffix(".renamed"))
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter}) == 0
    result = report(config_file)
    assert all(entry["original"].endswith("same.PNG") and entry["current"].endswith("renamed.PNG") for entry in result["files"])
    assert len({entry["file_id"] for entry in result["files"]}) == 2
    assert len({entry["backup"] for entry in result["preserved"]}) == 2


def test_selected_unsupported_file_is_counted_as_inventory_failure(config_file, monkeypatch):
    configure(config_file)
    path = config_file.parent / "source/unsupported.PNG"
    path.write_bytes(b"synthetic unsupported")
    def unsupported(*args):
        raise ValueError("synthetic unsupported format")
    monkeypatch.setattr("media_library.inventory.probe_media", unsupported)
    assert run(config_file, "--apply") == 3
    value = report(config_file)
    assert value["failures"][0]["stage"] == "inventory"
    assert value["failures"][0]["file_id"] == value["files"][0]["file_id"]
    assert "synthetic unsupported" in value["failures"][0]["reason"]
