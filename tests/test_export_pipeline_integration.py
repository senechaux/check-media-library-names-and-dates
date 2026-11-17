"""Derivados reales y recorrido local; sin cuentas ni tráfico de subida."""

from pathlib import Path
import json

import pytest

from media_library.filesystem import fingerprint
from export_support import configure_export,make_jpeg,make_video,run_real,manifest,video_tools,exiftool

pytestmark=pytest.mark.integration


def test_real_homonyms_years_without_exif_and_recipe_reuse(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    for relative in ('2025/album-a/2026-01-02 04.04.05.JPG','2026/album-b/2026-01-02 04.04.05.JPG'):
        make_jpeg(config.source/relative)
    before={str(p):fingerprint(p)['sha256'] for p in config.source.rglob('*.JPG')}
    code,report=run_real(config_file,'--apply')
    assert code==0,report
    outputs=[f['stages']['export']['evidence']['export'] for f in report['files']]
    assert len({o['path'] for o in outputs})==2
    assert report['coverage']['local_complete'] and len(report['coverage']['exported'])==2
    assert {o['recipe']['relative'] for o in outputs}=={'2025/album-a/2026-01-02 04.04.05.jpg','2026/album-b/2026-01-02 04.04.05.jpg'}
    assert all(o['validation']['technical']['orientation']==1 and o['recipe']['date'] for o in outputs)
    assert all(fingerprint(p)['sha256']==sha for p,sha in before.items())
    code,fresh=run_real(config_file,'--apply')
    assert code==0,fresh
    assert not manifest(config_file,fresh)['operations']
    assert all(f['stages']['export']['evidence']['export']['reused'] for f in fresh['files'])


def test_recipe_change_and_owned_partial_are_repaired_with_preservation(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    source=config.source/'2026-01-02 04.04.05.jpg';make_jpeg(source,size=(1600,900))
    code,first=run_real(config_file,'--apply');assert code==0,first
    exported=first['files'][0]['stages']['export']['evidence']['export'];path=Path(exported['path'])
    prior=path.read_bytes()
    config_file.write_text(config_file.read_text()+'image_max_side=600\n')
    code,changed=run_real(config_file,'--apply');assert code==0,changed
    op=next(iter(manifest(config_file,changed)['operations'].values()))
    assert Path(op['backup']).read_bytes()==prior
    assert changed['files'][0]['stages']['export']['evidence']['export']['recipe']['key']!=exported['recipe']['key']
    path.write_bytes(b'own partial synthetic derivative')
    code,repaired=run_real(config_file,'--resume',changed['run_id']);assert code==0,repaired
    data=manifest(config_file,repaired)
    assert sum(e['kind']=='prepared' for e in data['events'])==1  # Se reutiliza el candidato acreditado.
    assert any(op['backup'] and Path(op['backup']).read_bytes()==b'own partial synthetic derivative' for op in data['operations'].values())


def test_foreign_destination_and_unknown_date_block_the_scope(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    make_jpeg(config.source/'2026-01-02 04.04.05.JPG')
    target=config.export/'2026-01-02 04.04.05.jpg';make_jpeg(target)
    foreign=target.read_bytes()
    code,report=run_real(config_file,'--apply')
    assert code==2 and target.read_bytes()==foreign
    assert not manifest(config_file,report)['operations']
    assert not report['files'][0]['stages']['audit']['state']=='COMPLETED'


def test_unknown_capture_date_is_explicit_without_exif_exception(config_file,video_tools):
    config=configure_export(config_file,video_tools)
    make_jpeg(config.source/'unknown.jpg')
    code,report=run_real(config_file,'--apply')
    assert code==2 and 'Fecha requerida' in str(report['pending'])
    assert not manifest(config_file,report)['operations']


def test_video_upload_profile_uses_archived_original_and_verified_audio(config_file,video_tools):
    config=configure_export(config_file,video_tools,video=True,metadata=True)
    source=config.source/'2026-01-02 04.04.05.MOV'
    make_video(source,width=1080,height=1920,audio=True)
    original=fingerprint(source)['sha256']
    code,report=run_real(config_file,'--apply');assert code==0,report
    output=report['files'][0]['stages']['export']['evidence']['export']
    recipe=output['recipe'];actual=output['validation']['technical']['video']['output']
    assert recipe['source']['quality_source']=='verified_archive' and recipe['source']['sha256']==original
    assert recipe['video_plan']['info']['height']==1920
    assert actual['width']<=480 and actual['height']<=854 and actual['sar']=='1' and actual['rotation']==0
    assert actual['audio'][0]['codec']=='aac'
    assert video_tools.read(output['path'])['QuickTime:CreateDate']=='2026:01:02 03:04:05'
    code,fresh=run_real(config_file,'--apply');assert code==0,fresh
    assert fresh['files'][0]['stages']['export']['evidence']['export']['reused']
    assert not any(e['kind']=='export_encode_intent' for e in manifest(config_file,fresh)['events'])


def test_manual_export_uses_original_copy_and_explicit_association(config_file,video_tools):
    from media_library.image_export import render_image
    from media_library.export_settings import parse_export_settings
    from pipeline_support import ScriptConsole
    config=configure_export(config_file,video_tools,metadata=True,manual=True)
    source=config.source/'2026-01-02 04.04.05.JPG';make_jpeg(source,orientation=6,exif=True)
    original=fingerprint(source)['sha256']
    code,report=run_real(config_file,'--apply');assert code==2,report
    pause=report['files'][0]['stages']['export']['pause']
    assert fingerprint(next(iter(pause['inputs'].values())))['sha256']==original
    output=Path(next(iter(pause['outputs'].values()))).with_name('corrected manually.jpg')
    render_image(next(iter(pause['inputs'].values())),output,parse_export_settings({}))
    code,resumed=run_real(config_file,'--resume',report['run_id'],console=ScriptConsole(['decidir output='+json.dumps(str(output)),'comprobar']))
    assert code==0,resumed
    exported=resumed['files'][0]['stages']['export']['evidence']['export']
    assert exported['recipe']['source']['quality_source']=='verified_archive'
    assert exported['recipe']['date'] and Path(exported['path']).is_file()
