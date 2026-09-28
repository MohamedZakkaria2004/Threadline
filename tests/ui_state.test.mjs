// Pure unit tests: synthetic DOM and deferred responses, no browser automation.
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function harness() {
  const elements = new Map(), all = [], requests = [];
  class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this._text=''; this.hidden=false; this.disabled=false; this.value=''; this.className=''; this.attributes={}; this.listeners={}; this.open=false; all.push(this); }
    get textContent() { return this._text+this.children.map(c=>c.textContent||'').join(''); }
    set textContent(v) { this._text=String(v); this.children=[]; }
    get classList() { const self=this; return {contains:c=>self.className.split(' ').includes(c), add:c=>{self.className+=' '+c;}, remove:c=>{self.className=self.className.split(' ').filter(x=>x!==c).join(' ');}, toggle(c,on) {const has=this.contains(c); if(on??!has){if(!has)this.add(c);}else this.remove(c);}}; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this._text=''; this.children=children; }
    setAttribute(k,v) { this.attributes[k]=String(v); }
    getAttribute(k) { return this.attributes[k]??null; }
    removeAttribute(k) { delete this.attributes[k]; }
    addEventListener(k,fn) { this.listeners[k]=fn; }
    close() { this.open=false; }
    showModal() { this.open=true; }
    focus() { document.activeElement=this; }
    scrollIntoView() {}
    querySelector() { return null; }
  }
  const html=readFileSync('app/static/index.html','utf8');
  for(const match of html.matchAll(/id="([^"]+)"/g)){const e=new Element(); e.id=match[1]; elements.set(e.id,e);}
  const document={getElementById:id=>elements.get(id),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>all.filter(e=>selector.split(',').some(s=>s.startsWith('.')&&e.classList.contains(s.slice(1)))),addEventListener(){},activeElement:null};
  const context=vm.createContext({document,console,AbortController,FormData,Option:class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}},setTimeout,clearTimeout,crypto:{randomUUID:()=> 'unit-request'},window:{matchMedia:()=>({addEventListener(){}})},fetch:(path,options)=>new Promise(resolve=>requests.push({path,options,resolve}))});
  vm.runInContext(readFileSync('app/static/app.js','utf8'),context);
  const settle=()=>new Promise(resolve=>setImmediate(resolve));
  function respond(path,body,status=200){const i=requests.findIndex(r=>r.path===path);assert.notEqual(i,-1,`Expected request ${path}`);const [r]=requests.splice(i,1);r.resolve({ok:status<400,status,json:async()=>body});}
  return {elements,requests,run:code=>vm.runInContext(code,context),respond,settle};
}
async function initialized(){const h=harness();h.respond('/api/me',{detail:'Sign in'},401);await h.settle();return h;}

await test('late previous-account library response cannot enter the new session',async()=>{
  const h=await initialized();
  h.run("currentUser={id:'admin',role:'admin'}");
  const pending=h.run('loadDocuments()').catch(()=>{});
  h.run('showLogin(); currentUser={id:"employee",role:"employee"}');
  h.respond('/api/documents',[{id:'secret',title:'Sensitive leadership reserve',filename:'secret.md',status:'ready',department:'Operations',classification:'leadership',version:1,chunk_count:1}]);
  await pending;
  assert.equal(h.elements.get('library-list').textContent.includes('Sensitive leadership reserve'),false);
});

await test('new conversation cannot be replaced by a late saved-conversation response',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  const listing=h.run('loadConversations()');h.respond('/api/conversations',[{id:'older',title:'Older conversation'}]);await listing;
  const opening=h.elements.get('conversation-list').children[0].listeners.click();
  h.run('newChat()');
  h.respond('/api/conversations/older',[{role:'assistant',content:'STALE ANSWER',metadata:{}}]);await opening;
  assert.equal(h.elements.get('messages').textContent.includes('STALE ANSWER'),false);
  assert.equal(h.run('conversationId'),null);
});

await test('sign-out clears an open source and the question draft',async()=>{
  const h=await initialized();
  h.elements.get('source-dialog').showModal();h.elements.get('source-content').textContent='Sensitive source';h.elements.get('source-title').textContent='Restricted policy';h.elements.get('question').value='Sensitive draft';
  h.run('showLogin()');
  assert.equal(h.elements.get('source-dialog').open,false);
  assert.equal(h.elements.get('source-content').textContent,'');
  assert.equal(h.elements.get('source-title').textContent,'');
  assert.equal(h.elements.get('question').value,'');
});

