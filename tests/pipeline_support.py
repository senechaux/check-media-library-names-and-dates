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

PNG = b"\x89PNG\r\n\x1a\nsynthetic original"


class ScriptConsole(Console):
    def __init__(self, answers=()):
        super().__init__(stdout=StringIO())
        self.answers = iter(answers)
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        answer = next(self.answers, None)
        if isinstance(answer, BaseException):
            raise answer
        return answer() if callable(answer) else answer


class SimulatedAdapter(Adapter):
    identity = "test-noop:v1"
    simulated = True

    def __init__(self):
        self.calls = []

    def run(self, context):
        self.calls.append((context.stage, context.file_id))
        return StageResult(State.COMPLETED, evidence={"unchanged": True, "simulated": True})

    validate = run


def configure(config_file, *, modes=None, include=None):
    disabled = {stage: "disabled" for stage in DEFAULT_MODES}
    raw = "\n[pipeline]\ninclude=" + json.dumps(include or ["*"]) + "\n[pipeline.modes]\n"
    raw += "\n".join(f'{stage}="{mode}"' for stage, mode in {**disabled, **(modes or {})}.items())
    config_file.write_text(config_file.read_text().split("\n[pipeline]")[0] + raw + "\n")
    return config_file


def media(config_file, names=("a/same.PNG",)):
    for name in names:
        path = config_file.parent / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)


def run(config_file, *flags, console=None, adapters=None):
    return main(["run", "--config", str(config_file), *flags], console=console or ScriptConsole(), adapters=adapters)


def report(config_file):
    runs = sorted((config_file.parent / "work").iterdir())
    assert len(runs) == 1
    return json.loads((runs[0] / "report.json").read_text())


def snapshot(config_file):
    root = next((config_file.parent / "work").iterdir())
    manifest = json.loads((root / "manifest.json").read_text())
    return next(event["evidence"]["pipeline"] for event in reversed(manifest["events"]) if "pipeline" in event["evidence"])
