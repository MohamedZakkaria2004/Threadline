'use strict';
const $ = id => document.getElementById(id);
let currentUser = null, conversationId = null, documents = [], busy = false;
let sessionEpoch = 0, viewRevision = 0;
let chatMode = 'ask', pendingSubmission = null, operationData = null, operationTab = 'tickets', operationRevision = 0;
let sourceRevision = 0, reportRevision = 0;
let insightTab = 'overview', insightRevision = 0, evaluationTimer = null, selectedEvaluation = null, businessScenarios = null, businessControls = [];
let businessRevision = 0;
class ObsoleteRequest extends Error {}
function reportError(error) { if (!(error instanceof ObsoleteRequest)) banner(error.message); }
const node = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('icon'); svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`); svg.append(use); return svg;
}
function setNavigation(open, restoreFocus = true) {
  const sidebar = $('sidebar');
  const wasOpen = sidebar.classList.contains('mobile-open');
  sidebar.classList.toggle('mobile-open', open);
  $('sidebar-scrim').hidden = !open;
  $('mobile-menu').setAttribute('aria-expanded', String(open));
  $('main-content').inert = open;
  if (open) {
    sidebar.setAttribute('role', 'dialog'); sidebar.setAttribute('aria-modal', 'true');
    $('close-menu').focus();
  } else {
    sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal');
    if (wasOpen && restoreFocus) $('mobile-menu').focus();
  }
}
function banner(message = '') { $('banner').textContent = message; $('banner').hidden = !message; }
async function api(path, options = {}) {
  const epoch = sessionEpoch;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 780000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal, credentials: 'same-origin', headers: { 'X-Copilot-Request': '1', ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers } });
    const body = await response.json();
    if (epoch !== sessionEpoch) throw new ObsoleteRequest('The account changed while this request was in progress.');
    if (!response.ok) {
      if (response.status === 401 && currentUser) showLogin();
      const detail = Array.isArray(body.detail) ? body.detail.map(x => x.msg).join('; ') : body.detail;
      const error = new Error(detail || 'Request failed. Please retry.'); error.status = response.status; throw error;
    }
    return body;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The local request timed out. Check saved conversations before retrying.');
    if (error instanceof TypeError) throw new Error('Cannot reach the local application. Restart the server and try again.');
    throw error;
  } finally { clearTimeout(timer); }
}
function showLogin() {
  sessionEpoch++; viewRevision++;
  resetInsights();
  setNavigation(false, false);
  currentUser = null; conversationId = null; documents = [];
  pendingSubmission = null; operationData = null; operationRevision++;
  $('operations-list').replaceChildren(); $('operations-summary').replaceChildren();
  $('report-dialog').close(); $('report-content').textContent = ''; $('report-title').textContent = ''; $('report-download').removeAttribute('href');
  $('app-view').hidden = true; $('login-view').hidden = false;
  $('messages').replaceChildren(); $('conversation-list').replaceChildren(); $('library-list').replaceChildren();
  $('source-dialog').close(); $('source-content').replaceChildren();
  $('source-title').textContent = ''; $('source-meta').textContent = '';
  $('question').value = ''; $('thinking').hidden = true; setBusy(false);
  $('upload-file').value = ''; $('upload-title').value = ''; $('upload-status').textContent = '';
  $('upload-replacement').replaceChildren(new Option('New document', ''));
  $('upload-department').value = 'All'; $('upload-classification').value = 'internal';
  $('upload-department').disabled = false; $('upload-classification').disabled = false;
  $('password').value = ''; banner();
}
function setBusy(value) {
  busy = value;
  for (const id of ['send', 'question', 'new-chat', 'upload-button', 'logout', 'mode-ask', 'mode-agent', 'start-action']) $(id).disabled = value;
  document.querySelectorAll('.suggestion,.conversation-item').forEach(el => el.disabled = value);
}
async function health() {
  try {
    const state = await api('/api/health');
    $('status-text').textContent = state.status === 'ready' ? 'Local models ready' : state.status === 'busy' ? 'Local model busy' : 'Check model connection';
    $('model-status').classList.toggle('unavailable', state.status !== 'ready');
    $('model-status').title = state.status === 'ready' ? `${state.model} · ${state.embedding_model}` : state.status === 'busy' ? 'A local request is in progress. Click to refresh.' : state.error || `Install these local models: ${state.missing.join(', ')}`;
  } catch (e) { if (e instanceof ObsoleteRequest) return; $('status-text').textContent = 'Application offline'; $('model-status').classList.add('unavailable'); }
}
async function enterApp(user) {
  sessionEpoch++; setBusy(false);
  const epoch = sessionEpoch;
  currentUser = user; $('login-view').hidden = true; $('app-view').hidden = false;
  $('insight-quality').hidden = $('insight-prompts').hidden = user.role !== 'admin';
  $('insight-scope-label').hidden = user.role !== 'admin'; $('insight-scope').value = 'mine';
  $('profile-name').textContent = user.name; $('profile-role').textContent = `${user.role} · ${user.department}`;
  $('avatar').textContent = user.name.split(' ').map(w => w[0]).slice(0, 2).join('');
  $('upload-panel').hidden = user.role !== 'admin';
  $('password').value = ''; setMode('ask'); newChat();
  const loaded = await Promise.allSettled([health(), loadConversations(), loadDocuments()]);
  if (epoch !== sessionEpoch) return;
  const failed = loaded.find(result => result.status === 'rejected' && !(result.reason instanceof ObsoleteRequest));
  if (failed) reportError(failed.reason);
}
function view(name) {
  viewRevision++;
  insightRevision++; clearTimeout(evaluationTimer);
  for (const section of ['chat', 'library', 'operations', 'insights']) {
    $(`${section}-view`).hidden = name !== section;
    $(`nav-${section}`).classList.toggle('active', name === section);
    if (section === name) $(`nav-${section}`).setAttribute('aria-current', 'page');
    else $(`nav-${section}`).removeAttribute('aria-current');
  }
  $('page-label').textContent = {chat:'Knowledge assistant', operations:'Operations', library:'Document library', insights:'Insights'}[name];
  setNavigation(false);
}
function newChat() {
  if (busy) return;
  conversationId = null; pendingSubmission = null; $('messages').replaceChildren(); $('welcome').hidden = false; $('question').value = ''; banner(); view('chat');
  $('chat-scroll').scrollTop = 0;
  document.querySelectorAll('.conversation-item').forEach(el => el.classList.remove('active'));
}
async function loadConversations() {
  const rows = await api('/api/conversations'); $('conversation-list').replaceChildren();
  if (!rows.length) $('conversation-list').append(node('p', 'empty-history', 'Your conversations will appear here. Pick a question to get started.'));
  for (const row of rows) {
    const button = node('button', 'conversation-item', row.title); button.title = row.title; button.disabled = busy;
    button.classList.toggle('active', row.id === conversationId);
    button.addEventListener('click', async () => {
      if (busy) return;
      const selection = ++viewRevision;
      try {
        const messages = await api(`/api/conversations/${encodeURIComponent(row.id)}`);
        if (selection !== viewRevision) return;
        conversationId = row.id; pendingSubmission = null; $('messages').replaceChildren(); $('welcome').hidden = true; view('chat'); banner();
        for (const item of messages) renderMessage(item.role, item.content, item.metadata);
        document.querySelectorAll('.conversation-item').forEach(el => el.classList.toggle('active', el === button));
        scrollBottom();
      } catch (e) { if (selection === viewRevision) reportError(e); }
    });
    $('conversation-list').append(button);
  }
}
function renderMessage(role, text, metadata = {}) {
  const article = node('article', `message ${role}`);
  const label = node('div', 'message-label');
  if (role === 'assistant') label.append(node('span', 'brand-mark', 't'));
  label.append(node('span', '', role === 'assistant' ? 'Threadline' : 'You'));
  article.append(label, node('div', 'message-text', text));
  if (metadata.insufficient_evidence) article.append(node('div', 'abstention-label', 'Insufficient evidence · No policy conclusion made'));
  if (metadata.historical_sources) article.append(node('div', 'historical-note', 'Historical answer: a cited document has been superseded. Ask again for current policy.'));
  if (metadata.citations?.length) {
    const details = node('details', 'sources'); details.open = true;
    details.append(node('summary', '', `${metadata.citations.length} supporting passage${metadata.citations.length === 1 ? '' : 's'}`));
    for (const citation of metadata.citations) {
      const card = node('div', 'citation');
      const button = node('button', '', citation.title);
      button.addEventListener('click', () => openDocument(citation.document_id, citation.chunk_id));
      card.append(button, node('blockquote', '', citation.quote), node('small', '', `${citation.filename} · ${citation.locator || 'Document'} · Version ${citation.version || 1}`)); details.append(card);
    }
    article.append(details);
  }
  if (metadata.latency_ms !== undefined) {
    const meta = node('div', 'answer-meta');
    meta.append(node('span', '', `${(metadata.latency_ms / 1000).toFixed(1)}s`), node('span', '', metadata.model), node('span', '', `Prompt ${metadata.prompt_version}`));
    article.append(meta);
  }
  if (metadata.steps?.length) article.append(workflowSteps(metadata.steps));
  if (metadata.tool && metadata.tool !== 'answer') {
    const actions = node('div', 'message-actions');
    actions.append(statusBadge(metadata.status));
    const button = node('button', 'secondary', metadata.report ? 'Open report' : 'View in Operations');
    button.addEventListener('click', () => metadata.report ? openReport(metadata.report.id) : showOperations(metadata.tool === 'generate_report' ? 'reports' : metadata.approval_id ? 'approvals' : 'tickets'));
    actions.append(button); article.append(actions);
  }
  if (metadata.message_id && metadata.status === 'completed' && ['answer','generate_report'].includes(metadata.tool) && !metadata.action_unavailable && !metadata.access_changed) article.append(feedbackControls(metadata));
  $('messages').append(article);
}
function scrollBottom() { $('chat-scroll').scrollTop = $('chat-scroll').scrollHeight; }
function setMode(mode) {
  if (busy) return;
  chatMode = mode;
  for (const value of ['ask', 'agent']) {
    $(`mode-${value}`).classList.toggle('selected', value === mode);
    $(`mode-${value}`).setAttribute('aria-pressed', String(value === mode));
  }
  $('knowledge-suggestions').hidden = mode !== 'ask'; $('action-suggestions').hidden = mode !== 'agent';
  $('question').maxLength = mode === 'agent' ? 1200 : 3000;
  $('question').placeholder = mode === 'agent' ? 'Create a support ticket, generate a report, or request access…' : "What's on your mind?";
  $('mode-note').textContent = mode === 'agent' ? 'Local tools · Human review for sensitive requests' : 'Answers with evidence';
}

function statusBadge(status) { return node('span', `operation-status status-${status}`, (status || 'saved').replaceAll('_', ' ')); }
function workflowSteps(steps) {
  const details = node('details', 'workflow-trace'); details.append(node('summary', '', 'Workflow trace'));
  const list = node('ol');
  for (const step of steps) { const item = node('li'); item.append(node('strong', '', step.name), node('p', '', step.detail)); list.append(item); }
  details.append(list); return details;
}
function showOperations(tab) {
  if (tab) operationTab = tab;
  view('operations'); banner(); loadOperations().catch(reportError);
}
async function loadOperations() {
  const revision = ++operationRevision;
  const result = await api('/api/operations');
  if (revision !== operationRevision) return;
  operationData = result; renderOperations();
}
function renderOperations() {
  if (!operationData || !currentUser) return;
  const data = operationData;
  $('operations-summary').replaceChildren();
  for (const [label, value, detail] of [
    ['Open tickets', data.tickets.filter(t => t.status !== 'resolved').length, 'Within your access'],
    ['Awaiting review', data.approvals.filter(a => a.status === 'pending').length, 'A human makes the call'],
    ['Saved reports', data.reports.length, 'Your private briefings'],
  ]) { const card = node('div', 'operation-stat'); card.append(node('span', '', label), node('strong', '', String(value)), node('small', '', detail)); $('operations-summary').append(card); }
  for (const tab of ['tickets', 'approvals', 'reports', 'workflows']) {
    $(`ops-${tab}`).classList.toggle('selected', tab === operationTab);
    $(`ops-${tab}`).setAttribute('aria-pressed', String(tab === operationTab));
  }
  const scope = currentUser.role === 'admin' ? 'all local requests' : currentUser.role === 'manager' ? 'your requests and requests in your department' : 'your own requests';
  $('operations-scope').textContent = operationTab === 'reports' ? 'Reports are private to their creator. Sources are checked again whenever you open or download one.' : operationTab === 'workflows' ? 'Your most recent 100 action workflows, including failures and human decisions.' : `Showing ${scope}. Refresh to see new decisions and progress.`;
  const list = $('operations-list'); list.replaceChildren();
  if (!data[operationTab].length) {
    const empty = node('div', 'operations-empty'); empty.append(icon(operationTab === 'reports' ? 'file' : 'receipt'), node('h3', '', 'A clear space, for now.'), node('p', '', 'Create an action from the assistant. Its progress will appear here.')); list.append(empty);
  }
  for (const item of data[operationTab]) {
    const card = node('article', 'operation-card');
    const top = node('div', 'operation-card-top');
    const info = node('div');
    info.append(node('small', 'operation-reference', `${item.id.slice(0, 16)} · ${new Date(item.created_at).toLocaleString()}`));
    info.append(node('h3', '', item.title || item.plan?.title || item.input));
    top.append(info, statusBadge(item.status || (item.available ? 'saved' : 'unavailable'))); card.append(top);
    if (operationTab === 'tickets') {
      card.append(node('p', 'operation-body', item.description), node('p', 'operation-detail', `${item.requester} · ${item.department} · ${item.priority} priority · ${item.category.replaceAll('_', ' ')}`));
      const controls = node('div', 'operation-controls');
      const transitions = item.status === 'resolved' ? [['open', 'Reopen']] : item.status === 'open' ? [['in_progress', 'Start work'], ['resolved', 'Resolve']] : [['resolved', 'Resolve']];
      for (const [status, label] of transitions) {
        const button = node('button', 'secondary', label);
        button.addEventListener('click', () => mutateOperation(button, () => api(`/api/tickets/${encodeURIComponent(item.id)}`, {method: 'PATCH', body: JSON.stringify({status, expected_status: item.status})})));
        controls.append(button);
      }
      card.append(controls);
    } else if (operationTab === 'approvals') {
      card.append(node('p', 'operation-body', item.input), node('p', 'operation-detail', `${item.requester} · ${item.department} · ${item.plan.tool.replaceAll('_', ' ')} · ${item.plan.priority} priority`), node('p', 'review-reason', item.reason));
      if (item.decision_note) card.append(node('p', 'operation-detail', `Decision note: ${item.decision_note}`));
      if (item.can_review) {
        const form = node('form', 'review-form');
        const label = node('label', '', 'Decision reason'); const input = node('input'); input.required = true; input.minLength = 3; input.maxLength = 500; input.placeholder = 'Explain why this request should proceed or stop'; label.append(input);
        const actions = node('div', 'operation-controls');
        const approve = node('button', 'primary', 'Approve & create ticket'); approve.type = 'submit'; approve.value = 'approve';
        const reject = node('button', 'secondary', 'Reject request'); reject.type = 'submit'; reject.value = 'reject'; actions.append(approve, reject); form.append(label, actions);
        let submitting = false;
        form.addEventListener('submit', async event => {
          event.preventDefault(); if (submitting) return;
          const decision = event.submitter?.value;
          if (!['approve', 'reject'].includes(decision) || input.value.trim().length < 3) { banner('Enter a reason and choose Approve or Reject.'); return; }
          submitting = true; approve.disabled = true; reject.disabled = true;
          try { await mutateOperation(approve, () => api(`/api/approvals/${encodeURIComponent(item.id)}/decision`, {method: 'POST', body: JSON.stringify({decision, reason: input.value.trim()})})); }
          finally { submitting = false; approve.disabled = false; reject.disabled = false; }
        }); card.append(form);
      } else if (item.status === 'pending') card.append(node('p', 'operation-detail', 'Waiting for a different, authorized reviewer. You cannot approve your own request.'));
    } else if (operationTab === 'reports') {
      card.append(node('p', 'operation-detail', item.historical_sources ? 'Historical sources · Generate a new report for current policy.' : 'Evidence-backed draft · Includes your own ticket snapshot'));
      const button = node('button', 'secondary', 'Read report'); button.disabled = !item.available; button.addEventListener('click', () => openReport(item.id)); card.append(button);
    } else {
      card.append(node('p', 'operation-detail', `Tool: ${item.tool.replaceAll('_', ' ')}`), workflowSteps(item.steps));
    }
    list.append(card);
  }
}
async function mutateOperation(button, action) {
  const epoch = sessionEpoch; button.disabled = true; banner();
  try { await action(); await loadOperations(); }
  catch (error) { if (epoch === sessionEpoch) reportError(error); }
  finally { if (epoch === sessionEpoch) button.disabled = false; }
}
async function openReport(id) {
  const revision = ++reportRevision;
  const selection = viewRevision;
  try {
    const report = await api(`/api/reports/${encodeURIComponent(id)}`);
    if (revision !== reportRevision || selection !== viewRevision) return;
    $('report-title').textContent = report.title;
    const content = $('report-content'); content.replaceChildren();
    content.append(node('p', 'operation-detail', `Saved ${new Date(report.created_at).toLocaleString()} · ${report.metadata.model} · Prompt ${report.metadata.prompt_version}`));
    if (report.metadata.historical_sources) content.append(node('p', 'review-reason', 'Historical report: a source has been superseded. Generate a new report for current policy.'));
    content.append(node('h3', '', 'Evidence-based briefing'), node('p', 'report-answer', report.metadata.answer));
    content.append(node('h3', '', 'Your service desk snapshot'), node('p', 'operation-detail', 'Your own local tickets at the time this report was saved. Counts come directly from SQL.'));
    const table = node('table', 'report-table');
    const head = node('thead'), headings = node('tr'); for (const title of ['Status', 'Priority', 'Tickets']) headings.append(node('th', '', title)); head.append(headings); table.append(head);
    const body = node('tbody');
    for (const row of report.metadata.ticket_counts) { const tr = node('tr'); tr.append(node('td', '', row.status.replaceAll('_', ' ')), node('td', '', row.priority), node('td', '', String(row.count))); body.append(tr); }
    table.append(body); content.append(table);
    if (!report.metadata.ticket_counts.length) content.append(node('p', 'operation-detail', 'No tickets at generation time.'));
    content.append(node('h3', '', 'Supporting sources'));
    for (const source of report.metadata.citations) {
      const card = node('div', 'citation'); const button = node('button', '', source.title);
      button.addEventListener('click', () => openDocument(source.document_id, source.chunk_id));
      card.append(button, node('blockquote', '', source.quote), node('small', '', `${source.filename} · ${source.locator} · Version ${source.version}`)); content.append(card);
    }
    content.append(node('p', 'operation-detail', 'AI-generated draft for human review. Quote and number checks do not prove semantic correctness.'));
    $('report-download').href = `/api/reports/${encodeURIComponent(id)}/download`;
    $('report-dialog').showModal();
  } catch (error) { if (revision === reportRevision && selection === viewRevision) reportError(error); }
}

async function sendQuestion(question) {
  question = question.trim(); if (!question || busy) return;
  const epoch = sessionEpoch;
  const mode = chatMode;
  const prior = pendingSubmission;
  const payload = prior && prior.message === question && prior.mode === mode && prior.conversation_id === conversationId ? prior : { message: question, conversation_id: conversationId, request_id: crypto.randomUUID(), mode };
  pendingSubmission = payload;
  $('thinking-label').textContent = mode === 'agent' ? 'Planning your local action and checking its requirements…' : 'Finding the answer in your sources…';
  view('chat'); banner(); $('welcome').hidden = true; renderMessage('user', question);
  $('question').value = ''; setBusy(true); $('thinking').hidden = false; scrollBottom();
  try {
    const result = await api('/api/chat', { method: 'POST', body: JSON.stringify(payload) });
    if (!currentUser) return;
    pendingSubmission = null; conversationId = result.conversation_id; renderMessage('assistant', result.answer, result);
  } catch (e) {
    if (epoch !== sessionEpoch) return;
    if (e.status && e.status < 500 && e.status !== 409 || e.status === 503) pendingSubmission = null;
    banner(e.message); $('question').value = question;
    renderMessage('assistant', 'The request did not complete. Check the message above and retry when the local model is available.');
  } finally {
    if (epoch !== sessionEpoch) return;
    setBusy(false); $('thinking').hidden = true; scrollBottom();
    if (currentUser) { try { await loadConversations(); await health(); } catch (e) { reportError(e); } }
    if (epoch === sessionEpoch) $('question').focus();
  }
}
async function loadDocuments() {
  documents = await api('/api/documents');
  const ready = documents.filter(d => d.status === 'ready');
  $('document-count').textContent = `${ready.length} permitted document${ready.length === 1 ? '' : 's'} in your library`;
  $('library-total').textContent = `${ready.length} ready document${ready.length === 1 ? '' : 's'}`;
  const list = $('library-list'); list.replaceChildren();
  const replacement = $('upload-replacement'); replacement.replaceChildren(new Option('New document', ''));
  if (!documents.length) list.append(node('p', 'empty-library', 'No documents are available yet. An administrator can add documents to your knowledge library.'));
  for (const doc of documents) {
    if (doc.status === 'ready') replacement.append(new Option(`${doc.title} (v${doc.version})`, doc.id));
    const card = node('article', 'document-card');
    const symbol = node('div', 'doc-symbol'); symbol.append(icon('file')); card.append(symbol);
    const info = node('div', 'document-info'); const button = node('button'); button.append(node('h3', '', doc.title)); button.addEventListener('click', () => openDocument(doc.id));
    info.append(button, node('p', '', `${doc.filename} · ${doc.chunk_count} chunks · Version ${doc.version}`));
    const tags = node('div', 'tags'); tags.append(node('span', 'tag', doc.department === 'All' ? 'Company-wide' : doc.department), node('span', `tag ${doc.classification === 'leadership' ? 'warning' : ''}`, doc.classification));
    info.append(tags); if (doc.error) info.append(node('p', 'error', doc.error));
    card.append(info, node('span', 'doc-status', doc.status)); list.append(card);
  }
}
async function openDocument(id, chunkId) {
  const revision = ++sourceRevision;
  const selection = viewRevision;
  try {
    const result = await api(`/api/documents/${encodeURIComponent(id)}`);
    if (revision !== sourceRevision || selection !== viewRevision) return;
    $('source-title').textContent = result.document.title;
    $('source-meta').textContent = `${result.document.filename} · Version ${result.document.version} · ${result.document.department} · ${result.document.status}`;
    $('source-content').replaceChildren();
    for (const chunk of result.chunks) {
      const section = node('section', `source-chunk ${chunk.id === chunkId ? 'highlight' : ''}`);
      section.append(node('h4', '', `${chunk.locator} · Chunk ${chunk.position + 1}`), node('p', '', chunk.text)); $('source-content').append(section);
    }
    $('source-dialog').showModal();
    if (chunkId) $('source-content').querySelector('.highlight')?.scrollIntoView({ block: 'center' });
  } catch (e) { if (revision === sourceRevision && selection === viewRevision) reportError(e); }
}
$('login-form').addEventListener('submit', async e => {
  e.preventDefault(); $('login-error').textContent = ''; $('login-button').disabled = true;
  try { const user = await api('/api/login', { method: 'POST', body: JSON.stringify({ username: $('username').value, password: $('password').value }) }); await enterApp(user); }
  catch (error) { if (!(error instanceof ObsoleteRequest)) $('login-error').textContent = error.message; }
  finally { $('login-button').disabled = false; }
});
$('logout').addEventListener('click', async () => { try { await api('/api/logout', { method: 'POST' }); showLogin(); } catch (e) { reportError(e); } });
$('nav-chat').addEventListener('click', () => view('chat'));
$('nav-library').addEventListener('click', () => { view('library'); loadDocuments().catch(reportError); });
$('nav-operations').addEventListener('click', () => showOperations());
$('refresh-operations').addEventListener('click', () => loadOperations().catch(reportError));
$('start-action').addEventListener('click', () => { if (busy) return; newChat(); setMode('agent'); $('question').focus(); });
for (const tab of ['tickets', 'approvals', 'reports', 'workflows']) $(`ops-${tab}`).addEventListener('click', () => { operationTab = tab; renderOperations(); });
for (const mode of ['ask', 'agent']) $(`mode-${mode}`).addEventListener('click', () => setMode(mode));
$('close-report').addEventListener('click', () => { reportRevision++; sourceRevision++; $('report-dialog').close(); });
$('report-dialog').addEventListener('cancel', () => { reportRevision++; sourceRevision++; });
$('new-chat').addEventListener('click', newChat);
$('model-status').addEventListener('click', health);
$('refresh-library').addEventListener('click', () => loadDocuments().catch(reportError));
$('chat-form').addEventListener('submit', e => { e.preventDefault(); sendQuestion($('question').value); });
$('question').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuestion($('question').value); } });
document.querySelectorAll('.suggestion').forEach(el => el.addEventListener('click', () => { if (busy) return; setMode(el.dataset.mode || 'ask'); sendQuestion(el.dataset.question); }));
$('close-source').addEventListener('click', () => { sourceRevision++; $('source-dialog').close(); });
$('source-dialog').addEventListener('cancel', () => { sourceRevision++; });
$('source-dialog').addEventListener('click', e => { if (e.target === $('source-dialog')) { const r = e.target.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) { sourceRevision++; e.target.close(); } } });
$('upload-replacement').addEventListener('change', () => {
  const doc = documents.find(d => d.id === $('upload-replacement').value);
  $('upload-department').disabled = !!doc; $('upload-classification').disabled = !!doc;
  if (doc) { $('upload-department').value = doc.department; $('upload-classification').value = doc.classification; $('upload-title').value = doc.title; }
});
$('upload-form').addEventListener('submit', async e => {
  e.preventDefault(); if (busy) return;
  const epoch = sessionEpoch;
  const file = $('upload-file').files[0]; if (!file) return;
  if (file.size > 10 * 1024 * 1024) { $('upload-status').textContent = 'Files must be 10 MB or smaller.'; return; }
  const form = new FormData(); form.append('file', file); form.append('title', $('upload-title').value); form.append('department', $('upload-department').value); form.append('classification', $('upload-classification').value); form.append('replaces_id', $('upload-replacement').value);
  setBusy(true); $('upload-status').textContent = 'Extracting text, creating local embeddings, and indexing…'; banner();
  try {
    const result = await api('/api/documents', { method: 'POST', body: form });
    $('upload-status').textContent = result.duplicate ? 'This document is already indexed. No duplicate was created.' : `Ready: ${result.title} · ${result.chunk_count} chunks · Version ${result.version}`;
    $('upload-file').value = ''; $('upload-title').value = ''; $('upload-department').disabled = false; $('upload-classification').disabled = false;
    await loadDocuments();
  } catch (error) { if (epoch === sessionEpoch) $('upload-status').textContent = error.message; }
  finally { if (epoch === sessionEpoch) setBusy(false); }
});
$('mobile-menu').addEventListener('click', () => setNavigation(true));
$('close-menu').addEventListener('click', () => setNavigation(false));
$('sidebar-scrim').addEventListener('click', () => setNavigation(false));
document.addEventListener('keydown', event => {
  if (!$('sidebar').classList.contains('mobile-open')) return;
  if (event.key === 'Escape') { event.preventDefault(); setNavigation(false); }
  if (event.key === 'Tab') {
    const focusable = [...$('sidebar').querySelectorAll('a[href],button:not(:disabled)')].filter(el => el.getClientRects().length);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
window.matchMedia('(min-width: 761px)').addEventListener('change', event => { if (event.matches) setNavigation(false, false); });
function resetInsights() {
  insightRevision++; clearTimeout(evaluationTimer); evaluationTimer = null;
  businessRevision++;
  selectedEvaluation = null; businessScenarios = null; businessControls = []; insightTab = 'overview';
  for (const id of ['insights-status','insight-metrics','insight-details','insight-events','evaluation-history','evaluation-results','prompt-inventory','business-fields','business-results']) $(id).replaceChildren();
  $('start-evaluation').disabled = false; $('cancel-evaluation').hidden = true;
  $('calculate-business').disabled = false;
}
function feedbackControls(metadata) {
  const group = node('div', 'feedback-controls'); group.append(node('span', '', 'Was this useful?'));
  let saving = false;
  const buttons = ['helpful','unhelpful'].map(rating => {
    const button = node('button', 'feedback-button', rating === 'helpful' ? 'Helpful' : 'Not helpful');
    button.setAttribute('aria-pressed', String(metadata.feedback === rating));
    button.addEventListener('click', async () => {
      if (saving) return;
      const epoch = sessionEpoch; saving = true; buttons.forEach(b => b.disabled = true);
      try {
        await api(`/api/messages/${encodeURIComponent(metadata.message_id)}/feedback`, {method:'PUT',body:JSON.stringify({rating})});
        if (epoch !== sessionEpoch) return;
        metadata.feedback = rating; buttons.forEach((b,i) => b.setAttribute('aria-pressed', String(['helpful','unhelpful'][i] === rating)));
      } catch (error) { if (epoch === sessionEpoch) reportError(error); }
      finally { saving = false; if (epoch === sessionEpoch) buttons.forEach(b => b.disabled = false); }
    }); group.append(button); return button;
  });
  return group;
}
const displayNumber = (value, suffix = '') => value === null || value === undefined ? '—' : Number(value).toLocaleString(undefined,{maximumFractionDigits:2}) + suffix;
const displayMoney = value => value === null || value === undefined ? '—' : Number(value).toLocaleString('en-US',{style:'currency',currency:'USD'});
function metricCard(label, value, detail) {
  const card = node('div','operation-stat'); card.append(node('span','',label),node('strong','',value),node('small','',detail)); return card;
}
function insightCard(title, pairs) {
  const card=node('div','insight-card'); card.append(node('h3','',title));
  const list=node('dl','insight-facts');
  for (const [label,value] of pairs) { list.append(node('dt','',label),node('dd','',String(value))); }
  card.append(list); return card;
}
function showInsights(tab = insightTab) {
  if (['quality','prompts'].includes(tab) && currentUser?.role !== 'admin') tab='overview';
  insightTab=tab; view('insights'); banner(); loadInsights();
}
async function loadInsights() {
  const revision=++insightRevision; clearTimeout(evaluationTimer);
  for (const tab of ['overview','quality','prompts','business']) {
    $(`insight-${tab}-panel`).hidden = tab !== insightTab;
    $(`insight-${tab}`).setAttribute('aria-pressed',String(tab===insightTab));
    $(`insight-${tab}`).classList.toggle('selected',tab===insightTab);
  }
  $('insights-status').textContent='Loading…';
  try {
    if (insightTab==='overview') {
      const data=await api(`/api/insights?days=${encodeURIComponent($('insight-days').value || '30')}&scope=${encodeURIComponent($('insight-scope').value || 'mine')}`);
      if (revision!==insightRevision) return;
      renderInsights(data);
    } else if (insightTab==='quality') {
      const runs=await api('/api/evaluations'); if (revision!==insightRevision) return;
      health();
      const history=$('evaluation-history'); history.replaceChildren();
      for (const run of runs) {
        const button=node('button','secondary',`${new Date(run.created_at).toLocaleString()} · ${run.suite} · ${run.status}`);
        button.addEventListener('click',()=>{selectedEvaluation=run.id; loadInsights();}); history.append(button);
      }
      const run=runs.find(r=>r.id===selectedEvaluation) || runs[0];
      if (run) { selectedEvaluation=run.id; renderEvaluation(run,revision); $('start-evaluation').disabled=runs.some(r=>r.status==='running'); }
      else { $('evaluation-results').replaceChildren(node('p','muted','No benchmark runs yet. Start with the quick check.')); $('start-evaluation').disabled=false; $('cancel-evaluation').hidden=true; }
    } else if (insightTab==='prompts') {
      const data=await api('/api/prompts'); if (revision!==insightRevision) return;
      const list=$('prompt-inventory'); list.replaceChildren(insightCard('Prompt registry', [['Active version',data.active_version],['Local model',data.model],['Embeddings',data.embedding_model]]));
      list.append(node('p','muted','Read-only versions. Each template keeps its file fingerprint so an evaluation can be reproduced.'));
      for (const item of data.templates) {
        const details=node('details','insight-card'); details.append(node('summary','',`${item.version} / ${item.name}${item.version===data.active_version ? ' · Active' : ''}`),node('p','prompt-hash',`SHA-256 ${item.sha256}`),node('pre','prompt-text',item.content)); list.append(details);
      }
    } else {
      const data=await api('/api/business-case'); if (revision!==insightRevision) return;
      businessScenarios=data.scenarios; renderBusinessScenario();
    }
    if (revision===insightRevision) $('insights-status').textContent='';
  } catch (error) { if (revision===insightRevision) { $('insights-status').textContent='Could not refresh this view.'; reportError(error); } }
}
function renderInsights(data) {
  $('insight-metrics').replaceChildren(
    metricCard('Requests',displayNumber(data.requests),`${data.days} days · ${data.scope==='mine' ? 'Your activity' : 'Platform aggregates'}`),
    metricCard('Typical response',displayNumber(data.latency.p50_seconds,'s'),`P50 · ${data.latency.samples} recorded requests`),
    metricCard('P95 response',displayNumber(data.latency.p95_seconds,'s'),'Nearest rank · processing time'),
    metricCard('Helpful feedback',displayNumber(data.feedback.helpful_percent,'%'),`${data.feedback.rated} rated answers`));
  $('insight-details').replaceChildren(
    insightCard('Reliability', [['Completed',data.states.completed],['Failed',data.states.failed],['Running',data.states.running],['Waiting for review',data.states.waiting_approval],['Human rejections',data.states.rejected],['Failure rate',displayNumber(data.failure_rate_percent,'%')]]),
    insightCard('Evidence & outcomes', [['Knowledge responses',data.knowledge.answers],['Responses with citations',data.knowledge.cited],['Abstentions',data.knowledge.abstained],['Final quote/number rejections',data.knowledge.guard_rejections],['Artifacts created',data.actions.created],['Completed without artifact',data.actions.no_artifact]]),
    insightCard('Local generation', [['Model calls',data.generation.calls],['Model errors',data.generation.errors],['Prompt tokens',displayNumber(data.generation.prompt_tokens)],['Output tokens',displayNumber(data.generation.output_tokens)],['Estimated generation electricity',`$${data.generation.estimated_electricity_usd.toFixed(6)}`],['Active demo accounts',`${data.active_users} / ${data.registered_users}`]]));
  const events=$('insight-events'); events.replaceChildren(node('h3','','Recent audit events'),node('p','muted',data.definitions));
  if (!data.events.length) events.append(node('p','muted','No events in this window.'));
  for (const event of data.events) { const row=node('div','audit-row'); row.append(node('span','',event.event),node('time','',new Date(event.created_at).toLocaleString())); events.append(row); }
}
function renderEvaluation(run,revision) {
  const content=$('evaluation-results'); content.replaceChildren();
  const s=run.summary, running=run.status==='running';
  $('start-evaluation').disabled=running; $('cancel-evaluation').hidden=!running; $('cancel-evaluation').disabled=Boolean(run.cancel_requested);
  const header=node('div','insight-card'); header.append(node('h2','',`${run.suite==='full' ? 'Full' : 'Quick'} check · ${run.status}`),node('p','muted',`${s.finished || 0} of ${s.total || 0} cases finished. ${run.cancel_requested && running ? 'Stopping after the current case.' : ''}`));
  const progress=node('progress'); progress.max=s.total || 1; progress.value=s.finished || 0; progress.setAttribute('aria-label','Benchmark cases completed'); header.append(progress);
  header.append(node('p','muted',run.config.grading || 'Historical evaluation.'),node('p','operation-detail',`${run.config.model || ''} · Prompt ${run.config.prompt_version || ''} · ${run.config.benchmark_version || ''}`));
  if (s.error) header.append(node('p','error',s.error));
  const download=node('a','secondary','Download evaluation JSON'); download.href=`/api/evaluations/${encodeURIComponent(run.id)}/download`; download.setAttribute('download',''); header.append(download); content.append(header);
  if (!run.config.case_ids) { content.append(node('p','muted','Historical evaluation format. Download the original record or start a new benchmark.')); clearTimeout(evaluationTimer); return; }
  const gateLabels={needs_human_review:'Automated checks passed. Human source review is still required.',reviewed_correct:'All cases recorded as correct by a reviewer. This is a demo benchmark, not enterprise certification.',blocked:'Quality sign-off blocked. Inspect the failed or uncertain cases.',incomplete:'Quality sign-off pending: this run is incomplete.'};
  content.append(node('p','review-reason',run.config.semantic_prompt_hash ? (gateLabels[s.quality_gate] || gateLabels.incomplete) : 'Historical keyword/quote checks only. This run has no semantic assessment; run a new benchmark.'));
  const metrics=node('div','metric-grid'); metrics.append(metricCard('Automated checks',`${s.passed || 0} / ${s.finished || 0}`,'Among finished cases'),metricCard('Human reviews',`${s.human_reviewed || 0} / ${s.finished || 0}`,'Separate semantic assessment'),metricCard('Incorrect judgments',displayNumber(s.human_incorrect_percent,'%'),'Among correct / incorrect judgments'),metricCard('P95 case time',displayNumber(s.p95_seconds,'s'),'Small synthetic benchmark')); content.append(metrics);
  for (const item of run.results) {
    const card=node('article','insight-card evaluation-case'); card.append(statusBadge(item.passed ? 'checks_passed' : 'checks_failed'),node('h3','',item.question),node('p','expected-answer','Expected: '+item.expected),node('p','report-answer',item.answer.answer));
    if (item.semantic) card.append(node('p','review-reason',`Local semantic check: ${item.semantic.verdict}. ${item.semantic.reason}`));
    for (const citation of item.answer.citations || []) card.append(node('blockquote','',citation.quote),node('small','muted',`${citation.filename} · ${citation.locator}`));
    const sourceIds=new Set();
    for (const citation of item.answer.citations || []) {
      if (!citation.document_id || sourceIds.has(citation.document_id)) continue;
      sourceIds.add(citation.document_id);
      const sourceButton=node('button','secondary','Read source policy'); sourceButton.type='button';
      sourceButton.addEventListener('click',()=>openDocument(citation.document_id,citation.chunk_id)); card.append(sourceButton);
    }
    const checks=node('details'); checks.append(node('summary','','Automated checks'));
    for (const [key,value] of Object.entries(item.checks)) checks.append(node('p','operation-detail',`${value ? 'Pass' : 'Fail'} · ${key.replaceAll('_',' ')}`)); card.append(checks);
    if (item.review) card.append(node('p','review-reason',`Human judgment: ${item.review.verdict}. ${item.review.note}`));
    if (!running) {
      const form=node('form','quality-review'); const label=node('label','','Your judgment'); const select=node('select'); select.required=true;
      for (const [value,title] of [['','Choose a judgment'],['correct','Correct'],['incorrect','Incorrect'],['uncertain','Uncertain']]) select.append(new Option(title,value));
      if (item.review) select.value=item.review.verdict; label.append(select);
      const noteLabel=node('label','','Review note'); const note=node('input'); note.required=true; note.minLength=3; note.maxLength=500; note.placeholder='Compare each claim with its source'; note.value=item.review?.note || ''; noteLabel.append(note);
      const button=node('button','secondary','Save judgment'); button.type='submit'; form.append(label,noteLabel,button);
      form.addEventListener('submit',async event=>{
        event.preventDefault(); if (button.disabled) return; button.disabled=true;
        try { const updated=await api(`/api/evaluations/${encodeURIComponent(run.id)}/cases/${encodeURIComponent(item.id)}/review`,{method:'PUT',body:JSON.stringify({verdict:select.value,note:note.value.trim()})}); if (revision===insightRevision) renderEvaluation(updated,revision); }
        catch(error) { if (revision===insightRevision) reportError(error); }
        finally { button.disabled=false; }
      }); card.append(form);
    }
    content.append(card);
  }
  clearTimeout(evaluationTimer);
  if (running) evaluationTimer=setTimeout(async()=>{
    if (revision!==insightRevision || currentUser?.role!=='admin') return;
    try { const updated=await api(`/api/evaluations/${encodeURIComponent(run.id)}`); if(revision===insightRevision) { if(updated.status==='running') renderEvaluation(updated,revision); else await loadInsights(); } }
    catch(error) { if(revision===insightRevision) { reportError(error); $('insights-status').textContent='Progress refresh stopped. Click Refresh to reconnect.'; } }
  },5000);
}
const businessLabels = {
  employees:['Employees',1,10000,1], questions_per_day:['Questions per person / day',0,20,.1], adoption:['Adoption (0–1)',0,1,.05], usable_answer_rate:['Usable answer rate (0–1)',0,1,.05], minutes_saved:['Net minutes saved per usable answer',0,60,.5], employee_hourly_usd:['Employee hour value · USD',0,500,1], inference_seconds:['Seconds of inference per request',0,3600,1], working_days:['Working days / month',1,31,1], build_hours:['Implementation hours',0,1000,1], developer_hourly_usd:['Developer / support rate · USD per hour',0,500,1], support_hours_monthly:['Support hours / month',0,500,.5], power_watts:['Assumed active power · watts',0,3000,1], electricity_usd_kwh:['Electricity · USD per kWh',0,2,.01]
};
function renderBusinessScenario() {
  if (!businessScenarios) return;
  businessRevision++;
  const scenario=businessScenarios[$('business-scenario').value || 'base'];
  const fields=$('business-fields'); fields.replaceChildren(); businessControls=[];
  for(const [key,[title,min,max,step]] of Object.entries(businessLabels)) {
    const label=node('label','',title); const input=node('input'); input.type='number'; input.required=true; input.min=min; input.max=max; input.step=step; input.value=scenario.assumptions[key]; label.append(input); fields.append(label); businessControls.push([key,input]);
    input.addEventListener('input',()=>{
      businessRevision++;
      $('business-results').replaceChildren(node('p','muted','Inputs changed. Recalculate to see results for these assumptions.'));
    });
  }
  renderBusiness(scenario);
}
function renderBusiness(data) {
  const r=data.results, content=$('business-results'); content.replaceChildren();
  const grid=node('div','metric-grid'); grid.append(metricCard('Capacity value / month',displayMoney(r.monthly_capacity_value_usd),'Time saved × assumed hourly value'),metricCard('Operating cost / month',displayMoney(r.monthly_operating_usd),'Support labor + assumed electricity'),metricCard('First-year modeled ROI',displayNumber(r.first_year_roi_percent,'%'),'After implementation and operating cost'),metricCard('Payback',displayNumber(r.payback_months,' mo'),'— means no positive monthly return')); content.append(grid);
  content.append(insightCard('The arithmetic', [['Implementation effort cost',displayMoney(r.implementation_usd)],['Monthly requests',displayNumber(r.monthly_requests)],['Net hours freed / month',displayNumber(r.monthly_hours_saved)],['Net value / month',displayMoney(r.monthly_net_value_usd)],['First-year total cost',displayMoney(r.first_year_cost_usd)],['First-year net capacity value',displayMoney(r.first_year_net_value_usd)],['Sequential compute use',displayNumber(r.sequential_capacity_utilization*100,'% of an 8-hour workday')]]));
  if(r.sequential_capacity_utilization>1) content.append(node('p','review-reason','This scenario exceeds the assumed sequential compute capacity. Reduce demand or revisit deployment before treating it as feasible.'));
  content.append(node('p','muted',data.basis));
}
$('nav-insights').addEventListener('click',()=>showInsights());
$('refresh-insights').addEventListener('click',loadInsights);
for(const tab of ['overview','quality','prompts','business']) $(`insight-${tab}`).addEventListener('click',()=>showInsights(tab));
for(const id of ['insight-days','insight-scope']) $(id).addEventListener('change',loadInsights);
$('start-evaluation').addEventListener('click',async()=>{
  const revision=insightRevision; const epoch=sessionEpoch; $('start-evaluation').disabled=true; banner();
  try { const run=await api('/api/evaluations',{method:'POST',body:JSON.stringify({suite:$('evaluation-suite').value || 'quick'})}); if(revision!==insightRevision) return; selectedEvaluation=run.id; renderEvaluation(run,revision); health(); }
  catch(error) { if(revision===insightRevision) reportError(error); if(epoch===sessionEpoch) $('start-evaluation').disabled=false; }
});
$('cancel-evaluation').addEventListener('click',async()=>{
  const revision=insightRevision; $('cancel-evaluation').disabled=true;
  try { await api(`/api/evaluations/${encodeURIComponent(selectedEvaluation)}/cancel`,{method:'POST'}); if(revision===insightRevision) await loadInsights(); }
  catch(error) { if(revision===insightRevision) { $('cancel-evaluation').disabled=false; reportError(error); } }
});
$('business-scenario').addEventListener('change',renderBusinessScenario);
$('business-form').addEventListener('submit',async event=>{
  event.preventDefault(); if($('calculate-business').disabled) return;
  const revision=insightRevision, calculation=++businessRevision, epoch=sessionEpoch; $('calculate-business').disabled=true;
  const values=Object.fromEntries(businessControls.map(([key,input])=>[key,Number(input.value)]));
  try { const result=await api('/api/business-case',{method:'POST',body:JSON.stringify(values)}); if(revision===insightRevision && calculation===businessRevision) renderBusiness(result); }
  catch(error) { if(revision===insightRevision && calculation===businessRevision) reportError(error); }
  finally { if(epoch===sessionEpoch) $('calculate-business').disabled=false; }
});
(async () => { try { const user = await api('/api/me'); await enterApp(user); } catch (error) { if (!(error instanceof ObsoleteRequest)) showLogin(); } })();
