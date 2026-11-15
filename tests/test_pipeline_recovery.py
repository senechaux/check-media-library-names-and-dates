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


class TransformAdapter(Adapter):
    identity = "test-transform:v1"
    simulated = True

    def __init__(self):
        self.produced = []

    def run(self, context):
        self.produced.append((context.stage, context.file_id))
        previous = context.artifact()
        source = Path(previous.path) if previous and context.stage != "export" else Path(context.entry.current_path)
        def produce(output):
            output.write_bytes(source.read_bytes() + context.stage.encode())
        artifact = context.executor.prepare(context.file_id, produce, lambda output: {"synthetic_content": True})
        if context.stage == "export":
            operation = context.executor.plan(context.file_id, "export", artifact=artifact)
            return StageResult(State.COMPLETED, [operation], evidence={"artifact": asdict(artifact), "simulated": True})
        return StageResult(State.COMPLETED, evidence={"artifact": asdict(artifact), "simulated": True})

    def validate(self, context):
        if context.record.get("operations"):
            return StageResult(State.COMPLETED, [context.store.manifest.operations[key] for key in context.record["operations"]],
                               evidence={"recovered_by_simulated_validator": True})
        return StageResult(State.WAITING_USER)


def test_all_stages_with_simulated_services_and_real_safe_installation(config_file):
    configure(config_file, modes={"import_review": "manual", **{stage: "auto" for stage in FILE_STAGES}, "delivery": "manual"})
    media(config_file, ("a/same.PNG", "b/same.PNG"))
    transform, audit = TransformAdapter(), SimulatedAdapter()
    adapters = {stage: transform for stage in ("metadata", "normalize", "compression", "export")}
    adapters["audit"] = audit
    from media_library.stages import HumanAdapter
    adapters["delivery"] = HumanAdapter()
    assert run(config_file, console=ScriptConsole(["comprobar", "aprobar", "comprobar", "comprobar"]), adapters=adapters) == 0
    value = report(config_file)
    assert value["simulated"] and len(value["changed"]) == 2
    assert [stage for stage, _ in transform.produced] == ["metadata"] * 2 + ["normalize"] * 2 + ["compression"] * 2 + ["export"] * 2
    assert all(Path(item["backup"]).read_bytes() == PNG for item in value["preserved"])
    assert len(value["human_confirmations"]) == 3
    assert len(list((config_file.parent / "export").rglob("same.PNG"))) == 2
    assert run(config_file, "--resume", value["run_id"], adapters=adapters) == 0
    assert len(transform.produced) == 8


@pytest.mark.parametrize("boundary", ["operation_planned", "publish_intent", "published", "operation_completed"])
def test_interruption_during_installation_recovers_without_repeating_producer(config_file, monkeypatch, boundary):
    configure(config_file, modes={"metadata": "auto", "installation": "auto"})
    media(config_file)
    adapter = TransformAdapter()
    original = RunStore.commit
    triggered = False
    def interrupt(store, kind, *args, **kwargs):
        nonlocal triggered
        original(store, kind, *args, **kwargs)
        if kind == boundary and not triggered:
            triggered = True
            raise KeyboardInterrupt
    monkeypatch.setattr(RunStore, "commit", interrupt)
    assert run(config_file, "--apply", adapters={"metadata": adapter}) == 130
    value = report(config_file)
    assert value["pending"] and triggered
    monkeypatch.undo()
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter}) == 0
    assert len(adapter.produced) == 1
    assert (config_file.parent / "source/a/same.PNG").read_bytes() == PNG + b"metadata"


def test_failed_persistence_after_publication_is_reported_and_recoverable(config_file, monkeypatch):
    from media_library import state
    configure(config_file, modes={"metadata": "auto", "installation": "auto"})
    media(config_file)
    adapter = TransformAdapter()
    original = state.atomic_json
    def fail_published(path, data):
        if "operations" in data and any(op["state"] == "PUBLISHED" for op in data["operations"].values()):
            raise OSError("synthetic manifest disk failure")
        return original(path, data)
    monkeypatch.setattr(state, "atomic_json", fail_published)
    assert run(config_file, "--apply", adapters={"metadata": adapter}) == 3
    value = report(config_file)
    assert value["fatal_error"] and value["exit_code"] == 3
    monkeypatch.undo()
    assert run(config_file, "--resume", value["run_id"], adapters={"metadata": adapter}) == 0
    assert len(adapter.produced) == 1


def test_explicit_decisions_are_saved_but_do_not_validate_unavailable_service(config_file):
    configure(config_file, modes={"metadata": "manual"})
    media(config_file)
    console = ScriptConsole(["decidir authority=metadata timezone=Europe/Madrid", "comprobar", "posponer"])
    assert run(config_file, "--apply", console=console) == 2
    record = report(config_file)["files"][0]["stages"]["metadata"]
    assert record["decisions"] == {"authority": "metadata", "timezone": "Europe/Madrid"}
    assert record["state"] == "WAITING_USER"


def test_cancelled_file_cannot_advance_or_be_resumed_as_success(config_file):
    configure(config_file, modes={"metadata": "manual", "installation": "auto"})
    media(config_file)
    assert run(config_file, "--apply", console=ScriptConsole(["cancelar"])) == 2
    value = report(config_file)
    assert run(config_file, "--resume", value["run_id"], console=ScriptConsole(["comprobar"])) == 2
    assert report(config_file)["files"][0]["stages"]["installation"]["state"] == "PLANNED"


@pytest.mark.parametrize("signal_name", ["SIGINT", "SIGHUP"])
def test_real_signal_during_tty_wait_persists_state_and_releases_lock(config_file, signal_name):
    import os
    import pty
    import selectors
    import signal
    import subprocess
    import time
    configure(config_file, modes={"metadata": "manual"})
    media(config_file)
    master, slave = pty.openpty()
    process = subprocess.Popen([sys.executable, "-m", "media_library", "run", "--config", str(config_file), "--apply"],
                               stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    os.close(slave)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = b""
    deadline = time.monotonic() + 15
    try:
        while b"comprobar / posponer" not in output:
            remaining = deadline - time.monotonic()
            assert remaining > 0 and selector.select(remaining), output.decode(errors="replace")
            chunk = os.read(process.stdout.fileno(), 65536)
            assert chunk, output.decode(errors="replace")
            output += chunk
        os.kill(process.pid, getattr(signal, signal_name))
        rest, _ = process.communicate(timeout=15)
        assert process.returncode == 130, (output + rest).decode(errors="replace")
    finally:
        selector.close()
        os.close(master)
        if process.poll() is None:
            process.kill()
            process.communicate()
    value = report(config_file)
    assert value["exit_code"] == 130 and value["interrupted"]
    assert run(config_file, "--resume", value["run_id"]) == 2


def test_dry_run_cannot_be_promoted_or_resumed_with_different_adapters(config_file):
    configure(config_file, modes={"metadata": "auto"})
    media(config_file)
    adapter = SimulatedAdapter()
    assert run(config_file, "--dry-run", adapters={"metadata": adapter}) == 2
    value = report(config_file)
    assert run(config_file, "--resume", value["run_id"], "--apply", adapters={"metadata": adapter}) == 3
    assert not adapter.calls
    assert run(config_file, "--resume", value["run_id"], "--dry-run") == 3
