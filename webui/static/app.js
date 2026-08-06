/* LocalAssitent Web UI — клиентская логика (vanilla JS) */
const $ = (id) => document.getElementById(id);

async function api(path, body, method) {
  const opt = { method: method || 'POST', headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  try {
    const r = await fetch(path, opt);
    return await r.json();
  } catch (e) {
    return { ok: false, error: 'Сеть: ' + e.message };
  }
}

function showNote(el, text, isError) {
  if (!el) return;
  el.textContent = text || '';
  el.style.color = isError ? '#f87171' : '#4ade80';
}

function setBusy(busy) {
  $('busy').classList.toggle('hidden', !busy);
  ['btnConnect', 'btnDisconnect', 'btnSend'].forEach((id) => ($(id).disabled = busy));
}

function setBusyPipeline(busy) {
  $('busyPipeline').classList.toggle('hidden', !busy);
  ['btnRun'].forEach((id) => ($(id).disabled = busy));
}

/* ================== Навигация по вкладкам ================== */
const NAV = ['chat', 'pipeline', 'collect', 'prompts', 'logs'];
function switchView(view) {
  NAV.forEach((v) => $('view-' + v).classList.toggle('hidden', v !== view));
  document.querySelectorAll('.nav-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.view === view);
  });
  if (view === 'prompts') { refreshPrompts(); refreshPromptConfig(); }
  if (view === 'logs') refreshLogs();
}
document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.onclick = () => switchView(btn.dataset.view);
});

/* ================== Провайдеры / здоровье ================== */
async function refreshProviders() {
  const d = await api('/api/providers', undefined, 'GET');
  if (!d.ok) return;
  const sel = $('model');
  sel.innerHTML = d.qwen_models.map((m) => `<option value="${m}">${m}</option>`).join('');
  updateModelVisibility();
}

async function refreshHealth() {
  const d = await api('/api/health', undefined, 'GET');
  if (!d.ok) return;
  const badge = $('connBadge');
  badge.className = 'badge ' + (d.connected ? 'badge-on' : 'badge-off');
  badge.textContent = d.connected ? 'Подключено' : 'Не подключено';
  $('connInfo').textContent = d.connected ? `${d.provider} / ${d.model || '—'}` : '—';
}

function updateModelVisibility() {
  $('model').style.visibility = $('provider').value === 'qwen' ? 'visible' : 'hidden';
}

/* ================== Креды из .env (п.1 задачи) ================== */
window.__promptConfig = {};

async function refreshCredentials() {
  const d = await api('/api/credentials', undefined, 'GET');
  if (d.ok) {
    prefillCredentials(d);
    return d;
  }
  return null;
}

function prefillCredentials(d) {
  const provider = $('provider').value;
  const cred = d[provider];
  if (!cred) return;
  // префилл email из .env, если поле пустое
  const emailInput = $('email');
  if (!emailInput.value.trim() && cred.email) {
    emailInput.value = cred.email;
    emailInput.title = 'Подставлено из .env';
  }
  // пароль: не показываем сам, но подсвечиваем, что он есть в .env
  const passInput = $('password');
  passInput.placeholder = cred.has_password ? '•••••••• (из .env)' : '••••••••';
  passInput.title = cred.has_password ? 'Пароль будет взят из .env' : 'Пароль не задан в .env';
}

/* ================== Подключение ================== */
async function connect() {
  setBusy(true);
  showNote($('note'), 'Подключаюсь к браузеру... (Edge + авторизация, до 2–3 минут)');
  const provider = $('provider').value;
  const body = { provider, model: provider === 'qwen' ? $('model').value : null };
  const email = $('email').value.trim();
  const password = $('password').value;
  if (email) body.email = email;
  if (password) body.password = password;
  const d = await api('/api/connect', body);
  if (d.ok) showNote($('note'), `✅ Подключено: ${d.provider} / ${d.model || 'default'}`);
  else showNote($('note'), '❌ ' + (d.error || 'Ошибка подключения'), true);
  await refreshHealth();
  setBusy(false);
}

async function disconnect() {
  setBusy(true);
  const d = await api('/api/disconnect', {});
  showNote($('note'), d.ok ? 'Отключено.' : '❌ ' + (d.error || 'Ошибка'), !d.ok);
  await refreshHealth();
  setBusy(false);
}

/* ================== Чат: пары вопрос-ответ ================== */
function escHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function addChatPair(question, answer, receivedAt) {
  const log = $('chatLog');
  const pair = document.createElement('div');
  pair.className = 'chat-pair';

  const q = document.createElement('div');
  q.className = 'chat-msg chat-q';
  q.textContent = question;

  const a = document.createElement('div');
  a.className = 'chat-msg chat-a';
  a.innerHTML = '<pre>' + escHtml(answer || '(пустой ответ)') + '</pre>';

  const status = document.createElement('div');
  status.className = 'chat-status';
  if (receivedAt) {
    status.textContent = '✅ Получено ' + receivedAt;
    status.classList.add('received');
  } else {
    status.textContent = '⏳ Ожидание ответа...';
    status.classList.add('pending');
  }

  pair.appendChild(q);
  pair.appendChild(a);
  pair.appendChild(status);
  log.appendChild(pair);
  log.scrollTop = log.scrollHeight;
}

