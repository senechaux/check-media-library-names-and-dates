from pathlib import Path
import pytest
from media_library.stages import associate_outputs
from media_library.filesystem import ConflictError, fingerprint
PNG = b"\x89PNG\r\n\x1a\nsynthetic original"


def test_renamed_outputs_require_unique_hash_or_explicit_decision(tmp_path):
    a, b = tmp_path / "renamed A", tmp_path / "renamed B"
    a.write_bytes(PNG); b.write_bytes(PNG)
    sha = fingerprint(a)["sha256"]
    with pytest.raises(ConflictError, match="ambigua"):
        associate_outputs({"id-a": sha, "id-b": sha}, [a, b])
    assert associate_outputs({"id-a": sha, "id-b": sha}, [a, b], {"id-a": a, "id-b": b}) == {"id-a": str(a), "id-b": str(b)}
