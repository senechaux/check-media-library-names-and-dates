"""Adaptadores locales reales + transporte remoto SIMULADO en un proceso Python local."""

from pathlib import Path
import json

import pytest

from media_library.filesystem import fingerprint
from pipeline_support import ScriptConsole
from delivery_support import delivery_toml,FAKE_SECRET
from export_support import configure_export,make_jpeg,make_video,run_real,manifest,video_tools,exiftool

pytestmark=pytest.mark.integration


@pytest.mark.parametrize('resume_old',[False,True])
def test_real_pipeline_reconciles_a_ready_owner_with_later_uncertainty(config_file,video_tools,monkeypatch,resume_old):
    import itertools
    import uuid
    from media_library.state import RunStore
    from media_library.delivery_client import DeliveryClient
    config=configure_export(config_file,video_tools)
    counter=delivery_toml(config_file,behavior='fail',backup=False)
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    create=RunStore.create.__func__;numbers=itertools.count(1)
    def ordered_create(cls,*args,**kwargs):
        # Forzar que el READY antiguo se recorra antes que el run posterior.
        with monkeypatch.context() as patch:
            patch.setattr('media_library.state.uuid.uuid4',lambda:uuid.UUID(int=next(numbers)))
            return create(cls,*args,**kwargs)
    monkeypatch.setattr(RunStore,'create',classmethod(ordered_create))
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryClient,'preflight',lambda *a:(_ for _ in ()).throw(KeyboardInterrupt()))
        code,old=run_real(config_file,'--apply')
    assert code==130 and old['delivery']['state']=='READY' and not counter.exists()
    code,later=run_real(config_file,'--apply')
    assert code==2 and later['delivery']['state']=='UNCERTAIN' and counter.read_text()=='1'
    flags=['--resume',old['run_id']] if resume_old else ['--apply']
    code,current=run_real(config_file,*flags)
    assert code==2 and current['delivery']['state']=='UNCERTAIN' and counter.read_text()=='1'
    assert current['delivery']['job_id']==later['delivery']['job_id']


def test_complete_real_local_pipeline_preserves_human_review_gates(config_file,video_tools):
    config=configure_export(config_file,video_tools,video=True,metadata=True,reviewed=False)
    config_file.write_text(config_file.read_text().replace('import_review="disabled"','import_review="manual"').replace('\nquality_reviewed=true\n','\nquality_reviewed=false\n'))
    counter=delivery_toml(config_file)
    photo=config.source/'2026'/'album'/'2026-01-02 04.04.05.JPG'
    video=config.source/'2026'/'album'/'2026-01-02 04.04.06.MOV'
    make_jpeg(photo,orientation=6,exif=True,size=(1600,900));make_video(video,audio=True)
    originals={fingerprint(photo)['sha256'],fingerprint(video)['sha256']}
    code,report=run_real(config_file,'--apply')
    assert code==2 and not counter.exists()
    code,report=run_real(config_file,'--resume',report['run_id'],console=ScriptConsole(['comprobar','aprobar']))
    assert code==2 and not counter.exists() and not report['coverage']['local_complete']
    assert any(f['stages']['installation']['state']=='WAITING_USER' for f in report['files'])
    # Declaraciones sintéticas prueban el protocolo; no acreditan calidad humana.
    code,report=run_real(config_file,'--resume',report['run_id'],console=ScriptConsole(['decidir quality_reviewed=true','comprobar']))
    assert code==2 and not counter.exists()
    assert any(f['stages']['export'].get('evidence',{}).get('visual_review')=='pending_human' for f in report['files'])
    code,report=run_real(config_file,'--resume',report['run_id'],console=ScriptConsole(['decidir export_quality_reviewed=true','comprobar']))
    assert code==0,report
    assert counter.read_text()=='1' and report['coverage']['local_complete']
    assert report['delivery']['evidence_kind']=='client_receipts' and report['remote_interaction_simulated']
    assert report['delivery']['backup']['verified'] and report['delivery']['remote_presence_verified'] is False
    data=manifest(config_file,report)
    assert originals.issubset({op['expected']['sha256'] for op in data['operations'].values() if op['backup'] and op['kind']!='export'})
    assert sum(e['kind']=='video_encode_intent' for e in data['events'])==1
    assert sum(e['kind']=='export_encode_intent' for e in data['events'])==1
    code,resumed=run_real(config_file,'--resume',report['run_id'])
    assert code==0 and counter.read_text()=='1'
    assert FAKE_SECRET not in json.dumps(manifest(config_file,resumed))
    assert FAKE_SECRET not in json.dumps(resumed)


