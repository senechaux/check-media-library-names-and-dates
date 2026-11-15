"""Contratos serializables del núcleo. La versión 1 se rechaza si es desconocida."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from .capture_dates import CaptureDate

SCHEMA_VERSION = 1


class State(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class Issue:
    code: str
    message: str
    path: str | None = None
    file_id: str | None = None


@dataclass
class Entry:
    file_id: str
    original_path: str
    current_path: str
    relative_path: str
    stat: dict[str, int] = field(default_factory=dict)
    classification: str = "unsupported"
    media: dict[str, Any] = field(default_factory=dict)
    sha256: str | None = None
    temporal_decision: dict[str, Any] | None = None
    operations: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


@dataclass
class Operation:
    operation_id: str
    file_id: str
    kind: str
    source: str
    destination: str
    expected: dict[str, Any]
    candidate: str
    output_sha256: str
    backup: str | None = None
    local_part: str | None = None
    state: str = "PLANNED"
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class StageResult:
    state: State
    operations: list[Operation] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.state == State.COMPLETED and self.issues:
            raise ValueError("Una etapa con incidencias no puede declarar éxito total")


@dataclass
class Manifest:
    run_id: str
    config: dict[str, Any]
    versions: dict[str, str]
    entries: list[Entry]
    schema_version: int = SCHEMA_VERSION
    state: str = State.PLANNED
    operations: dict[str, Operation] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    sequence: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
            raise ValueError("Versión de manifiesto desconocida; no se migra automáticamente")
        data = dict(data)
        data["entries"] = [Entry(**{**e, "issues": [Issue(**i) for i in e["issues"]]})
                           for e in data["entries"]]
        data["operations"] = {key: Operation(**op) for key, op in data["operations"].items()}
        manifest = cls(**data)
        State(manifest.state)
        ids = [entry.file_id for entry in manifest.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs duplicados en manifiesto")
        return manifest
