"""Real OCR work is partitioned between browsers and the server without duplicate frames."""
import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from modules.frames import sampling
from modules.frames.grabber import GrabResult
from modules.screentext import ScreenText
from modules.screentext.ocr import Line
from tests.test_screentext import make_job


def test_modes_are_explicit_and_legacy_imports_keep_server():
    assert sampling.plan(None, 60).as_dict()['ocr_mode'] == 'server'
    for mode in ('hybrid', 'local', 'server'):
        assert sampling.plan({'ocr_mode': mode}, 60).ocr_mode == mode
    assert sampling.plan({'ocr_mode': 'other'}, 60).ocr_mode == 'server'


def work(tmp_path, mode='hybrid', count=6):
    from modules.screentext.hybrid import WorkSession
    job = make_job(tmp_path, count)
    job.video.extra['sampling'] = {'ocr_mode': mode, 'ocr_fps': 1}
    files=[]
    for i in range(count):
        p=job.root / f'{i+1:05d}.jpg'; p.write_bytes(b'jpg'); files.append(p)
    return job, WorkSession(job, files, 1, mode)


def result(frame, text='课程文字'):
    return {'id': frame['id'], 'lines': [{'text': text, 'confidence': .98, 'x': .1, 'y': .2, 'w': .5, 'h': .1}]}


def test_browser_lease_excludes_server_and_replies_are_idempotent(tmp_path):
    _, w = work(tmp_path)
    lease = w.claim('browser')
    assert lease['state'] == 'ready' and len(lease['frames']) == 1
    server = w.take_server(2)
    assert not ({f['id'] for f in lease['frames']} & set(server))
    payload = [result(lease['frames'][0])]
    assert w.submit('browser', lease['lease_id'], payload) == 1
    assert w.submit('browser', lease['lease_id'], payload) == 0
    assert w.progress()['local'] == 1 and w.progress()['done'] == 1
    next_lease=w.claim('browser')
    assert len(next_lease['frames']) == 2


def test_expired_lease_is_reclaimed_and_stale_result_cannot_override(tmp_path, monkeypatch):
    import modules.screentext.hybrid as hybrid
    clock=[0.]
    monkeypatch.setattr(hybrid, 'now', lambda:clock[0])
    _, w = work(tmp_path)
    lease=w.claim('browser')
    clock[0]=hybrid.LEASE_SECONDS+1
    w.reap()
    ids=w.take_server(6)
    assert lease['frames'][0]['id'] in ids
    with pytest.raises(HTTPException) as error:
        w.submit('browser',lease['lease_id'],[result(lease['frames'][0])])
    assert error.value.status_code==409


def test_lease_heartbeat_has_a_hard_upper_bound(tmp_path, monkeypatch):
    import modules.screentext.hybrid as hybrid
    clock=[0.]
    monkeypatch.setattr(hybrid,'now',lambda:clock[0])
    _,w=work(tmp_path)
    lease=w.claim('browser')
    clock[0]=hybrid.LEASE_SECONDS/2
    w.heartbeat('browser',lease['lease_id'])
    clock[0]=hybrid.MAX_LEASE_SECONDS+1
    w.reap()
    assert lease['frames'][0]['id'] in w.take_server(6)


