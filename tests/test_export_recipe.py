"""Contratos puros de receta/procedencia; sin acreditar herramientas de medios."""

from pathlib import Path

import pytest

from media_library.config import ConfigError, load_config
from media_library.export_settings import parse_export_settings
from media_library.filesystem import ConflictError, fingerprint
from media_library.provenance import best_source, digest
from media_library.video_plan import geometry


@pytest.mark.parametrize("visual,bounds", [((1920,1080),(854,480)), ((1080,1920),(480,854)), ((640,360),(640,360)), ((1080,1080),(480,480))])
def test_upload_geometry_respects_visual_bounds(visual,bounds):
    result=geometry(dict(zip(("visible_width","visible_height"),visual)),"upload-480p30")
    assert result["width"]<=bounds[0] and result["height"]<=bounds[1]
    assert abs(result["width"]/result["height"]/(visual[0]/visual[1])-1)<=.005


def test_recipe_digest_is_stable_and_changes_with_date_profile_or_identity():
    recipe={"identity":"album/a", "source_sha256":"abc", "date":"2026-01-02", "profile":"480"}
    assert digest(recipe)==digest(dict(reversed(list(recipe.items()))))
    for key in recipe:
        assert digest({**recipe,key:"changed"})!=digest(recipe)


def test_registered_original_is_required_instead_of_recompressing_derivative(execution):
    executor,file_id=execution
    source=Path(executor.store.entry(file_id).current_path)
    original=source.read_bytes()
    artifact=executor.prepare(file_id,lambda p:p.write_bytes(b"derived") and None,lambda p:{"synthetic":True})
    op=executor.plan(file_id,"substitute",artifact=artifact,destination=source.with_name("reduced.mp4"))
    assert executor.execute(op.operation_id).state=="COMPLETED"
    provenance=best_source(executor.store,executor.store.entry(file_id))
    assert provenance["path"]==op.backup and Path(provenance["path"]).read_bytes()==original
    Path(op.backup).write_bytes(b"changed")
    with pytest.raises(ConflictError,match="archivado"):
        best_source(executor.store,executor.store.entry(file_id))
    assert best_source(executor.store,executor.store.entry(file_id),use_archive=False)["path"]==op.destination


def test_export_config_optional_and_limits_explicit(config_file):
    assert "export_settings" not in load_config(config_file).effective()
    config_file.write_text(config_file.read_text()+'\n[export]\nimage_max_side=1000\n')
    assert load_config(config_file).export_settings["image_max_side"]==1000
    config_file.write_text(config_file.read_text().replace('image_max_side=1000','image_max_side=1201'))
    with pytest.raises(ConfigError):load_config(config_file)
    with pytest.raises(ValueError):parse_export_settings({"color_policy":"discard"})
