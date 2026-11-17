"""Contrato de planificación; estos casos puros no acreditan un codificador real."""

from copy import deepcopy

import pytest

from media_library.config import ConfigError, load_config
from media_library.video_plan import VideoPolicyError, geometry, plan_video, preset, profile_hash, video_info
from media_library.video_settings import parse_video_settings


def probe(width=1920, height=1080, *, brand="mp42", fps="24/1", sar="1:1", rotation=0):
    return {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "2", "tags": {"major_brand": brand}},
            "streams": [{"codec_type": "video", "codec_name": "h264", "width": width, "height": height,
                         "sample_aspect_ratio": sar, "avg_frame_rate": fps, "r_frame_rate": fps,
                         "side_data_list": [{"rotation": rotation}], "field_order": "progressive", "pix_fmt": "yuv420p"}]}


@pytest.mark.parametrize("data,expected", [
    (probe(), (1280, 720)), (probe(1080, 1920), (720, 1280)),
    (probe(rotation=90), (720, 1280)), (probe(rotation=270), (720, 1280)),
    (probe(640, 360), (640, 360)), (probe(1000, 1000), (720, 720)),
    (probe(720, 576, sar="16:15"), (768, 576)),
])
def test_geometry_uses_visual_dimensions_without_upscale_or_crop(data, expected):
    info = video_info(data)
    result = geometry(info)
    assert (result["width"], result["height"]) == expected
    assert result["sar"] == "1:1" and result["rotation"] == 0
    assert result["width"] <= info["visible_width"] and result["height"] <= info["visible_height"]


def test_height_720_is_a_distinct_vertical_policy():
    result = geometry(video_info(probe(1080, 1920)), "height-720")
    assert (result["width"], result["height"]) == (404, 720)


def test_selection_threshold_real_brand_and_combined_work():
    below = plan_video("a.mp4", 49_999_999, probe(), {})
    boundary = plan_video("a.mp4", 50_000_000, probe(), {})
    mov = plan_video("mislabelled.mp4", 1, probe(640, 360, brand="qt  "), {})
    combined = plan_video("a.MOV", 50_000_000, probe(brand="qt  "), {})
    assert below["action"] == "none"
    assert boundary["action"] == "encode" and boundary["stage"] == "compression"
    assert mov["action"] == "remux" and mov["stage"] == "normalize"
    assert combined["action"] == "encode" and combined["combined"]
    assert combined["destination"] == "a reduced_size.mp4"
    assert plan_video("a.MOV", 1, probe(brand="qt  "), {})["action"] == "encode"


def test_history_requires_explicit_migration_but_verified_output_is_reused():
    with pytest.raises(VideoPolicyError, match="historical_marker"):
        plan_video("a reduced_size.mp4", 50_000_000, probe(), {})
    assert plan_video("a reduced_size.mp4", 50_000_000, probe(), {"historical_policy": "keep"})["action"] == "none"
    assert plan_video("a reduced_size.mp4", 50_000_000, probe(), {}, already_validated=True)["action"] == "none"
    assert plan_video("a reduced_size.mp4", 50_000_000, probe(), {"historical_policy": "process"})["action"] == "encode"


@pytest.mark.parametrize("fault", ["hdr", "audio", "subtitle", "interlaced", "rotation", "sar"])
def test_unapproved_content_blocks_before_transform(fault):
    data = probe()
    stream = data["streams"][0]
    if fault == "hdr": stream["color_transfer"] = "smpte2084"
    if fault == "audio": data["streams"].extend([{"codec_type": "audio", "codec_name": "aac", "channels": 2}] * 2)
    if fault == "subtitle": data["streams"].append({"codec_type": "subtitle"})
    if fault == "interlaced": stream["field_order"] = "tt"
    if fault == "rotation": stream["side_data_list"][0]["rotation"] = 45
    if fault == "sar": stream["sample_aspect_ratio"] = "0:1"
    with pytest.raises(VideoPolicyError):
        plan_video("a.mov", 50_000_000, data, {})


def test_profile_is_reproducible_and_distinguishes_pfr_cfr():
    pfr = parse_video_settings({})
    cfr = parse_video_settings({"frame_rate_mode": "cfr"})
    assert profile_hash(pfr) == profile_hash(deepcopy(pfr)) != profile_hash(cfr)
    value = preset(pfr)["PresetList"][0]
    assert value["PictureAllowUpscaling"] is False and value["PictureCropMode"] == 3
    assert value["PicturePAR"] == "off" and value["PictureCombDetectPreset"] == "off"
    assert value["VideoFramerateMode"] == "pfr" and value["VideoQualitySlider"] == 22
    assert plan_video("a.mov", 1, probe(640, 360, brand="qt  ", fps="24/1"), cfr)["action"] == "encode"


@pytest.mark.parametrize("raw", [{"min_bytes": -1}, {"min_savings_ratio": float("nan")}, {"quality": 52}, {"quality_reviewed": "yes"}, {"frame_rate_mode": "vfr"}])
def test_invalid_settings_rejected(raw):
    with pytest.raises(ValueError): parse_video_settings(raw)


def test_video_toml_is_optional_and_frozen(config_file):
    config = load_config(config_file)
    assert "video" not in config.effective()
    config_file.write_text(config_file.read_text() + '\n[video]\nmin_bytes=123\nframe_rate_mode="cfr"\n')
    assert load_config(config_file).effective()["video"]["min_bytes"] == 123
    config_file.write_text(config_file.read_text() + 'invented=true\n')
    with pytest.raises(ConfigError): load_config(config_file)
