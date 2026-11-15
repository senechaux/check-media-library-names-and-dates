import json

import pytest

from media_library.config import ConfigError, load_config
from media_library.inventory import inventory
from media_library.state import PersistenceError, RunStore, SourceLock


@pytest.mark.parametrize("settings", ['[pipeline.modes]\nmetadata="anything"', '[pipeline]\ninclude=["../outside"]', '[pipeline]\nunknown=true'])
def test_invalid_scope_is_rejected_before_creating_destinations(config_file, settings):
    config_file.write_text(config_file.read_text() + settings)
    with pytest.raises(ConfigError):
        load_config(config_file)
    assert not (config_file.parent / "work").exists()


def test_inventory_checkpoint_replays_entries_after_snapshot_failure(config, tmp_path, monkeypatch):
    from media_library import state
    (config.source / "source.PNG").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    entries, _ = inventory(config)
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        store = RunStore.create(config, lock, [])
        def fail(*args):
            raise OSError("synthetic disk failure")
        monkeypatch.setattr(state, "atomic_json", fail)
        with pytest.raises(PersistenceError):
            store.commit("pipeline_inventory", entries=entries, evidence={"pipeline": {"version": 1}})
        assert json.loads(store.path.read_text())["entries"] == []
        monkeypatch.undo()
        loaded = RunStore.load(config, lock, store.manifest.run_id)
        assert loaded.entry(entries[0].file_id).current_path == str(config.source / "source.PNG")
        assert loaded.manifest.events[-1]["evidence"]["pipeline"]["version"] == 1
