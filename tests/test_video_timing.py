"""Contratos de presentación; la compatibilidad real se verifica por separado."""

import copy
import pytest

from media_library.av_timing import presentation, validate_alignment, validate_video_coverage


def timeline(start=0, intervals=((0,1),)):
    return {"video":{"start":start}, "audio":{"sample_rate":44100,"segments":intervals}}


@pytest.mark.parametrize('duration',[1.9,2,2.1])
def test_video_duration_accepts_frame_rounding_and_common_timestamp_origin(duration):
    source={'video':{'start':2,'end':4,'segments':[(2,4)]},'audio':{'end':4}}
    output={'video':{'start':0,'end':duration,'segments':[(0,duration)]},'audio':{'end':2}}
    assert validate_video_coverage(source,output,.1)['verified']


@pytest.mark.parametrize('segments',[
    [(0,1)], [(0,.5),(1,2)], [(0,2.11)],
])
def test_video_missing_tail_or_internal_coverage_is_not_accredited_by_audio(segments):
    source={'video':{'start':0,'end':2,'segments':[(0,2)]},'audio':{'end':2}}
    output={'video':{'start':0,'end':segments[-1][1],'segments':segments},'audio':{'end':2}}
    with pytest.raises(ValueError,match='Vídeo'):
        validate_video_coverage(source,output,.1)


def test_shifted_audio_requires_real_silence_evidence():
    with pytest.raises(ValueError,match='A/V'):
        validate_alignment(timeline(),timeline(intervals=((.6,1.6),)),lambda *args:{"silent":False})


def test_internal_gap_can_only_be_filled_with_verified_silence():
    source=timeline(intervals=((0,.4),(.8,1)))
    with pytest.raises(ValueError,match='A/V'):
        validate_alignment(source,timeline(),lambda *args:{"silent":False})
    accepted=validate_alignment(source,timeline(),lambda *args:{"silent":True,"peak_dbfs":"-inf"})
    checks=accepted['silence_checks']
    assert len(checks)==1 and checks[0]['side']=='output'
    assert checks[0]['relative_start']>.4 and checks[0]['relative_end']<.8


@pytest.mark.parametrize('source,output',[
    (timeline(2,((2,3),)),timeline()),
    (timeline(),timeline(intervals=((-1024/44100,1+1024/44100),))),
])
def test_common_origin_and_aac_rounding_do_not_require_silence_guessing(source,output):
    def forbidden(*args):pytest.fail('No debe adivinar silencio para tiempos equivalentes')
    assert validate_alignment(source,output,forbidden)['verified']


@pytest.mark.parametrize('fault',['nan','missing_audio','zero_duration','non_increasing'])
def test_incomplete_decoded_timeline_is_rejected(fault):
    data={"streams":[{"index":0,"codec_type":"video"},{"index":1,"codec_type":"audio","sample_rate":"48000"}],
          "frames":[{"media_type":"video","stream_index":0,"best_effort_timestamp_time":"0","duration_time":"1"},
                    {"media_type":"audio","stream_index":1,"best_effort_timestamp_time":"0","duration_time":"1","nb_samples":48000}]}
    if fault=='nan':data['frames'][1]['best_effort_timestamp_time']='nan'
    if fault=='missing_audio':data['frames'].pop()
    if fault=='zero_duration':data['frames'][1]['duration_time']='0'
    if fault=='non_increasing':data['frames'].append(copy.deepcopy(data['frames'][1]))
    with pytest.raises(ValueError):presentation(data)


@pytest.mark.parametrize('proof',[{}, {'verified':True,'method':'decoded-presentation:v1'}])
def test_resume_revalidates_legacy_ready_video_operation_before_publication(config_file,monkeypatch,proof):
    from dataclasses import asdict
    from pathlib import Path
    from media_library.models import StageResult,State
    from media_library.stages import Adapter
    from media_library.state import RunStore
    from media_library.video_driver import VideoDriver,VideoValidationError
    from pipeline_support import configure,media,run,report,PNG
    configure(config_file,modes={'compression':'auto','installation':'auto'})
    config_file.write_text(config_file.read_text()+'\n[video]\nquality_reviewed=true\n')
    media(config_file)
    class LegacyVideo(Adapter):
        identity='legacy-video-test';simulated=True
        def run(self,context):
            plan={'source':context.entry.current_path,'action':'encode',
                  'destination':str(Path(context.entry.current_path).with_name('derived.mp4'))}
            def produce(path):path.write_bytes(b'synthetic old candidate')
            artifact=context.executor.prepare(context.file_id,produce,
                lambda path:{'video':{'plan':plan,'dates':{'targets':{'synthetic':'date'}},'av_timing':proof}})
            return StageResult(State.COMPLETED,evidence={'artifact':asdict(artifact)})
    commit=RunStore.commit;fired=False
    def interrupt(store,event,*args,**kwargs):
        nonlocal fired
        commit(store,event,*args,**kwargs)
        data=kwargs.get('evidence',{}).get('pipeline',{})
        if event=='pipeline_checkpoint' and not fired and any(v['stages']['installation'].get('ready') for v in data.get('files',{}).values()):
            fired=True;raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(VideoDriver,'validate',lambda *args:{'simulated_legacy_verifier':True})
        patch.setattr(RunStore,'commit',interrupt)
        assert run(config_file,'--apply',adapters={'compression':LegacyVideo()})==130
    old=report(config_file);assert fired
    def reject(*args):raise VideoValidationError('A/V: synthetic legacy shift')
    monkeypatch.setattr(VideoDriver,'validate',reject)
    assert run(config_file,'--resume',old['run_id'],adapters={'compression':LegacyVideo()})==3
    assert (config_file.parent/'source/a/same.PNG').read_bytes()==PNG
    assert not (config_file.parent/'source/a/derived.mp4').exists()