await test('an old unauthorized response cannot sign out the new account',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  const pending=h.run('loadDocuments()').catch(error=>assert.match(error.message,/account changed/));
  h.run('showLogin(); currentUser={id:"employee",role:"employee"}');
  h.respond('/api/documents',{detail:'Expired old session'},401);await pending;
  assert.equal(h.run('currentUser.id'),'employee');
});

await test('an old chat response cannot restore the previous account draft',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  const pending=h.run("sendQuestion('Sensitive administrator question')");
  h.run('showLogin(); currentUser={id:"employee",role:"employee"}');
  h.respond('/api/chat',{answer:'Sensitive answer',conversation_id:'old',citations:[]});await pending;
  assert.equal(h.elements.get('question').value,'');
  assert.equal(h.elements.get('messages').textContent,'');
  assert.equal(h.run('conversationId'),null);
});

await test('a library-load error is visible after successful authentication',async()=>{
  const h=await initialized();
  const pending=h.run("enterApp({id:'employee',name:'Aisha Khan',role:'employee',department:'IT'})").catch(()=>{});
  h.respond('/api/health',{status:'ready',model:'local',embedding_model:'local',missing:[]});
  h.respond('/api/conversations',[]);
  h.respond('/api/documents',{detail:'Library temporarily unavailable'},500);
  await pending;
  assert.equal(h.elements.get('app-view').hidden,false);
  assert.match(h.elements.get('banner').textContent,/Library temporarily unavailable/);
});

await test('late operations response cannot reveal the previous account requests',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  const pending=h.run('loadOperations()').catch(()=>{});
  h.run('showLogin(); currentUser={id:"employee",role:"employee"}');
  h.respond('/api/operations',{tickets:[{title:'Confidential admin ticket'}],approvals:[],reports:[],workflows:[]});await pending;
  assert.equal(h.elements.get('operations-list').textContent,'');
  assert.equal(h.run('operationData'),null);
});

await test('a late report response cannot open a dialog after sign-out',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  const pending=h.run("openReport('rpt-1')");h.run('showLogin()');
  h.respond('/api/reports/rpt-1',{title:'Restricted report',markdown:'Secret content'});await pending;
  assert.equal(h.elements.get('report-dialog').open,false);
  assert.equal(h.elements.get('report-content').textContent,'');
});

await test('newer Operations refresh wins over an older delayed response',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}");
  const older=h.run('loadOperations()'), newer=h.run('loadOperations()');
  const req=h.requests.splice(h.requests.findLastIndex(r=>r.path==='/api/operations'),1)[0];
  req.resolve({ok:true,status:200,json:async()=>({tickets:[],approvals:[],reports:[],workflows:[]})});await newer;
  h.respond('/api/operations',{tickets:[{title:'Stale request'}],approvals:[],reports:[],workflows:[]});await older;
  assert.equal(h.elements.get('operations-list').textContent.includes('Stale request'),false);
});

await test('requester sees pending review without approval controls',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; operationTab='approvals'");
  const pending=h.run('loadOperations()');
  h.respond('/api/operations',{tickets:[],reports:[],workflows:[],approvals:[{id:'review-1',requester:'Aisha',department:'IT',created_at:'2026-09-27T10:00:00Z',status:'pending',input:'Request access to planning',reason:'Human review required',plan:{title:'Planning',tool:'request_access',priority:'normal'},can_review:false}]});await pending;
  const content=h.elements.get('operations-list').textContent;
  assert.match(content,/You cannot approve your own request/);
  assert.equal(content.includes('Approve & create ticket'),false);
});

await test('double approval submission sends only one decision',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; operationTab='approvals'");
  const pending=h.run('loadOperations()');
  h.respond('/api/operations',{tickets:[],reports:[],workflows:[],approvals:[{id:'review-1',requester:'Aisha',department:'IT',created_at:'2026-09-27T10:00:00Z',status:'pending',input:'Request access to planning',reason:'Human review required',plan:{title:'Planning',tool:'request_access',priority:'normal'},can_review:true}]});await pending;
  const card=h.elements.get('operations-list').children[0],form=card.children.find(e=>e.tagName==='form');
  const input=form.children[0].children[0]; input.value='Reviewed business need';
  const event={preventDefault(){},submitter:{value:'approve'}};
  const first=form.listeners.submit(event);await form.listeners.submit(event);
  assert.equal(h.requests.filter(r=>r.path==='/api/approvals/review-1/decision').length,1);
  h.respond('/api/approvals/review-1/decision',{status:'completed'});await h.settle();
  h.respond('/api/operations',{tickets:[],approvals:[],reports:[],workflows:[]});await first;
});

