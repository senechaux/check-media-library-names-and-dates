"""Protocolo/estado con transporte local simulado; no compatibilidad con Google Photos."""

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import copy

import pytest

from media_library.config import load_config,ConfigError
from media_library.delivery_stage import DeliveryAdapter
from media_library.export_stage import ExportAdapter
from media_library.filesystem import fingerprint
from media_library.inventory import inventory
from media_library.operations import SafeExecutor
from media_library.stages import StageContext
from media_library.state import RunStore,SourceLock
from pipeline_support import configure
from media_library.pipeline import Pipeline
from delivery_support import delivery_toml,FAKE_SECRET


@pytest.fixture
def delivery_case(config_file,monkeypatch,tmp_path):
    stack=ExitStack()
    monkeypatch.setattr(ExportAdapter,'validate_derivative',lambda *a:{"simulated_unit_validator":True})
    def create(*,mode='configured-cli',behavior='receipts',backup=True,complete=True):
        configure(config_file,modes={"delivery":"disabled"})
        counter=delivery_toml(config_file,mode=mode,behavior=behavior,backup=backup)
        config=load_config(config_file)
        source=config.source/'photo.PNG';source.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')
        entries,_=inventory(config);file_id=entries[0].file_id
        config.export.mkdir();output=config.export/'album.jpg';output.write_bytes(b'synthetic exported bytes')
        sha=fingerprint(output)['sha256']
        lock=stack.enter_context(SourceLock(config.source,registry=tmp_path/'locks'))
        store=RunStore.create(config,lock,entries)
        def pipeline(store,data):
            p=SimpleNamespace(store=store,data=data,executor=SafeExecutor(store))
            p.save=lambda **kwargs:Pipeline.save(p,**kwargs)
            p.context=lambda stage,key,record:StageContext(p,stage,key,record)
            p.mode=lambda stage:'auto' if mode=='configured-cli' else 'manual'
            return p
        records={"export":{"state":"COMPLETED","evidence":{"export":{"validation":{},"path":str(output),"sha256":sha}}},
                 "audit":{"state":"COMPLETED"},"delivery":{"state":"PLANNED","decisions":{}}}
        data={"files":{file_id:{"replan":False,"stages":records}},"coverage":{"local_complete":complete,
            "exported":[{"file_id":file_id,"identity":"logical-photo","relative":"album.jpg","path":str(output),"sha256":sha,"recipe_key":"r1","date_known":True}]}}
        p=pipeline(store,data);p.save()
        def context():return StageContext(p,'delivery',file_id,p.data['files'][file_id]['stages']['delivery'])
        def reload():
            nonlocal p
            loaded=RunStore.load(config,lock,store.manifest.run_id)
            data=copy.deepcopy(next(e['evidence']['pipeline'] for e in reversed(loaded.manifest.events) if 'pipeline' in e.get('evidence',{})))
            p=pipeline(loaded,data)
            return context()
        return context(),counter,reload
    yield create
    stack.close()


def fork_delivery(context, *, run_id=None):
    """Otra ejecución del mismo alcance; conserva solo su inventario/validación sintética."""
    from unittest.mock import patch
    from uuid import UUID
    from contextlib import nullcontext
    ids=patch('media_library.state.uuid.uuid4',return_value=UUID(hex=run_id)) if run_id else nullcontext()
    with ids:
        store=RunStore.create(context.store.config,context.store.lock,copy.deepcopy(context.store.manifest.entries))
    p=copy.copy(context.pipeline);p.store=store;p.executor=SafeExecutor(store)
    p.data=copy.deepcopy(context.pipeline.data);p.data.pop('delivery_job',None)
    p.save=lambda **kwargs:Pipeline.save(p,**kwargs)
    p.context=lambda stage,key,record:StageContext(p,stage,key,record)
    p.save()
    return StageContext(p,'delivery',context.file_id,p.data['files'][context.file_id]['stages']['delivery'])


