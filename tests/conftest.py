from pathlib import Path

import pytest

from media_library.config import load_config


@pytest.fixture
def config_file(tmp_path):
    (tmp_path / "source").mkdir()
    path = tmp_path / "config.toml"
    path.write_text('''[paths]
source = "source"
workspace = "work"
archive = "archive"
export = "export"
[execution]
reserve_bytes = 0
''')
    return path


@pytest.fixture
def config(config_file):
    return load_config(config_file)


@pytest.fixture
def stored(config, tmp_path):
    from media_library.inventory import inventory
    from media_library.state import RunStore, SourceLock
    path = config.source / "album" / "original.PNG"
    path.parent.mkdir()
    path.write_bytes(b"\x89PNG\r\n\x1a\noriginal synthetic")
    entries, result = inventory(config)
    assert result.state == "COMPLETED"
    with SourceLock(config.source, registry=tmp_path / "locks") as lock:
        store = RunStore.create(config, lock, entries)
        yield store, entries[0].file_id


@pytest.fixture
def execution(stored):
    from media_library.operations import SafeExecutor
    store, file_id = stored
    return SafeExecutor(store), file_id