def test_manual_delivery_only_uses_audited_exports_and_records_declaration(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    counter=delivery_toml(config_file,mode='manual')
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    code,report=run_real(config_file,'--apply');assert code==2,report
    pause=report['files'][0]['stages']['delivery']['pause']
    assert next(iter(pause['inputs'].values())).endswith('scope.json')
    code,report=run_real(config_file,'--resume',report['run_id'],console=ScriptConsole(['decidir delivery_confirmed=true','comprobar']))
    assert code==0 and not counter.exists()
    assert report['delivery']['evidence_kind']=='human_declaration'
    assert report['delivery']['remote_presence_verified'] is False


def test_uncertain_delivery_cannot_be_repeated_by_resume_or_new_run(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    counter=delivery_toml(config_file,behavior='fail')
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    code,first=run_real(config_file,'--apply');assert code==2 and counter.read_text()=='1'
    assert first['delivery']['state']=='UNCERTAIN'
    code,resumed=run_real(config_file,'--resume',first['run_id']);assert code==2 and counter.read_text()=='1'
    code,fresh=run_real(config_file,'--apply');assert code==2 and counter.read_text()=='1'
    assert fresh['delivery']['adopted_from_run']==first['run_id']
    raw=config_file.read_text();config_file.write_text(raw.replace('"fail"','"receipts"'))
    code,different_client=run_real(config_file,'--apply')
    assert code==2 and counter.read_text()=='1'  # Cambiar el comando tampoco elude la incertidumbre.
    config_file.write_text(raw)
    code,resolved=run_real(config_file,'--resume',first['run_id'],console=ScriptConsole(['decidir delivery_resolution=delivered','comprobar']))
    assert code==0 and counter.read_text()=='1'
    assert resolved['delivery']['evidence_kind']=='human_reconciliation'


def test_only_an_explicit_new_resolution_can_authorize_another_attempt(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    counter=delivery_toml(config_file,behavior='fail',backup=False)
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    code,report=run_real(config_file,'--apply');assert code==2 and counter.read_text()=='1'
    run_id=report['run_id']
    code,report=run_real(config_file,'--resume',run_id,console=ScriptConsole(['decidir delivery_resolution=not-delivered','comprobar']))
    assert code==2 and counter.read_text()=='2'
    code,report=run_real(config_file,'--resume',run_id,console=ScriptConsole(['decidir delivery_confirmed=false','comprobar']))
    assert code==2 and counter.read_text()=='2'
    code,report=run_real(config_file,'--resume',run_id,console=ScriptConsole(['decidir delivery_resolution=not-delivered','comprobar']))
    assert code==2 and counter.read_text()=='3'
    assert run_real(config_file,'--resume',run_id)[0]==2 and counter.read_text()=='3'


def test_backup_failure_after_client_receipts_only_retries_backup(config_file,video_tools,monkeypatch):
    config=configure_export(config_file,video_tools)
    counter=delivery_toml(config_file)
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    import media_library.delivery_backup as backup
    original=backup.durable_copy
    def fail(*args,**kwargs):raise OSError('synthetic state backup failure')
    with monkeypatch.context() as patch:
        patch.setattr(backup,'durable_copy',fail)
        code,report=run_real(config_file,'--apply')
    assert code==3 and report['delivery']['state']=='DELIVERED' and counter.read_text()=='1'
    prepared=sum(e['kind']=='prepared' for e in manifest(config_file,report)['events'])
    code,resumed=run_real(config_file,'--resume',report['run_id'])
    assert code==0 and counter.read_text()=='1' and resumed['delivery']['backup']['verified']
    assert sum(e['kind']=='prepared' for e in manifest(config_file,resumed)['events'])==prepared


def test_local_unknown_date_cannot_start_delivery_requiring_dates(config_file,video_tools):
    config=configure_export(config_file,video_tools,require_capture_date=False)
    counter=delivery_toml(config_file)
    make_jpeg(config.source/'unknown.JPG')
    code,report=run_real(config_file,'--apply')
    assert code==2 and report['coverage']['local_complete'] and not counter.exists()
    assert report['coverage']['exported'][0]['date_known'] is False


def test_video_copy_fulfilling_recipe_avoids_another_encode(config_file,video_tools):
    config=configure_export(config_file,video_tools,reviewed=False)
    source=config.source/'2026-01-02 04.04.05.mp4'
    make_video(source,codec='libx264')
    code,report=run_real(config_file,'--apply');assert code==0,report
    exported=report['files'][0]['stages']['export']['evidence']['export']
    assert exported['recipe']['video_plan']['action']=='copy'
    assert not any(e['kind']=='export_encode_intent' for e in manifest(config_file,report)['events'])
