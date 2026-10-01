/* Explicit commands only; page lifecycle never owns the backend task. */
'use strict';
((root) => {
  const prefix='/api/workspace/simulation', key='catos_simulation_pending_v1';
  const validId=x=>typeof x==='string'&&/^[0-9a-f]{32}$/.test(x);
  const states={idle:'可啟動',starting:'啟動中',running:'運行中',stopping:'停止中',completed:'已完成',stopped:'已停止',failed:'失敗',recovery_required:'需人工檢查',unavailable:'控制服務不可用'};
  function validCommand(c) {
    return c && validId(c.body?.request_id) && typeof c.build==='string' && validId(c.instance) &&
      ((c.path===prefix+'/start'&&Object.keys(c.body).length===2&&c.body.template_id==='sma-synthetic-smoke-v1') ||
       (new RegExp('^'+prefix+'/runs/[0-9a-f]{32}/stop$').test(c.path)&&Object.keys(c.body).length===1));
  }
  class Control {
    constructor({request,storage,id}) {
      Object.assign(this,{request,storage,id,version:null,workspace:null,runs:[],pending:null,busy:false,reading:false,error:'',storageError:false});
      try {const saved=JSON.parse(storage.getItem(key)||'null');if(saved&&!validCommand(saved))throw Error();this.pending=saved;}
      catch {this.storageError=true;this.error='命令保存資料無法讀取，禁止建立新命令';}
    }
    reason(operation) {
      if(this.busy)return '提交中';
      if(this.storageError)return '命令保存不可用';
      if(this.workspace?.preview)return '預覽僅可閱讀；請至正式 8770 操作';
      if(!this.version||!this.workspace)return '控制服務未連線';
      if(this.version.unavailable_reason)return '控制服務不可用：'+this.version.unavailable_reason;
      if(this.pending) return operation==='retry' ? (this.pending.instance===this.version.instance_id&&this.pending.build===this.version.build_id?'':'服務已更換，保留原命令供人工檢查') : '先確認或重送原命令';
      if(operation==='start'&&(this.workspace.restart_required||this.version.restart_required))return '服務版本待更新';
      return this.version.capabilities?.[operation]===true?'':(states[this.version.slot]||'操作不可用');
    }
    async refresh() {
      if(this.reading)return;
      this.reading=true;
      try {
        const workspace=await this.request('/api/workspace/version');this.workspace=workspace;
        if(workspace.preview){this.version=null;this.runs=[];return;}
        const [version,runs]=await Promise.all([this.request(prefix+'/version'),this.request(prefix+'/runs')]);
        if(version.contract!=='catos.simulation.v1'||!validId(version.instance_id)||typeof version.build_id!=='string'||!Array.isArray(runs.items))throw Error('控制回覆格式不符');
        this.version=version;this.runs=runs.items;
      } catch(e) {this.version=null;this.error='狀態讀取失敗：'+e.message;}
      finally {this.reading=false;}
    }
    async send(operation) {
      if(!['start','stop','retry'].includes(operation))return;
      const reason=this.reason(operation);if(reason){this.error=reason;return;}
      if(!this.pending) {
        const body={request_id:this.id()};
        let path=prefix+'/start';
        if(operation==='start')body.template_id='sma-synthetic-smoke-v1';
        else {if(!validId(this.version.active_run_id)){this.error='無可停止案例';return;}path=prefix+'/runs/'+this.version.active_run_id+'/stop';}
        const command={path,body,build:this.version.build_id,instance:this.version.instance_id};
        try {this.storage.setItem(key,JSON.stringify(command));this.pending=command;}
        catch {this.storageError=true;this.error='命令保存失敗，未提交';return;}
      }
      this.busy=true;this.error='';
      try {
        const c=this.pending;
        const run=await this.request(c.path,{method:'POST',headers:{'Content-Type':'application/json','X-CatOS-Build':c.build,'X-CatOS-Instance':c.instance},body:JSON.stringify(c.body)});
        if(!validId(run.run_id)||!(run.control_state in states))throw Error('命令回覆格式不符');
        this.runs=[run,...this.runs.filter(r=>r.run_id!==run.run_id)];
        // Persisted command is removed only after a confirmed response; GET never submits it.
        this.storage.removeItem(key);this.pending=null;
      } catch(e) {this.error='命令結果未確認：'+e.message+'；保留原 ID，請重送原命令';}
      finally {this.busy=false;await this.refresh();}
    }
  }
  function mount() {
    if(root.location.pathname!=='/workspace/execution')return;
    const host=root.document.createElement('section');host.className='simulation-control';host.setAttribute('aria-label','短程合成模擬');
    host.innerHTML='<div class="simulation-actions"><strong>短程合成模擬</strong><button class="gold-button" data-sim="start">啟動短程模擬</button><button class="plain" data-sim="stop">停止模擬</button><button class="plain" data-sim="retry" hidden>重送原命令</button><span data-sim-status role="status" aria-live="polite"></span></div><p>固定 SMA · 2 根預熱＋8 根合成 15m K 線 · 每根間隔 1 秒。完成目前事件後停止，保留部位；切頁、刷新或關頁不會停止。</p><p data-sim-note role="status"></p><details><summary>最新案例與事件</summary><select data-sim-select aria-label="選擇短程模擬案例"></select><pre data-sim-detail></pre></details>';
    root.document.getElementById('page-controls').after(host);
    const request=async(path,options={})=>{
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
      try {const response=await root.fetch(path,{cache:'no-store',...options,signal:controller.signal});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'HTTP '+response.status);return data;}
      finally {clearTimeout(timer);}
    };
    const storage={getItem:k=>root.sessionStorage.getItem(k),setItem:(k,v)=>root.sessionStorage.setItem(k,v),removeItem:k=>root.sessionStorage.removeItem(k)};
    const control=new Control({request,storage,id:()=>root.crypto.randomUUID().replaceAll('-','')});
    let selected=null;
    const select=host.querySelector('[data-sim-select]');
    function render() {
      host.querySelectorAll('[data-sim]').forEach(b=>{const op=b.dataset.sim;b.hidden=op==='retry'&&!control.pending;const reason=control.reason(op);b.disabled=!!reason;b.title=reason;});
      const active=control.runs.find(r=>r.run_id===control.version?.active_run_id)||control.runs[0];
      host.querySelector('[data-sim-status]').textContent=control.workspace?.preview?'預覽唯讀':control.version?(states[control.version.slot]||'不可用')+(active?' · '+(states[active.control_state]||'—')+' · '+active.bars+'/8 根 · '+active.fills+' 成交'+(active.still_finishing?' · 仍在收尾':''):''):'未連線';
      host.querySelector('[data-sim-note]').textContent=control.workspace?.preview?'請至 http://127.0.0.1:8770/workspace/execution 操作':control.error||(control.pending?'保留原命令，等待確認／手動重送':control.reason('start'));
      const options=control.runs.map(r=>{const option=root.document.createElement('option');option.value=r.run_id;option.textContent=r.run_id.slice(0,8)+' · '+(states[r.control_state]||'—');return option;});select.replaceChildren(...options);
      if(!control.runs.some(r=>r.run_id===selected))selected=active?.run_id;
      select.value=selected||'';select.disabled=!control.runs.length;
      const run=control.runs.find(r=>r.run_id===selected);
      host.querySelector('[data-sim-detail]').textContent=run?JSON.stringify({run_id:run.run_id,state:run.control_state,cleanup_confirmed:run.cleanup_confirmed,warmup_bars:run.warmup_bars,last_signal:run.last_signal,last_fill:run.last_fill,error:run.error,events:run.events},null,2):'尚無短程模擬案例';
    }
    host.addEventListener('click',async e=>{const op=e.target.closest('[data-sim]')?.dataset.sim;if(!op)return;const task=control.send(op);render();await task;render();});
    select.addEventListener('change',()=>{selected=select.value;render();});
    async function refresh(){await control.refresh();render();}
    root.document.getElementById('refresh').addEventListener('click',refresh);
    render();refresh();root.setInterval(()=>{if(!root.document.hidden)refresh();},1000);
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={Control,validCommand};
  else mount();
})(typeof window==='undefined'?globalThis:window);