async function sendChat() {
  const message = $('message').value.trim();
  if (!message) {
    showNote($('note'), 'Введите вопрос.', true);
    return;
  }
  setBusy(true);
  $('message').value = '';
  const newChat = $('newChatChat').checked;
  const statusEl = addChatPair(message, '', null);
  showNote($('note'), 'Запущено…');
  const d = await api('/api/chat', { message, new_chat: newChat });
  if (d.ok) {
    const now = new Date().toLocaleTimeString('ru-RU');
    statusEl.querySelector('.chat-msg.chat-a pre').textContent = d.response || '(пустой ответ)';
    statusEl.querySelector('.chat-status').textContent = '✅ Получено ' + now;
    statusEl.querySelector('.chat-status').classList.remove('pending');
    statusEl.querySelector('.chat-status').classList.add('received');
    window.__lastAnswer = d.response || '';
    showNote($('note'), 'Готово.');
  } else {
    statusEl.querySelector('.chat-status').textContent = '❌ ' + (d.error || 'Ошибка');
    showNote($('note'), '❌ ' + (d.error || 'Ошибка'), true);
  }
  setBusy(false);
}

/* ================== Пайплайн ================== */
async function run() {
  const message = $('pipelineMessage').value.trim();
  if (!message) {
    showNote($('notePipeline'), 'Введите вопрос/задачу.', true);
    return;
  }
  setBusyPipeline(true);
  $('output').textContent = '…';
  showNote($('notePipeline'), 'Запущено…');
  const body = {
    pipeline: $('pipeline').value,
    message,
    new_chat: $('newChat').checked,
  };
  const dir = $('directory').value.trim();
  if (dir) body.directory = dir;
  const d = await api('/api/run', body);
  if (d.ok) {
    let out = d.response || '(пустой ответ)';
    if (d.code) out += '\n\n════════ КОД ════════\n' + d.code;
    $('output').textContent = out;
    window.__lastAnswer = out;
    showNote($('notePipeline'), d.note || 'Готово.');
  } else {
    showNote($('notePipeline'), '❌ ' + (d.error || 'Ошибка'), true);
    $('output').textContent = '';
  }
  setBusyPipeline(false);
}

/* ================== Журнал ================== */
async function refreshLogs() {
  const d = await api('/api/logs?limit=80', undefined, 'GET');
  if (d.ok) $('logs').textContent = d.logs.join('\n') || '(пусто)';
}

/* ================== Сбор файлов ================== */
async function collect() {
  const box = $('collectResult');
  const directories = $('collectDirs').value
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!directories.length) {
    box.textContent = 'Укажите хотя бы одну директорию.';
    box.style.color = '#f87171';
    return;
  }
  box.textContent = '⏳ Собираю файлы…';
  box.style.color = '#4ade80';
  $('btnCollect').disabled = true;
  const body = {
    directories,
    project_type: $('collectType').value,
    filename: $('collectFilename').value.trim() || 'cloud_context.txt',
  };
  const d = await api('/api/collect', body);
  if (d.ok) {
    box.style.color = '#4ade80';
    box.innerHTML = `<pre>${d.message}</pre>` +
      `<a class="dl" href="${d.download_url}" target="_blank">⬇️ Скачать: ${d.file} (${d.size} байт)</a>`;
  } else {
    box.style.color = '#f87171';
    box.textContent = '❌ ' + (d.error || 'Ошибка');
  }
  $('btnCollect').disabled = false;
}

/* ================== Промпты (CRUD) ================== */
const PIPELINE_LABELS = { qa: 'Чат Q&A', code: 'Вопрос — код', merge: 'Проект → облако', improve: 'Improve' };

async function refreshPrompts() {
  const d = await api('/api/prompts', undefined, 'GET');
  if (!d.ok) return;
  const tbody = $('promptTableBody');
  tbody.innerHTML = d.prompts.map((p) => {
    const active = p.is_active ? '✅' : '❌';
    return `<tr>
      <td>${p.id}</td>
      <td>${PIPELINE_LABELS[p.pipeline] || p.pipeline}</td>
      <td>${p.stage}</td>
      <td title="${escHtml(p.content.slice(0, 120))}">${escHtml(p.name)}</td>
      <td>${active}</td>
      <td class="actions">
        <button class="btn btn-mini" data-act="edit" data-id="${p.id}">✏️</button>
        <button class="btn btn-mini" data-act="delete" data-id="${p.id}">🗑️</button>
        <button class="btn btn-mini" data-act="first" data-id="${p.id}" data-pipe="${p.pipeline}">1️⃣</button>
        <button class="btn btn-mini" data-act="subsequent" data-id="${p.id}" data-pipe="${p.pipeline}">2️⃣</button>
      </td>
    </tr>`;
  }).join('');
  tbody.querySelectorAll('button[data-act]').forEach((btn) => {
    btn.onclick = () => promptAction(btn.dataset.act, btn.dataset.id, btn.dataset.pipe);
  });
}