await test('uncertain action retry reuses its idempotency key and mode',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; setMode('agent')");
  const first=h.run("sendQuestion('Create a support ticket for a monitor.')");
  const firstPayload=JSON.parse(h.requests.find(r=>r.path==='/api/chat').options.body);
  assert.equal(firstPayload.mode,'agent');
  h.respond('/api/chat',{detail:'Uncertain server response'},500);await h.settle();
  h.respond('/api/conversations',[]);await h.settle();
  h.respond('/api/health',{status:'ready',model:'local',embedding_model:'local',missing:[]});await first;
  assert.equal(h.run('pendingSubmission.request_id'),firstPayload.request_id);
  const second=h.run("sendQuestion('Create a support ticket for a monitor.')");
  const secondPayload=JSON.parse(h.requests.find(r=>r.path==='/api/chat').options.body);
  assert.deepEqual(secondPayload,firstPayload);
  h.respond('/api/chat',{answer:'Created ticket',conversation_id:'conversation-1',citations:[]});await h.settle();
  h.respond('/api/conversations',[]);await h.settle();
  h.respond('/api/health',{status:'ready',model:'local',embedding_model:'local',missing:[]});await second;
  assert.equal(h.run('pendingSubmission'),null);
});

await test('a revoked or unsaved report opens the Reports category, not Tickets',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; renderMessage('assistant','Report source access changed.',{tool:'generate_report',status:'completed',access_changed:true})");
  const article=h.elements.get('messages').children[0];
  const actions=article.children.find(e=>e.className==='message-actions');
  actions.children.find(e=>e.tagName==='button').listeners.click();
  h.respond('/api/operations',{tickets:[],approvals:[],reports:[],workflows:[]});await h.settle();
  assert.equal(h.elements.get('operations-view').hidden,false);
  assert.equal(h.elements.get('ops-reports').getAttribute('aria-pressed'),'true');
});

await test('a late source response cannot replace a newer selected source',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}");
  const old=h.run("openDocument('old')"), recent=h.run("openDocument('new')");
  h.respond('/api/documents/new',{document:{title:'Selected policy',filename:'new.md',version:1,department:'IT',status:'ready'},chunks:[]});await recent;
  h.respond('/api/documents/old',{document:{title:'Previous policy',filename:'old.md',version:1,department:'IT',status:'ready'},chunks:[]});await old;
  assert.equal(h.elements.get('source-title').textContent,'Selected policy');
});

await test('closing a report prevents a pending response from reopening it',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}");
  const pending=h.run("openReport('rpt-1')");h.elements.get('close-report').listeners.click();
  h.respond('/api/reports/rpt-1',{title:'Late report',markdown:'Content'});await pending;
  assert.equal(h.elements.get('report-dialog').open,false);
  assert.equal(h.elements.get('report-title').textContent,'');
});

await test('navigating away cancels a pending source dialog',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}");
  const pending=h.run("openDocument('old')");h.run('newChat()');
  h.respond('/api/documents/old',{document:{title:'Old source',filename:'old.md',version:1,department:'IT',status:'ready'},chunks:[]});await pending;
  assert.equal(h.elements.get('source-dialog').open,false);
  assert.equal(h.elements.get('source-title').textContent,'');
});

for (const close of ['button', 'escape']) {
  await test(`closing a report with ${close} cancels its pending source request`,async()=>{
    const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}");
    h.elements.get('report-dialog').showModal();
    const pending=h.run("openDocument('report-source')");
    if (close==='button') h.elements.get('close-report').listeners.click();
    else { h.elements.get('report-dialog').listeners.cancel(); h.elements.get('report-dialog').close(); }
    h.respond('/api/documents/report-source',{document:{title:'Unwanted late source',filename:'policy.md',version:1,department:'IT',status:'ready'},chunks:[]});
    await pending;
    assert.equal(h.elements.get('source-dialog').open,false);
    assert.equal(h.elements.get('source-title').textContent,'');
  });
}

await test('late platform analytics cannot enter a different account',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; insightTab='overview'");
  const pending=h.run('loadInsights()'); h.run('showLogin(); currentUser={id:"employee",role:"employee"}');
  h.respond('/api/insights?days=30&scope=mine',{requests:12345});await pending;
  assert.equal(h.elements.get('insight-metrics').textContent,'');
});

