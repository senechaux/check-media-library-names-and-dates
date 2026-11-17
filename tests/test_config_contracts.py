from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pytest

from media_library.config import ConfigError, Tool, load_config, preflight
from media_library.models import Manifest, StageResult, State
from media_library.process import ProcessResult, ToolError, run_tool


def test_config_is_relative_to_toml_and_preflight_creates_nothing(config_file, tmp_path, monkeypatch):
    first = load_config(config_file)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert load_config(config_file) == first
    assert preflight(first) == {}
    assert not first.workspace.exists()
    assert not first.archive.exists()
    assert not first.export.exists()


@pytest.mark.parametrize("target", ["source", "work", "work/inside", "WORK"])
def test_overlap_and_symlink_are_rejected(config_file, tmp_path, target):
    (tmp_path / "alias").symlink_to(tmp_path / target, target_is_directory=True)
    config_file.write_text(config_file.read_text().replace('export = "export"', 'export = "alias"'))
    with pytest.raises(ConfigError, match="solapadas"):
        load_config(config_file)
    assert not (tmp_path / "work").exists()


def test_preflight_permission_space_and_capabilities(config, monkeypatch):
    monkeypatch.setattr("media_library.config.os.access", lambda *_: False)
    with pytest.raises(ConfigError):
        preflight(config)
    monkeypatch.undo()
    monkeypatch.setattr("media_library.config.shutil.disk_usage", lambda _: SimpleNamespace(free=9))
    with pytest.raises(ConfigError, match="Espacio"):
        preflight(config, estimates={"archive": 5, "workspace": 5})
    monkeypatch.undo()
    tool_config = replace(config, tools={"probe": Tool(sys.executable, ("--version",), ("--help",), ("impossible-option",))})
    with pytest.raises(ConfigError, match="Capacidades"):
        preflight(tool_config)
    with pytest.raises(ToolError):
        preflight(replace(config, tools={"missing": Tool("/does-not-exist")}))


@pytest.mark.parametrize("addition", ['[extra]\nx=1', '[inventory]\nexclude=["../bad"]', '[tools.x]\nversion_args="shell"'])
def test_invalid_config_is_rejected(config_file, addition):
    config_file.write_text(config_file.read_text() + addition)
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_contract_roundtrip_and_unknown_schema(config):
    manifest = Manifest("test", config.effective(), {}, [])
    assert Manifest.from_dict(json.loads(json.dumps(manifest.to_dict()))) == manifest
    for version in (0, 2, True, "1", None):
        with pytest.raises(ValueError, match="Versión"):
            Manifest.from_dict({**manifest.to_dict(), "schema_version": version})
    with pytest.raises(ValueError):
        StageResult(State.COMPLETED, issues=["error"])


def test_process_literal_arguments_and_failure(tmp_path):
    value = str(tmp_path / '''spaces ' " $(touch INJECTED) ;.MOV''')
    result = run_tool([sys.executable, "-c", "import sys; print(sys.argv[1])", value]).check()
    assert result.stdout.strip() == value
    assert not (tmp_path / "INJECTED").exists()
    result = run_tool([sys.executable, "-c", "import sys; print('diagnostic', file=sys.stderr); sys.exit(7)"])
    assert result.returncode == 7 and "diagnostic" in result.stderr
    with pytest.raises(ToolError):
        result.check()
    assert run_tool(["/not-a-tool"]).error
    result = run_tool([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.05)
    assert result.timed_out and not result.ok