def authorize_resolution(context,value):
    DeliveryAdapter().record_decisions(context,{'delivery_resolution':value})
    context.decisions['delivery_resolution']=value
    context.record['decision_revision']=context.record.get('decision_revision',0)+1
    context.pipeline.save()


def test_all_job_antecedents_override_stale_ready_even_when_resuming_its_owner(delivery_case,monkeypatch):
    from media_library.delivery_client import DeliveryClient
    original,counter,_=delivery_case(behavior='fail',backup=False)
    adapter=DeliveryAdapter()
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryClient,'preflight',lambda *a:(_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):adapter.run(original)
    assert original.pipeline.data['delivery_job']['state']=='READY' and not counter.exists()
    later=fork_delivery(original,run_id='f'*32)
    assert adapter.run(later).state=='WAITING_USER' and counter.read_text()=='1'
    assert later.pipeline.data['delivery_job']['state']=='UNCERTAIN'
    newest=fork_delivery(original)
    assert adapter.run(newest).state=='WAITING_USER' and counter.read_text()=='1'
    assert adapter.run(original).state=='WAITING_USER' and counter.read_text()=='1'
    authorize_resolution(newest,'delivered')
    assert adapter.run(newest).state=='COMPLETED' and counter.read_text()=='1'
    assert adapter.run(original).state=='COMPLETED' and counter.read_text()=='1'


def test_completed_job_and_unused_ready_can_be_adopted_without_duplicate_submit(delivery_case,monkeypatch):
    from media_library.delivery_client import DeliveryClient
    original,counter,_=delivery_case(backup=False)
    adapter=DeliveryAdapter()
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryClient,'preflight',lambda *a:(_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):adapter.run(original)
    later=fork_delivery(original)
    assert adapter.run(later).state=='COMPLETED' and counter.read_text()=='1'
    newest=fork_delivery(original)
    assert adapter.run(newest).state=='COMPLETED' and counter.read_text()=='1'


def test_scoped_receipts_and_private_backup_without_secret_logging(delivery_case):
    context,counter,reload=delivery_case()
    result=DeliveryAdapter().run(context)
    assert result.state=='COMPLETED' and counter.read_text()=='1'
    assert result.evidence['delivery']=='client_receipts' and not result.evidence['remote_presence_verified']
    assert result.evidence['simulated_remote'] and result.evidence['backup']['verified']
    root=Path(result.evidence['backup']['root'])
    assert (root.stat().st_mode&0o777)==0o700
    assert (root/'files/client.db').read_text()==FAKE_SECRET
    assert (root/'files/client.db').stat().st_mode&0o777==0o600
    assert FAKE_SECRET not in context.store.journal.read_text()
    assert DeliveryAdapter().run(reload()).state=='COMPLETED' and counter.read_text()=='1'


@pytest.mark.parametrize('behavior',['no-receipts','partial','fail'])
def test_command_without_complete_receipts_never_repeats_automatically(delivery_case,behavior):
    context,counter,reload=delivery_case(behavior=behavior)
    result=DeliveryAdapter().run(context)
    assert result.state=='WAITING_USER' and counter.read_text()=='1'
    result=DeliveryAdapter().run(reload())
    assert result.state=='WAITING_USER' and counter.read_text()=='1'
    assert FAKE_SECRET not in context.store.journal.read_text()


def test_zero_is_not_remote_presence_and_requires_human_declaration(delivery_case):
    context,counter,reload=delivery_case(behavior='no-receipts')
    assert DeliveryAdapter().run(context).state=='WAITING_USER'
    context=reload();context.decisions['delivery_confirmed']='true'
    result=DeliveryAdapter().validate(context)
    assert result.state=='COMPLETED' and result.evidence['human_confirmation']
    assert result.evidence['command_succeeded'] is True and result.evidence['remote_presence_verified'] is False
    assert counter.read_text()=='1'


