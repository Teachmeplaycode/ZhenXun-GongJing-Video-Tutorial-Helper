import test from 'node:test'
import assert from 'node:assert/strict'
import { createClientOcrManager, OcrWorkerPool, ocrUrl } from '../src/lib/clientOcrCore.js'
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms))
async function until(check, max = 1500) { const end = Date.now() + max; while (!check()) { if (Date.now() > end) throw Error('timed out'); await tick(5) } }
class Worker {
 constructor({fail = false,hold = false}={}) { Object.assign(this,{fail,hold,messages:[],terminated:false}) }
 postMessage(m) { this.messages.push(m); if (m.type==='detect'&&this.hold)return; queueMicrotask(()=>this.onmessage?.({data:{id:m.id,result:m.type==='init'?null:[{text:'数据结构',confidence:.99,x:.1,y:.1,w:.6,h:.2}],elapsed:10,...(this.fail?{error:'模型下载失败'}:{})}})) }
 terminate(){this.terminated=true}
}
const json=(v)=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}})
function setup({fail,hold,failResult=0,accepted=1}={}) {
 const worker=new Worker({fail,hold}), calls=[]; let claims=0, failures=failResult
 const manager=createClientOcrManager({workerFactory:()=>worker,apiBase:'/ZhenXun',assetBase:'http://localhost/ocr/',supported:()=>true,hidden:()=>false,events:null,visibility:null,pollMs:1,idleMs:10,
 fetch:async(url,options={})=>{const body=options.body?JSON.parse(options.body):null;calls.push({url,body});if(url.endsWith('/claim'))return json(++claims===1?{state:'ready',mode:'hybrid',lease_id:'lease',lease_seconds:20,frames:[{id:0,time:0,url:'/api/link-jobs/job/ocr/frames/lease/0.jpg'}]}:{state:'done',mode:'hybrid'});if(url.endsWith('/result')){if(failures-->0)throw TypeError('network');return json({accepted})}if(url.endsWith('/release')||url.endsWith('/heartbeat'))return json({state:'ready'});return new Response(new Uint8Array([1,2,3]))}})
 return {manager,worker,calls}
}
test('API base is applied once',()=>{assert.equal(ocrUrl('/api/x','/ZhenXun/'),'/ZhenXun/api/x');assert.equal(ocrUrl('/ZhenXun/api/x','/ZhenXun'),'/ZhenXun/api/x')})
test('server mode never initializes worker',async()=>{const x=setup();x.manager.start('job',{mode:'server'});await tick();assert.equal(x.worker.messages.length,0);assert.equal(x.calls.length,0);x.manager.close()})
test('submission retries without repeating inference, accepts idempotent 0',async()=>{const x=setup({failResult:1,accepted:0});let done=false;x.manager.start('job',{onStatus:s=>done=s.phase==='done'});await until(()=>done);const results=x.calls.filter(c=>c.url.endsWith('/result'));assert.equal(results.length,2);assert.deepEqual(results[0].body,results[1].body);assert.equal(x.worker.messages.filter(m=>m.type==='detect').length,1);assert.ok(x.calls.every(c=>c.url.startsWith('/ZhenXun/')));x.manager.close()})
test('duplicate subscribers and StrictMode remount share one active lease',async()=>{const x=setup({hold:true});const first=x.manager.start('job');first();const second=x.manager.start('job');const third=x.manager.start('job');await until(()=>x.worker.messages.some(m=>m.type==='detect'));second();await tick();assert.equal(x.worker.terminated,false);assert.equal(x.calls.filter(c=>c.url.endsWith('/claim')).length,1);third();await until(()=>x.worker.terminated);await until(()=>x.calls.some(c=>c.url.endsWith('/release')));assert.equal(x.calls.filter(c=>c.url.endsWith('/result')).length,0);x.manager.close()})
test('model error releases before claiming work',async()=>{const x=setup({fail:true});let status;x.manager.start('job',{mode:'local',onStatus:s=>status=s});await until(()=>x.calls.some(c=>c.url.endsWith('/release')));assert.equal(x.calls.some(c=>c.url.endsWith('/claim')),false);assert.equal(status.phase,'error');assert.equal(x.calls.at(-1).body.reason,'model_error');x.manager.close()})
test('closing busy pool rejects queued work immediately',async()=>{const worker=new Worker({hold:true}),pool=new OcrWorkerPool(()=>worker,{idleMs:10});const a=pool.run('detect',{buffer:new ArrayBuffer(1)},null,1000).catch(e=>e.name),b=pool.run('detect',{buffer:new ArrayBuffer(1)},null,1000).catch(e=>e.name);pool.close();assert.deepEqual(await Promise.race([Promise.all([a,b]),tick(100).then(()=>'pending')]),['AbortError','AbortError']);assert.equal(worker.messages.length,1)})
test('stalled claim times out and releases session',async()=>{const worker=new Worker(),calls=[];const manager=createClientOcrManager({workerFactory:()=>worker,supported:()=>true,hidden:()=>false,events:null,visibility:null,assetBase:'http://localhost/ocr/',requestTimeout:20,idleMs:10,fetch:async(url,o)=>{calls.push(url);if(url.endsWith('/release'))return json({});return new Promise((r,j)=>o.signal.addEventListener('abort',()=>j(new DOMException('timeout','AbortError')),{once:true}))}});manager.start('job');await until(()=>calls.some(u=>u.endsWith('/release')),200);manager.close()})
test('BFCache return resumes existing subscribers without switching local mode',async()=>{
 const events=new EventTarget(),calls=[],workers=[];let count=0
 const manager=createClientOcrManager({events,visibility:null,hidden:()=>false,supported:()=>true,assetBase:'http://localhost/ocr/',idleMs:10,
 workerFactory:()=>{const w=new Worker({hold:true});workers.push(w);return w},fetch:async(url,o={})=>{
  const body=o.body?JSON.parse(o.body):null;calls.push({url,body})
  if(url.endsWith('/claim'))return json({state:'ready',mode:'local',lease_id:`lease${++count}`,lease_seconds:20,frames:[{id:0,time:0,url:'/frame.jpg'}]})
  if(url.endsWith('/release'))return json({state:'ready'})
  return new Response(new Uint8Array([1,2,3]))
 }})
 const stop=manager.start('job',{mode:'local'})
 await until(()=>workers[0]?.messages.some(m=>m.type==='detect'))
 const hide=new Event('pagehide');Object.defineProperty(hide,'persisted',{value:true});events.dispatchEvent(hide)
 await until(()=>workers[0].terminated)
 const show=new Event('pageshow');Object.defineProperty(show,'persisted',{value:true});events.dispatchEvent(show)
 await until(()=>workers[1]?.messages.some(m=>m.type==='detect'))
 assert.equal(calls.filter(c=>c.url.endsWith('/claim')).length,2)
 assert.ok(calls.some(c=>c.url.endsWith('/release')&&c.body.lease_id==='lease1'&&c.body.reason==='hidden'))
 stop();await until(()=>workers[1].terminated);manager.close()
})
