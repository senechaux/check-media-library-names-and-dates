"""Pausas, fallos y recuperación con codificadores reales y originales sintéticos."""

from pathlib import Path
import json
import os
import uuid

import pytest

from media_library.filesystem import fingerprint
from media_library.state import RunStore
from media_library.video_driver import VideoDriver
from pipeline_support import ScriptConsole
from video_support import configure_video, make_video, manifest, run_real, video_tools, exiftool

pytestmark = pytest.mark.integration


def test_visual_review_is_separate_from_technical_validation(config_file, video_tools):
    config = configure_video(config_file, video_tools, reviewed=False)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source)
    original = source.read_bytes()
    code, report = run_real(config_file, "--apply")
    assert code == 2 and source.read_bytes() == original
    record = report["files"][0]["stages"]["installation"]
    assert record["evidence"]["technical_validation"] and record["evidence"]["visual_review"] == "pending_human"
    candidate = Path(record["evidence"]["candidate"])
    assert candidate.is_file() and not manifest(config_file, report)["operations"]
    # Simula exclusivamente una declaración humana del protocolo; no acredita calidad visual.
    code, resumed = run_real(config_file, "--resume", report["run_id"], console=ScriptConsole(["decidir quality_reviewed=true", "comprobar"]))
    assert code == 0
    assert resumed["files"][0]["stages"]["installation"]["evidence"]["quality_review"] == "human_declaration"
    assert sum(e["kind"] == "video_encode_intent" for e in manifest(config_file, resumed)["events"]) == 1


@pytest.mark.parametrize("corrupt", [False, True])
def test_manual_output_is_revalidated_before_safe_installation(config_file, video_tools, corrupt):
    config = configure_video(config_file, video_tools, manual=True)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source)
    original = source.read_bytes()
    code, report = run_real(config_file, "--apply")
    assert code == 2 and source.read_bytes() == original
    record = report["files"][0]["stages"]["normalize"]
    pause = record["pause"]
    output = Path(next(iter(pause["outputs"].values())))
    driver = VideoDriver(config)
    plan = pause["video_plan"]
    preset = output.parent / "manual-preset.json"
    driver.write_preset(preset, plan)
    for command in driver.produce(next(iter(pause["inputs"].values())), output, plan, preset): driver.call(command)
    if corrupt:
        # Contenedor y cabeceras válidos, pero un paquete de vídeo roto: prueba
        # real de decodificación, sin sustituirla por un error de formato/mocks.
        packets = json.loads(driver.call([driver.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_packets",
                                           "-show_entries", "packet=pos,size", "-of", "json", str(output)]).stdout)["packets"]
        packet = packets[len(packets)//2]
        data = bytearray(output.read_bytes())
        start, size = int(packet["pos"]), int(packet["size"])
        data[start+4:start+size] = b"\xff" * (size-4)
        output.write_bytes(data)
        assert driver.inspect(output)["streams"][0]["codec_name"] == "h264"
        assert output.stat().st_size < source.stat().st_size
    code, resumed = run_real(config_file, "--resume", report["run_id"])
    assert code == (3 if corrupt else 0), resumed
    if corrupt:
        assert source.read_bytes() == original and not manifest(config_file, resumed)["operations"]
        assert output.exists()  # Un fallo nunca limpia pendientes.
    else:
        assert not source.exists() and not output.exists()
        op = next(iter(manifest(config_file, resumed)["operations"].values()))
        assert op["evidence"]["validation"]["video"]["manual"]
        assert Path(op["backup"]).read_bytes() == original


@pytest.mark.parametrize("policy", ["hdr", "multiple_audio"])
def test_real_unapproved_streams_pause_without_encoding(config_file, video_tools, policy):
    config = configure_video(config_file, video_tools)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source, codec="libx264", audio=policy == "multiple_audio", hdr=policy == "hdr", multiple_audio=policy == "multiple_audio")
    before = fingerprint(source)
    code, report = run_real(config_file, "--apply")
    assert code == 2 and fingerprint(source) == before
    assert policy in str(report["pending"])
    assert not any(e["kind"] == "video_encode_intent" for e in manifest(config_file, report)["events"])