async function refreshPromptConfig() {
  const d = await api('/api/prompt-config', undefined, 'GET');
  if (!d.ok) return;
  window.__promptConfig = d.config || {};
  const box = $('promptConfigBox');
  box.innerHTML = Object.entries(window.__promptConfig).map(([pipe, cfg]) => {
    const first = cfg.first != null ? `#${cfg.first}` : '—';
    const sub = cfg.subsequent != null ? `#${cfg.subsequent}` : '—';
    return `<div class="config-row"><span class="pipe">${PIPELINE_LABELS[pipe] || pipe}</span>
      <span class="kv"><b>first:</b> ${first}</span>
      <span class="kv"><b>subsequent:</b> ${sub}</span></div>`;
  }).join('') || '(пусто)';
}

async function promptAction(act, id, pipe) {
  if (act === 'delete') {
    if (!confirm('Удалить промпт #' + id + '?')) return;
    const d = await api('/api/prompts/' + id, undefined, 'DELETE');
    if (!d.ok) { alert(d.error || 'Ошибка удаления'); return; }
    refreshPrompts(); refreshPromptConfig();
    return;
  }
  if (act === 'first' || act === 'subsequent') {
    const d = await api('/api/prompt-config', {
      pipeline: pipe, stage: act, prompt_id: parseInt(id, 10),
    });
    if (!d.ok) { alert(d.error || 'Ошибка назначения'); return; }
    refreshPromptConfig();
    return;
  }
  if (act === 'edit') {
    const d = await api('/api/prompts', undefined, 'GET');
    const p = d.prompts.find((x) => x.id === parseInt(id, 10));
    if (!p) return;
    $('pfEditId').value = p.id;
    $('pfPipeline').value = p.pipeline;
    $('pfStage').value = p.stage;
    $('pfName').value = p.name;
    $('pfContent').value = p.content;
    $('btnPromptCancel').classList.remove('hidden');
    $('pfContent').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function createPrompt() {
  const body = {
    pipeline: $('pfPipeline').value,
    stage: $('pfStage').value,
    name: $('pfName').value.trim(),
    content: $('pfContent').value,
  };
  const editId = $('pfEditId').value;
  if (!body.name || !body.content) { alert('Укажите название и содержимое.'); return; }
  let d;
  if (editId) {
    d = await api('/api/prompts/' + editId, { name: body.name, content: body.content, stage: body.stage });
  } else {
    d = await api('/api/prompts', body);
  }
  if (!d.ok) { alert(d.error || 'Ошибка сохранения'); return; }
  $('pfEditId').value = '';
  $('pfName').value = '';
  $('pfContent').value = '';
  $('btnPromptCancel').classList.add('hidden');
  refreshPrompts(); refreshPromptConfig();
}

/* ================== События ================== */
$('btnConnect').onclick = connect;
$('btnDisconnect').onclick = disconnect;
$('btnSend').onclick = sendChat;
$('btnRun').onclick = run;
$('btnCollect').onclick = collect;
$('btnPromptCreate').onclick = createPrompt;
$('btnPromptCancel').onclick = () => {
  $('pfEditId').value = '';
  $('pfName').value = '';
  $('pfContent').value = '';
  $('btnPromptCancel').classList.add('hidden');
};
$('btnCopy').onclick = () => {
  const el = document.querySelector('#chatLog .chat-pair:last-child .chat-a pre');
  const text = el ? el.textContent : '';
  if (text) navigator.clipboard.writeText(text).then(() => showNote($('note'), 'Ответ скопирован.'));
};
$('btnCopyPipeline').onclick = () => {
  const text = $('output').textContent;
  if (text && text !== '—') navigator.clipboard.writeText(text).then(() => showNote($('notePipeline'), 'Ответ скопирован.'));
};
$('provider').onchange = () => { updateModelVisibility(); refreshCredentials(); };
$('message').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

/* модальное окно справки */
$('btnHelp').onclick = () => $('helpModal').classList.remove('hidden');
$('btnCloseHelp').onclick = () => $('helpModal').classList.add('hidden');
$('helpModal').onclick = (e) => {
  if (e.target === $('helpModal')) $('helpModal').classList.add('hidden');
};

/* старт */
refreshProviders();
refreshHealth();
refreshCredentials();
refreshLogs();
setInterval(refreshLogs, 3000);
setInterval(refreshHealth, 5000);