await test('late prompt registry does not appear after sign-out',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; insightTab='prompts'");
  const pending=h.run('loadInsights()');h.run('showLogin()');
  h.respond('/api/prompts',{templates:[{content:'OLD ADMIN DATA'}]});await pending;
  assert.equal(h.elements.get('prompt-inventory').textContent,'');
});

await test('leaving quality lab prevents a late run list from rendering',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; insightTab='quality'");
  const pending=h.run('loadInsights()');h.run("view('chat')");
  h.respond('/api/evaluations',[{id:'late',results:[]}]);await pending;
  assert.equal(h.elements.get('evaluation-results').textContent,'');
  assert.equal(h.run('evaluationTimer'),null);
});

await test('employees cannot open admin quality panels through navigation',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; showInsights('quality')");
  assert.equal(h.run('insightTab'),'overview');
  assert.equal(h.requests.some(r=>r.path==='/api/evaluations'),false);
  h.respond('/api/insights?days=30&scope=mine',{detail:'test complete'},500);await h.settle();
});

await test('late ROI calculation cannot replace a newly selected scenario',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; businessControls=[['employees',{value:'25'}]]");
  const pending=h.elements.get('business-form').listeners.submit({preventDefault(){}});
  h.run('businessRevision++');h.elements.get('business-results').textContent='NEW SCENARIO';
  h.respond('/api/business-case',{results:{monthly_capacity_value_usd:999},basis:'OLD'});await pending;
  assert.equal(h.elements.get('business-results').textContent,'NEW SCENARIO');
});

await test('feedback sends one write and marks the saved choice',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; renderMessage('assistant','25 days',{message_id:'answer-1',status:'completed',tool:'answer'})");
  const article=h.elements.get('messages').children[0];const group=article.children.find(e=>e.className==='feedback-controls');const button=group.children[1];
  const pending=button.listeners.click();await button.listeners.click();
  assert.equal(h.requests.filter(r=>r.path==='/api/messages/answer-1/feedback').length,1);
  h.respond('/api/messages/answer-1/feedback',{rating:'helpful'});await pending;
  assert.equal(button.getAttribute('aria-pressed'),'true');
});

await test('sign-out resets a pending calculator and rejects its late result',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; businessControls=[['employees',{value:'25'}]]");
  const pending=h.elements.get('business-form').listeners.submit({preventDefault(){}});
  assert.equal(h.elements.get('calculate-business').disabled,true);
  h.run('showLogin(); currentUser={id:"admin",role:"admin"}');
  assert.equal(h.elements.get('calculate-business').disabled,false);
  h.respond('/api/business-case',{results:{monthly_capacity_value_usd:999},basis:'OLD ACCOUNT'});await pending;
  assert.equal(h.elements.get('business-results').textContent,'');
});

await test('legacy evaluation format remains downloadable without rendering invalid cases',async()=>{
  const h=await initialized();h.run("renderEvaluation({id:'legacy',suite:'legacy',status:'completed',config:{},summary:{},results:[{question:'Old format'}]},insightRevision)");
  const output=h.elements.get('evaluation-results').textContent;
  assert.match(output,/Historical evaluation format/);
  assert.match(output,/Download evaluation JSON/);
  assert.equal(output.includes('Save judgment'),false);
});

await test('loading completed evaluations refreshes the stale busy status',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; insightTab='quality'");
  h.elements.get('status-text').textContent='Local model busy';
  const pending=h.run('loadInsights()');
  h.respond('/api/evaluations',[{id:'complete',suite:'full',status:'completed',created_at:'2026-09-27T12:00:00Z',config:{case_ids:[]},summary:{},results:[]}]);await pending;
  h.respond('/api/health',{status:'ready',model:'local',embedding_model:'local',missing:[]});await h.settle();
  assert.equal(h.elements.get('status-text').textContent,'Local models ready');
  assert.equal(h.elements.get('start-evaluation').disabled,false);
});

