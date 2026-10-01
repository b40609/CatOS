'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Control}=require('../frontend/workspace/simulation.js');
const RID='a'.repeat(32), INSTANCE='b'.repeat(32);
function setup() {
  const calls=[], memory=new Map();let ids=0;
  const version={contract:'catos.simulation.v1',build_id:'build',instance_id:INSTANCE,slot:'idle',capabilities:{start:true,stop:false},active_run_id:null};
  const workspace={preview:false,restart_required:false};
  const fixture={calls,memory,version,workspace,items:[],post:null};
  const storage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
  const request=async(path,options={})=>{
    calls.push({path,options});
    if(options.method==='POST')return fixture.post?fixture.post(path,options):{run_id:RID,control_state:'starting'};
    if(path==='/api/workspace/version')return structuredClone(workspace);
    if(path.endsWith('/version'))return structuredClone(version);
    return {items:structuredClone(fixture.items)};
  };
  Object.assign(fixture,{storage,request,newControl:()=>new Control({request,storage,id:()=>String(++ids).padStart(32,'0')})});
  fixture.control=fixture.newControl();return fixture;
}
const posts=f=>f.calls.filter(c=>c.options.method==='POST');
test('initial/read refresh and restored pending command never submit',async()=>{
  const f=setup();await f.control.refresh();assert.equal(posts(f).length,0);
  f.post=()=>{throw Error('lost response');};await f.control.send('start');
  const restored=f.newControl();await restored.refresh();await restored.refresh();assert.equal(posts(f).length,1);assert.deepEqual(restored.pending,f.control.pending);
});
test('response loss retry retains exact body and build/instance headers',async()=>{
  const f=setup();await f.control.refresh();f.post=()=>{throw Error('timeout');};await f.control.send('start');
  const first=posts(f)[0];assert.ok(f.control.pending);assert.equal(f.control.reason('start'),'先確認或重送原命令');
  f.post=null;await f.control.send('retry');const second=posts(f)[1];assert.deepEqual(second,first);assert.equal(f.control.pending,null);assert.equal(f.memory.size,0);
});
test('concurrent clicks submit once',async()=>{
  const f=setup();await f.control.refresh();let release;f.post=()=>new Promise(resolve=>{release=resolve;});
  const first=f.control.send('start');await f.control.send('start');await f.control.send('retry');assert.equal(posts(f).length,1);
  release({run_id:RID,control_state:'starting'});await first;
});
test('stop uses active control run and 202 stopping is not a stopped state',async()=>{
  const f=setup();Object.assign(f.version,{slot:'running',active_run_id:RID,capabilities:{start:false,stop:true}});
  f.post=()=>({run_id:RID,control_state:'stopping',cleanup_confirmed:false});f.items=[{run_id:RID,control_state:'stopping',still_finishing:true}];
  await f.control.refresh();await f.control.send('stop');assert.equal(posts(f)[0].path,'/api/workspace/simulation/runs/'+RID+'/stop');
  assert.deepEqual(Object.keys(JSON.parse(posts(f)[0].options.body)),['request_id']);assert.equal(f.control.runs[0].control_state,'stopping');assert.equal(f.control.runs[0].still_finishing,true);
});
test('source/workspace drift blocks new start but permits existing stop',async()=>{
  const f=setup();f.workspace.restart_required=true;Object.assign(f.version,{restart_required:true,active_run_id:RID,capabilities:{start:false,stop:true}});
  await f.control.refresh();await f.control.send('start');assert.equal(posts(f).length,0);await f.control.send('stop');assert.equal(posts(f).length,1);
});
test('preview reads only workspace version, never simulation or mutation',async()=>{
  const f=setup();f.workspace.preview=true;await f.control.refresh();await f.control.send('start');await f.control.send('stop');assert.equal(f.calls.length,1);assert.match(f.control.reason('start'),/正式 8770/);
});
test('restart never rebinds an uncertain command to another instance',async()=>{
  const f=setup();await f.control.refresh();f.post=()=>{throw Error('lost');};await f.control.send('start');const command=structuredClone(f.control.pending);
  f.version.instance_id='c'.repeat(32);await f.control.refresh();await f.control.send('retry');assert.equal(posts(f).length,1);assert.deepEqual(f.control.pending,command);assert.match(f.control.reason('retry'),/人工檢查/);
});
test('recovery/unavailable and disconnected service block new commands',async()=>{
  const f=setup();f.version.slot='recovery_required';f.version.capabilities.start=false;await f.control.refresh();await f.control.send('start');assert.equal(posts(f).length,0);
  f.version.unavailable_reason='metadata_uncertain';await f.control.refresh();await f.control.send('stop');assert.equal(posts(f).length,0);
  f.control.request=async()=>{throw Error('offline');};await f.control.refresh();assert.equal(f.control.version,null);assert.equal(f.control.reason('start'),'控制服務未連線');
});
test('storage failure and corrupted command fail closed without POST',async()=>{
  const f=setup();await f.control.refresh();f.storage.setItem=()=>{throw Error('quota');};await f.control.send('start');assert.equal(posts(f).length,0);
  f.memory.set('catos_simulation_pending_v1','{"path":"https://example.invalid"}');const other=f.newControl();await other.refresh();await other.send('start');assert.equal(posts(f).length,0);assert.equal(other.storageError,true);
});
test('HTTP rejection/malformed reply retains command, manual retry only',async()=>{
  const f=setup();await f.control.refresh();f.post=()=>{throw Error('HTTP 503');};await f.control.send('start');await f.control.refresh();assert.equal(posts(f).length,1);
  f.post=()=>({run_id:'invalid',control_state:'completed'});await f.control.send('retry');assert.ok(f.control.pending);assert.equal(posts(f)[0].options.body,posts(f)[1].options.body);
});
test('Decimal strings and history pass through unchanged',async()=>{
  const f=setup();f.items=[{run_id:RID,control_state:'completed',cleanup_confirmed:true,last_fill:{price:'101.0000000000000000001',fee:'0.00000000000000000001'}}];await f.control.refresh();assert.deepEqual(f.control.runs,f.items);assert.equal(posts(f).length,0);
});