def test_interruption_after_client_returns_is_uncertain_and_not_retried(delivery_case,monkeypatch):
    context,counter,reload=delivery_case(behavior='no-receipts')
    from media_library.delivery_client import DeliveryClient
    submit=DeliveryClient.submit
    def interrupted(client,values):
        submit(client,values);raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryClient,'submit',interrupted)
        with pytest.raises(KeyboardInterrupt):DeliveryAdapter().run(context)
    context=reload()
    assert DeliveryAdapter().run(context).state=='WAITING_USER'
    assert context.pipeline.data['delivery_job']['state']=='UNCERTAIN' and counter.read_text()=='1'


def test_backup_failure_after_delivery_retries_only_backup(delivery_case,monkeypatch):
    context,counter,reload=delivery_case()
    import media_library.delivery_backup as backup
    copy_file=backup.durable_copy;calls=0
    def fail_second(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:raise OSError('synthetic backup disk full')
        return copy_file(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(backup,'durable_copy',fail_second)
        with pytest.raises(OSError):DeliveryAdapter().run(context)
    context=reload()
    assert context.pipeline.data['delivery_job']['state']=='DELIVERED'
    assert DeliveryAdapter().run(context).state=='COMPLETED' and counter.read_text()=='1'


def test_incomplete_audit_prevents_any_client_invocation(delivery_case):
    context,counter,_=delivery_case(complete=False)
    assert DeliveryAdapter().run(context).state=='WAITING_USER' and not counter.exists()
    assert 'delivery_job' not in context.pipeline.data


def test_manual_delivery_is_explicit_and_does_not_launch_client(delivery_case):
    context,counter,_=delivery_case(mode='manual')
    assert DeliveryAdapter().run(context).state=='WAITING_USER'
    context.decisions['delivery_confirmed']='true'
    result=DeliveryAdapter().validate(context)
    assert result.state=='COMPLETED' and result.evidence['delivery']=='human_declaration'
    assert not counter.exists()


def test_empty_scope_never_starts_a_client(delivery_case):
    context,counter,_=delivery_case()
    context.pipeline.data['coverage']['exported']=[]
    result=DeliveryAdapter().run(context)
    assert result.state=='COMPLETED' and result.evidence['local_only'] and not counter.exists()


def test_explicit_not_delivered_authorizes_only_one_retry(delivery_case):
    context,counter,reload=delivery_case(behavior='fail')
    assert DeliveryAdapter().run(context).state=='WAITING_USER'
    context=reload();authorize_resolution(context,'not-delivered')
    assert DeliveryAdapter().run(context).state=='WAITING_USER' and counter.read_text()=='2'
    assert DeliveryAdapter().run(reload()).state=='WAITING_USER' and counter.read_text()=='2'
    context=reload();authorize_resolution(context,'not-delivered')
    assert DeliveryAdapter().run(context).state=='WAITING_USER' and counter.read_text()=='3'
    assert DeliveryAdapter().run(reload()).state=='WAITING_USER' and counter.read_text()=='3'


def test_retry_authorization_survives_interruption_before_submit_once(delivery_case,monkeypatch):
    from media_library.delivery_client import DeliveryClient
    context,counter,reload=delivery_case(behavior='fail',backup=False)
    adapter=DeliveryAdapter();assert adapter.run(context).state=='WAITING_USER'
    context=reload();authorize_resolution(context,'not-delivered')
    with monkeypatch.context() as patch:
        patch.setattr(DeliveryClient,'preflight',lambda *a:(_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):adapter.run(context)
    context=reload();assert context.pipeline.data['delivery_job']['state']=='READY'
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'
    assert adapter.run(reload()).state=='WAITING_USER' and counter.read_text()=='2'


def test_legacy_resolution_requires_new_explicit_authorization(delivery_case):
    context,counter,reload=delivery_case(behavior='fail',backup=False)
    adapter=DeliveryAdapter();assert adapter.run(context).state=='WAITING_USER'
    context=reload();context.decisions['delivery_resolution']='not-delivered'
    context.record['decision_revision']=2
    context.pipeline.data['delivery_job']['resolution_consumed']=[context.file_id,1]
    context.pipeline.save()
    assert adapter.run(reload()).state=='WAITING_USER' and counter.read_text()=='1'
    context=reload();authorize_resolution(context,'not-delivered')
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'


def test_unrelated_decision_does_not_renew_consumed_retry(delivery_case):
    context,counter,reload=delivery_case(behavior='fail',backup=False)
    adapter=DeliveryAdapter();assert adapter.run(context).state=='WAITING_USER'
    context=reload();authorize_resolution(context,'not-delivered')
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'
    context=reload();context.decisions['delivery_confirmed']='false';context.record['decision_revision']=2
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'


def test_export_repair_does_not_reactivate_a_consumed_delivery_resolution(delivery_case):
    context,counter,reload=delivery_case(behavior='fail')
    adapter=DeliveryAdapter();assert adapter.run(context).state=='WAITING_USER'
    context=reload();authorize_resolution(context,'not-delivered')
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'
    value=context.pipeline.data['files'][context.file_id]
    exported=copy.deepcopy(value['stages']['export']['evidence'])
    path=Path(exported['export']['path']);original=path.read_bytes();path.write_bytes(b'own partial')
    ExportAdapter().revalidate_completed(context.pipeline)
    path.write_bytes(original)  # El fixture simula la reparación local; no altera la resolución consumida.
    value['stages']['export'].update(state='COMPLETED',evidence=exported)
    value['stages']['audit']['state']='COMPLETED'
    context=StageContext(context.pipeline,'delivery',context.file_id,value['stages']['delivery'])
    assert context.record['decision_revision']==1
    assert adapter.run(context).state=='WAITING_USER' and counter.read_text()=='2'


def test_configured_cli_requires_opt_in_and_rejects_inline_secrets(config_file):
    configure(config_file,modes={"delivery":"auto"})
    delivery_toml(config_file)
    raw=config_file.read_text()
    config_file.write_text(raw.replace('allow_cli=true','allow_cli=false'))
    with pytest.raises(ConfigError):load_config(config_file)
    config_file.write_text(raw.replace('"submit"','"--token=forbidden"'))
    with pytest.raises(ConfigError):load_config(config_file)


def test_unsupported_protocol_never_runs_authentication_or_logs_output():
    from media_library.delivery_client import DeliveryClient,DeliveryClientError
    from media_library.process import ProcessResult
    calls=[]
    def runner(args,**kwargs):
        calls.append(args)
        return ProcessResult(tuple(args),0,stdout='{"protocol":"unsupported"}',stderr=FAKE_SECRET)
    client=DeliveryClient({"executable":"synthetic-client","capability_args":["caps"],"auth_args":["auth"]},runner=runner)
    with pytest.raises(DeliveryClientError) as failure:client.preflight({})
    assert len(calls)==1 and FAKE_SECRET not in str(failure.value)


@pytest.mark.parametrize('fault',['job','hash','duplicate','secret_field'])
def test_receipts_are_bound_to_job_identity_and_hash(tmp_path,fault):
    import json
    from media_library.delivery_client import read_receipts,PROTOCOL
    scope={"job_id":"job-1","files":[{"file_id":"file-1","sha256":"a"*64}]}
    receipt={"file_id":"file-1","sha256":"a"*64,"remote_id":"simulated-remote"}
    data={"protocol":PROTOCOL,"job_id":"job-1","receipts":[receipt]}
    if fault=='job':data['job_id']='different-job'
    if fault=='hash':receipt['sha256']='b'*64
    if fault=='duplicate':data['receipts'].append(dict(receipt))
    if fault=='secret_field':receipt['token']=FAKE_SECRET
    path=tmp_path/'receipt.json';path.write_text(json.dumps(data))
    assert read_receipts(path,scope) is None