def test_real_dry_run_only_probes_and_plans(config_file, video_tools):
    config = configure_video(config_file, video_tools)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source)
    before = fingerprint(source)
    code, report = run_real(config_file, "--dry-run")
    assert code == 2 and fingerprint(source) == before
    data = manifest(config_file, report)
    assert not data["operations"] and not any(e["kind"] in ("video_encode_intent", "prepare_intent") for e in data["events"])
    assert not list(config.workspace.rglob("*.result"))


def test_real_larger_candidate_is_not_installed(config_file, video_tools):
    config = configure_video(config_file, video_tools, quality=0)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source, codec="libx264")
    before = source.read_bytes()
    code, report = run_real(config_file, "--apply")
    assert code == 0 and source.read_bytes() == before
    evidence = report["files"][0]["stages"]["normalize"]["evidence"]
    assert evidence["reason"] == "not_beneficial"
    assert evidence["video"]["output_bytes"] >= len(before)
    assert not manifest(config_file, report)["operations"]


def test_collision_blocks_only_one_album_and_keeps_its_temporaries(config_file, video_tools):
    config = configure_video(config_file, video_tools, include=["*.MOV"])
    first = config.source / "a" / "2026-01-02 04.04.05.MOV"
    second = config.source / "b" / first.name
    make_video(first); make_video(second)
    target = first.with_name(first.stem + " reduced_size.mp4")
    make_video(target, codec="libx264")
    original, existing = first.read_bytes(), target.read_bytes()
    code, report = run_real(config_file, "--apply")
    assert code == 3 and first.read_bytes() == original and target.read_bytes() == existing
    assert not second.exists()
    data = manifest(config_file, report)
    op = next(iter(data["operations"].values()))
    assert op["source"] == str(second) and "/b/" in op["backup"]
    pending = next(f for f in report["files"] if f["original"] == str(first))
    assert Path(pending["stages"]["normalize"]["evidence"]["artifact"]["path"]).exists()
    assert not Path(op["candidate"]).exists()


@pytest.mark.parametrize("boundary", ["operation_planned", "operation_intent", "backup_verified", "publish_intent", "published", "source_retired", "operation_completed", "video_cleanup_intent"])
def test_real_cross_volume_publication_resumes_without_recoding(config_file, video_tools, monkeypatch, boundary):
    root = os.environ.get("MEDIA_LIBRARY_TEST_VOLUME")
    if not root:
        pytest.skip("Falta volumen sintético separado; indicar MEDIA_LIBRARY_TEST_VOLUME")
    volume = Path(root).resolve() / ("video-" + uuid.uuid4().hex)
    volume.mkdir()
    assert volume.stat().st_dev != config_file.parent.stat().st_dev, "La prueba exige volúmenes realmente distintos"
    config = configure_video(config_file, video_tools)
    raw = config_file.read_text().replace('workspace = "work"', 'workspace = ' + json.dumps(str(volume / "work")))
    raw = raw.replace('archive = "archive"', 'archive = ' + json.dumps(str(volume / "archive")))
    config_file.write_text(raw)
    from media_library.config import load_config
    config = load_config(config_file)
    source = config.source / "2026-01-02 04.04.05.MOV"
    make_video(source, width=160, height=90)
    original = fingerprint(source)["sha256"]
    commit = RunStore.commit
    fired = False
    def interrupt(store, event, *args, **kwargs):
        nonlocal fired
        commit(store, event, *args, **kwargs)
        if event == boundary and not fired:
            fired = True
            raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(RunStore, "commit", interrupt)
        code, report = run_real(config_file, "--apply")
    assert fired and code == 130, report
    prepared = [e for e in manifest(config_file, report)["events"] if e["kind"] == "prepared"]
    assert len(prepared) == 1
    code, resumed = run_real(config_file, "--resume", report["run_id"])
    assert code == 0, resumed
    data = manifest(config_file, resumed)
    assert sum(e["kind"] == "video_encode_intent" for e in data["events"]) == 1
    op = next(iter(data["operations"].values()))
    assert op["state"] == "COMPLETED" and not source.exists()
    assert fingerprint(op["backup"])["sha256"] == original
    assert fingerprint(op["destination"])["sha256"] == op["output_sha256"]
    assert not Path(op["candidate"]).exists()
