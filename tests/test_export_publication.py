"""Renovación recuperable sobre bytes sintéticos: no es prueba de un codec."""

from pathlib import Path

import pytest

from media_library.filesystem import ConflictError, fingerprint
from media_library.operations import SafeExecutor
from media_library.state import RunStore


@pytest.mark.parametrize("boundary",["operation_intent","backup_verified","publish_intent","published","operation_completed"])
def test_owned_export_refresh_preserves_previous_and_resumes(execution,monkeypatch,boundary):
    executor,file_id=execution
    source=Path(executor.store.entry(file_id).current_path);original=source.read_bytes()
    target=executor.config.export/'2026'/'album'/'same.jpg';target.parent.mkdir(parents=True);target.write_bytes(b'old partial derivative')
    previous=fingerprint(target)
    def produce(path):path.write_bytes(b'new validated derivative')
    artifact=executor.prepare(file_id,produce,lambda p:{"synthetic":True})
    op=executor.plan(file_id,'export',artifact=artifact,destination=target,previous_destination=previous)
    commit=executor.store.commit
    def interrupt(event,*args,**kwargs):
        commit(event,*args,**kwargs)
        if event==boundary:raise KeyboardInterrupt
    monkeypatch.setattr(executor.store,'commit',interrupt)
    with pytest.raises(KeyboardInterrupt):executor.execute(op.operation_id)
    store=RunStore.load(executor.config,executor.store.lock,executor.store.manifest.run_id)
    assert SafeExecutor(store).execute(op.operation_id).state=='COMPLETED'
    assert target.read_bytes()==b'new validated derivative' and source.read_bytes()==original
    assert Path(op.backup).read_bytes()==b'old partial derivative'
    assert store.entry(file_id).current_path==str(source)


def test_external_edit_after_refresh_plan_is_preserved(execution):
    executor,file_id=execution
    target=executor.config.export/'same.jpg';target.parent.mkdir();target.write_bytes(b'owned derivative')
    def produce(path):path.write_bytes(b'new derivative')
    artifact=executor.prepare(file_id,produce,lambda p:{"synthetic":True})
    op=executor.plan(file_id,'export',artifact=artifact,destination=target,previous_destination=fingerprint(target))
    target.write_bytes(b'external edit')
    assert executor.execute(op.operation_id).state=='FAILED'
    assert target.read_bytes()==b'external edit' and not Path(op.backup).exists()