def test_local_uses_browser_results_and_never_calls_server_ocr(tmp_path):
    from modules.screentext.task import run_screentext
    job=make_job(tmp_path,duration=3)
    job.video.extra['sampling']={'ocr_mode':'local','ocr_fps':1}
    async def read(stream,folder,timeout):
        folder.mkdir(parents=True,exist_ok=True)
        for i in range(1,4): (folder/f'{i:05d}.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    def forbidden(_): raise AssertionError('local mode must not execute server OCR')
    async def go():
        task=asyncio.create_task(run_screentext(job,read=read,recognize=forbidden))
        for _ in range(100):
            w=getattr(job,'_ocr_work',None)
            if w is not None: break
            await asyncio.sleep(.001)
        assert w is not None
        while not w.complete:
            lease=w.claim('browser')
            w.submit('browser',lease['lease_id'],[result(f,f"课程知识点{f['id']}") for f in lease['frames']])
            await asyncio.sleep(.001)
        await asyncio.wait_for(task,1)
    asyncio.run(go())
    assert job.screentext.status=='done',job.screentext.message
    assert job.screentext.summary()['processing']=={'mode':'local','done':3,'total':3,'local':3,'server':0}
    assert max(c.end for c in job.screentext.segments)==3
    assert not (job.root/'screentext').exists()


def test_local_model_failure_fails_quickly_without_server_fallback(tmp_path):
    from modules.screentext.hybrid import ClientOCRService
    job,w=work(tmp_path,'local')
    job._ocr_work=w
    service=ClientOCRService(lambda _:job)
    service.release('j',{'client_id':'browser','reason':'model_error'})
    assert w.client_error


def test_api_rejects_foreign_jobs_bad_coordinates_and_foreign_frames(tmp_path):
    from modules.screentext.hybrid import ClientOCRService
    job,w=work(tmp_path)
    job._ocr_work=w
    def owned(job_id):
        if job_id!='j': raise HTTPException(403,'not owner')
        return job
    api=FastAPI();api.include_router(ClientOCRService(owned).router)
    with TestClient(api) as client:
        assert client.post('/api/link-jobs/foreign/ocr/claim',json={'client_id':'browser'}).status_code==403
        lease=client.post('/api/link-jobs/j/ocr/claim',json={'client_id':'browser'}).json()
        bad=result(lease['frames'][0]);bad['lines'][0]['x']=2
        assert client.post('/api/link-jobs/j/ocr/result',json={'client_id':'browser','lease_id':lease['lease_id'],'results':[bad]}).status_code==422
        bad=result({'id':999})
        assert client.post('/api/link-jobs/j/ocr/result',json={'client_id':'browser','lease_id':lease['lease_id'],'results':[bad]}).status_code==409
        assert client.get(f"/api/link-jobs/j/ocr/frames/{lease['lease_id']}/999.jpg").status_code==404
        good=client.post('/api/link-jobs/j/ocr/result',json={'client_id':'browser','lease_id':lease['lease_id'],'results':[result(lease['frames'][0])]} )
        assert good.status_code==200 and good.json()['accepted']==1

def test_local_retry_uses_the_retained_source_and_preserves_mode(tmp_path, monkeypatch):
    import app
    from modules.video_source import Stream
    job=make_job(tmp_path)
    job.video.platform='local'
    job.video.extra['sampling']={'ocr_mode':'local','ocr_fps':.5}
    job.screentext=ScreenText('failed','model error')
    job.video.streams=[]
    (job.root/'source.mp4').write_bytes(b'retained video')
    for slot in job.slots: slot.status='ok'
    monkeypatch.setattr(app,'own_job',lambda _:job)
    monkeypatch.setattr(app.chapter_service,'invalidate',lambda _:None)
    spawned=[]
    monkeypatch.setattr(app,'spawn',spawned.append)
    try:
        answer=asyncio.run(app.retry_missing(job.id))
        assert answer['screentext'] is True
        assert job.video.streams[0].url==str(job.root/'source.mp4')
        assert job.video.extra['sampling']['ocr_mode']=='local'
    finally:
        for coro in spawned:coro.close()


def test_remote_retry_refresh_keeps_the_saved_processing_plan(tmp_path, monkeypatch):
    import app
    from modules.video_source import ResolvedVideo
    job=make_job(tmp_path)
    saved={'ocr_mode':'hybrid','preset':'fine','ocr_fps':2,'shots':False}
    job.video.extra['sampling']=saved.copy()
    job.screentext=ScreenText('failed','interrupted')
    job.restored=True
    for slot in job.slots:slot.status='ok'
    async def resolve(*args):
        return None,ResolvedVideo('bilibili','BV1','url','fresh',10,[],extra={'cid':123})
    monkeypatch.setattr(app.registry,'resolve',resolve)
    monkeypatch.setattr(app,'own_job',lambda _:job)
    monkeypatch.setattr(app.chapter_service,'invalidate',lambda _:None)
    spawned=[]
    monkeypatch.setattr(app,'spawn',spawned.append)
    try:
        asyncio.run(app.retry_missing(job.id))
        assert job.video.extra['sampling']==saved
        assert job.video.extra['cid']==123
    finally:
        for coro in spawned:coro.close()


def test_hybrid_runs_browser_and_server_on_distinct_actual_ocr_samples(tmp_path):
    import threading
    from modules.screentext.task import run_screentext
    job=make_job(tmp_path,duration=8)
    job.video.extra['sampling']={'ocr_mode':'hybrid','ocr_fps':1}
    entered=threading.Event(); release=threading.Event(); recognized=[]; browser_ids=[]
    async def read(stream,folder,timeout):
        folder.mkdir(parents=True,exist_ok=True)
        for i in range(1,9): (folder/f'{i:05d}.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    def recognize(path):
        entered.set()
        assert release.wait(2)
        recognized.append(int(Path(path).stem)-1)
        return [Line(f'服务器课程内容{Path(path).stem}',.99,.1,.2,.5,.1)]
    async def go():
        task=asyncio.create_task(run_screentext(job,read=read,recognize=recognize))
        for _ in range(1000):
            if entered.is_set(): break
            await asyncio.sleep(.001)
        assert entered.is_set()
        w=job._ocr_work
        for _ in range(3):
            lease=w.claim('browser')
            assert lease['state']=='ready'
            browser_ids.extend(f['id'] for f in lease['frames'])
            w.submit('browser',lease['lease_id'],[result(f,f"本机课程内容{f['id']}") for f in lease['frames']])
            await asyncio.sleep(.001)
        assert job.screentext.segments, 'browser text should publish while the server batch is still running'
        release.set()
        await asyncio.wait_for(task,2)
    try:
        asyncio.run(go())
    finally:
        release.set()
    assert job.screentext.status=='done',job.screentext.message
    assert set(recognized).isdisjoint(browser_ids)
    assert set(recognized)|set(browser_ids)==set(range(8))
    assert job.screentext.processing['local']==4 and job.screentext.processing['server']==4


def test_cancel_cleans_browser_lease_and_sample_files(tmp_path):
    from modules.screentext.task import run_screentext
    job=make_job(tmp_path,duration=2)
    job.video.extra['sampling']={'ocr_mode':'local','ocr_fps':1}
    async def read(stream,folder,timeout):
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'00001.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    async def go():
        task=asyncio.create_task(run_screentext(job,read=read))
        for _ in range(100):
            if getattr(job,'_ocr_work',None) is not None:break
            await asyncio.sleep(.001)
        w=job._ocr_work;lease=w.claim('browser')
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        with pytest.raises(HTTPException):w.submit('browser',lease['lease_id'],[result(lease['frames'][0])])
    asyncio.run(go())
    assert job._ocr_work is None and job.screentext.status=='failed'
    assert not (job.root/'screentext').exists()


def test_hybrid_recovers_unfinished_browser_frames_after_disconnect(tmp_path,monkeypatch):
    import modules.screentext.hybrid as hybrid
    clock=[0.]
    monkeypatch.setattr(hybrid,'now',lambda:clock[0])
    _,w=work(tmp_path,count=3)
    lease=w.claim('browser')
    server=w.take_server(3)
    w.accept_server(server,[[Line('已有服务器文字',1,.1,.1,.4,.1)]]*len(server))
    assert not w.complete
    clock[0]=hybrid.LEASE_SECONDS+1
    w.reap()
    recovered=w.take_server(3)
    assert recovered==[lease['frames'][0]['id']]
    w.accept_server(recovered,[[Line('服务器接续文字',1,.1,.1,.4,.1)]])
    assert w.complete and w.progress()['server']==3


def test_local_timeout_does_not_convert_to_server_ocr(tmp_path,monkeypatch):
    import modules.screentext.hybrid as hybrid
    from modules.screentext.task import run_screentext
    monkeypatch.setattr(hybrid,'LOCAL_IDLE_TIMEOUT',.01)
    job=make_job(tmp_path,duration=1)
    job.video.extra['sampling']={'ocr_mode':'local','ocr_fps':1}
    async def read(stream,folder,timeout):
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'00001.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    def forbidden(_):raise AssertionError('local timeout must not trigger server OCR')
    asyncio.run(run_screentext(job,read=read,recognize=forbidden))
    assert job.screentext.status=='failed'
    assert '已暂停' in job.screentext.message
    assert not (job.root/'screentext').exists()


def test_result_body_is_bounded_and_completed_lease_cannot_be_read(tmp_path):
    from modules.screentext.hybrid import ClientOCRService,MAX_BODY
    job,w=work(tmp_path)
    job._ocr_work=w
    api=FastAPI();api.include_router(ClientOCRService(lambda _:job).router)
    with TestClient(api) as client:
        assert client.post('/api/link-jobs/j/ocr/result',content=b'x'*(MAX_BODY+1)).status_code==413
        lease=client.post('/api/link-jobs/j/ocr/claim',json={'client_id':'browser'}).json()
        path=lease['frames'][0]['url']
        assert client.get(path).status_code==200
        response=client.post('/api/link-jobs/j/ocr/result',json={'client_id':'browser','lease_id':lease['lease_id'],'results':[result(lease['frames'][0])]})
        assert response.status_code==200
        assert client.get(path).status_code==404


def test_local_work_does_not_wait_in_the_server_cpu_queue(tmp_path,monkeypatch):
    import app
    from modules.store import SessionStore
    job=make_job(tmp_path)
    job.video.extra['sampling']={'ocr_mode':'local'}
    monkeypatch.setattr(app,'store',SessionStore(tmp_path/'queue.sqlite3'))
    monkeypatch.setattr(app,'ocr_slots',None)
    called=[]
    async def local(j,*,server_gate):
        assert app.ocr_slots is None
        called.append(j.id)
        j.screentext.status='done'
    monkeypatch.setattr(app,'run_screentext',local)
    asyncio.run(app.read_screen(job))
    assert called==[job.id]
    assert app.ocr_slots is None


def test_refreshing_the_page_many_times_does_not_exhaust_client_slots(tmp_path):
    _,w=work(tmp_path,count=45)
    for i in range(40):
        lease=w.claim(f'browser-{i}')
        assert lease['state']=='ready'
        w.submit(f'browser-{i}',lease['lease_id'],[result(f) for f in lease['frames']])
    assert len(w.clients)<=32 and w.progress()['local']==40
    assert w.claim('browser-41')['state']=='ready'


def test_frame_address_recovery_preserves_the_chosen_ocr_plan(tmp_path):
    from types import SimpleNamespace
    from modules.video_source import ResolvedVideo,Stream
    job=make_job(tmp_path)
    plan={'ocr_mode':'local','ocr_fps':2,'preset':'fine'}
    job.video.extra['sampling']=plan.copy()
    async def refresh(video):
        return ResolvedVideo('bilibili','BV1','url','fresh',10,[Stream('fresh',{},'fresh')],extra={'cid':99})
    job.resolver=SimpleNamespace(refresh=refresh)
    assert asyncio.run(job._recover(0)) is True
    assert job.video.extra['sampling']==plan and job.video.extra['cid']==99


def test_ocr_source_refresh_preserves_hybrid_mode(tmp_path):
    from types import SimpleNamespace
    from modules.screentext.task import run_screentext
    from modules.video_source import ResolvedVideo,Stream
    job=make_job(tmp_path)
    plan={'ocr_mode':'hybrid','ocr_fps':1,'preset':'fine'}
    job.video.extra['sampling']=plan.copy()
    calls=[]
    async def read(stream,folder,timeout):
        calls.append(stream.label)
        if len(calls)<3:return GrabResult(False,'forbidden','expired')
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'00001.jpg').write_bytes(b'jpg')
        return GrabResult(True)
    async def refresh(video):
        return ResolvedVideo('bilibili','BV1','url','fresh',10,[Stream('fresh',{},'fresh')])
    job.resolver=SimpleNamespace(refresh=refresh)
    asyncio.run(run_screentext(job,read=read,recognize=lambda _:[Line('有效课程文字',1,.1,.1,.5,.1)]))
    assert job.screentext.status=='done',job.screentext.message
    assert job.video.extra['sampling']==plan
    assert job.screentext.processing['mode']=='hybrid'


def test_ocr_decoders_have_an_independent_bounded_pool(monkeypatch):
    import modules.screentext.task as task
    monkeypatch.setattr(task,'_read_slots',None)
    monkeypatch.setattr(task,'READ_SLOTS',2)
    active=[];started=[]
    async def go():
        gates=[asyncio.Event() for _ in range(3)]
        async def one(i):
            async with task.sampling_slot():
                active.append(i);started.append(i)
                assert len(active)<=2
                await gates[i].wait()
                active.remove(i)
        tasks=[asyncio.create_task(one(i)) for i in range(3)]
        await asyncio.sleep(0)
        assert started==[0,1]
        gates[0].set();await asyncio.sleep(0);await asyncio.sleep(0)
        assert started==[0,1,2]
        for gate in gates:gate.set()
        await asyncio.gather(*tasks)
    asyncio.run(go())


def test_interrupted_restore_keeps_partial_processing_counts():
    state=ScreenText.from_dict({'status':'running','message':'processing','segments':[{'start':0,'end':2,'text':'已有内容','pos':'middle'}],
        'processing':{'mode':'hybrid','done':3,'total':10,'local':1,'server':2}})
    assert state.status=='failed' and len(state.segments)==1
    assert state.processing=={'mode':'hybrid','done':3,'total':10,'local':1,'server':2}