await test('terminal benchmark polling refreshes both history status and model health',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}; insightTab='quality'; let latestPoll; setTimeout=callback=>{latestPoll=callback;return 0}; renderEvaluation({id:'run',suite:'quick',status:'running',created_at:'2026-09-27T12:00:00Z',config:{case_ids:['one']},summary:{},results:[]},insightRevision)");
  const pending=h.run('latestPoll()');
  h.respond('/api/evaluations/run',{id:'run',status:'cancelled'});await h.settle();
  h.respond('/api/evaluations',[{id:'run',suite:'quick',status:'cancelled',created_at:'2026-09-27T12:00:00Z',config:{case_ids:['one']},summary:{},results:[]}]);await pending;
  h.respond('/api/health',{status:'ready',model:'local',embedding_model:'local',missing:[]});await h.settle();
  assert.match(h.elements.get('evaluation-history').textContent,/cancelled/);
  assert.equal(h.elements.get('cancel-evaluation').hidden,true);
  assert.equal(h.elements.get('status-text').textContent,'Local models ready');
});

await test('editing business inputs invalidates old results and a pending calculation',async()=>{
  const h=await initialized();h.run("currentUser={id:'employee',role:'employee'}; businessScenarios={base:{assumptions:{employees:25},results:{monthly_capacity_value_usd:525},basis:'Assumptions'}}; renderBusinessScenario()");
  const employeeInput=h.elements.get('business-fields').children[0].children[0];
  assert.equal(typeof employeeInput.listeners.input,'function','Editing an assumption must invalidate the displayed ROI');
  const pending=h.elements.get('business-form').listeners.submit({preventDefault(){}});
  employeeInput.value='100';
  employeeInput.listeners.input();
  h.respond('/api/business-case',{results:{monthly_capacity_value_usd:999},basis:'OLD INPUTS'});await pending;
  assert.equal(h.elements.get('business-results').textContent.includes('999'),false);
  assert.match(h.elements.get('business-results').textContent,/Recalculate/);
  assert.equal(h.elements.get('calculate-business').disabled,false);
});

await test('semantic passes still require human source review and show the reasoning',async()=>{
  const h=await initialized();
  h.run("renderEvaluation({id:'semantic',suite:'quick',status:'completed',config:{case_ids:['one'],semantic_prompt_hash:'hash'},summary:{quality_gate:'needs_human_review',passed:1,finished:1,total:1},results:[{id:'one',question:'Policy?',expected:'Evidence',answer:{answer:'Answer',citations:[]},passed:true,checks:{meaning_supported:true},semantic:{verdict:'supported',reason:'Roles agree with policy.'}}]},insightRevision)");
  const output=h.elements.get('evaluation-results').textContent;
  assert.match(output,/Human source review is still required/);
  assert.match(output,/Local semantic check: supported/);
  assert.match(output,/Roles agree with policy/);
});

await test('historical keyword benchmark is not presented as semantically checked',async()=>{
  const h=await initialized();
  h.run("renderEvaluation({id:'historical',suite:'quick',status:'completed',config:{case_ids:['one']},summary:{passed:1},results:[]},insightRevision)");
  assert.match(h.elements.get('evaluation-results').textContent,/no semantic assessment/);
});

await test('quality review opens the full authorized source without saving a human judgment',async()=>{
  const h=await initialized();h.run("currentUser={id:'admin',role:'admin'}");
  h.run("renderEvaluation({id:'semantic',suite:'quick',status:'completed',config:{case_ids:['one'],semantic_prompt_hash:'hash'},summary:{quality_gate:'needs_human_review'},results:[{id:'one',question:'Policy?',expected:'Evidence',answer:{answer:'Answer',citations:[{document_id:'policy-id',chunk_id:'chunk-id',filename:'policy.md',locator:'Paragraph 2',quote:'Policy quotation'},{document_id:'policy-id',filename:'policy.md',quote:'Second quotation'}]},passed:true,checks:{},semantic:{verdict:'supported',reason:'Policy supports the claim.'}}]},insightRevision)");
  const card=h.elements.get('evaluation-results').children.at(-1);
  const buttons=card.children.filter(e=>e.textContent==='Read source policy');
  assert.equal(buttons.length,1);
  const pending=buttons[0].listeners.click();
  h.respond('/api/documents/policy-id',{document:{title:'Complete policy',filename:'policy.md',version:1,department:'All',status:'ready'},chunks:[{id:'chunk-id',position:0,locator:'Paragraph 2',text:'Complete policy and its conditions.'}]});await pending;
  assert.equal(h.elements.get('source-dialog').open,true);
  assert.match(h.elements.get('source-content').textContent,/Complete policy and its conditions/);
  assert.equal(h.requests.some(r=>r.path.includes('/review')),false);
});
