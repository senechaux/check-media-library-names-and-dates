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
