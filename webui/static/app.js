/* LocalAssitent Web UI — два режима: вопрос-ответ и сводный файл (TDL) */
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

function setBusyMerge(busy) {
  $('busyMerge').classList.toggle('hidden', !busy);
  ['btnMergeSend', 'btnMergeOnly'].forEach((id) => ($(id).disabled = busy));
}

/* ================== Навигация (две вкладки) ================== */
const NAV = ['chat', 'merge', 'logs'];
function switchView(view) {
  NAV.forEach((v) => $('view-' + v).classList.toggle('hidden', v !== view));
  document.querySelectorAll('.nav-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.view === view);
  });
  if (view === 'merge') { refreshMergePrompts(); ensureDefaultPrompt(); }
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

/* ================== Креды из .env ================== */
async function refreshCredentials() {
  const d = await api('/api/credentials', undefined, 'GET');
  if (d.ok) prefillCredentials(d);
}

function prefillCredentials(d) {
  const provider = $('provider').value;
  const cred = d[provider];
  if (!cred) return;
  const emailInput = $('email');
  if (!emailInput.value.trim() && cred.email) {
    emailInput.value = cred.email;
    emailInput.title = 'Подставлено из .env';
  }
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

/* ================== Вопрос — ответ ================== */
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
  if (!message) { showNote($('note'), 'Введите вопрос.', true); return; }
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

/* ================== Сводный файл (merge, TDL) ================== */

/* База промптов → селектор. По умолчанию подставляем TDL-промпт в окно. */
let __promptsCache = [];

async function refreshMergePrompts() {
  const d = await api('/api/prompts', undefined, 'GET');
  if (!d.ok) return;
  __promptsCache = d.prompts || [];
  const sel = $('promptSelect');
  sel.innerHTML = __promptsCache
    .filter((p) => p.pipeline === 'merge' || p.pipeline === 'qa')
    .map((p) => `<option value="${p.id}">#${p.id} ${escHtml(p.name)} (${p.pipeline}/${p.stage})</option>`)
    .join('');
}

function ensureDefaultPrompt() {
  // Если окно промпта пустое — подставить TDL-промпт по умолчанию из БД (merge first).
  if ($('mergePrompt').value.trim()) return;
  const tpl = __promptsCache.find((p) => p.pipeline === 'merge' && p.stage === 'first');
  if (tpl) $('mergePrompt').value = tpl.content;
}

function useSelectedPrompt() {
  const id = parseInt($('promptSelect').value, 10);
  const p = __promptsCache.find((x) => x.id === id);
  if (p) $('mergePrompt').value = p.content;
}

function resetPromptToTdl() {
  const tpl = __promptsCache.find((p) => p.pipeline === 'merge' && p.stage === 'first');
  $('mergePrompt').value = tpl ? tpl.content : '';
}

async function mergeSend() {
  const localPrompt = $('mergePrompt').value.trim();
  const dir = $('mergeDir').value.trim();
  const filename = $('mergeFilename').value.trim() || 'cloud_context.txt';
  if (!localPrompt) { showNote($('noteMerge'), 'Введите локальный промпт.', true); return; }
  setBusyMerge(true);
  $('output').textContent = '…';
  showNote($('noteMerge'), 'Собираю сводный файл + отправляю в ИИ…');
  const body = {
    pipeline: 'merge',
    message: localPrompt,
    directory: dir || undefined,
    filename,
    new_chat: $('mergeNewChat').checked,
  };
  const d = await api('/api/run', body);
  if (d.ok) {
    let out = d.response || '(пустой ответ)';
    if (d.code) out += '\n\n════════ КОД ════════\n' + d.code;
    $('output').textContent = out;
    window.__lastAnswer = out;
    showNote($('noteMerge'), d.note || 'Готово.');
  } else {
    showNote($('noteMerge'), '❌ ' + (d.error || 'Ошибка'), true);
    $('output').textContent = '';
  }
  setBusyMerge(false);
}

async function mergeOnly() {
  const localPrompt = $('mergePrompt').value.trim();
  const dirs = $('mergeDir').value
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!dirs.length) { showNote($('noteMerge'), 'Укажите директорию.', true); return; }
  const box = $('mergeResult');
  box.textContent = '⏳ Собираю файлы…';
  box.style.color = '#4ade80';
  setBusyMerge(true);
  const body = {
    directories: dirs,
    project_type: 'auto',
    filename: $('mergeFilename').value.trim() || 'cloud_context.txt',
    local_prompt: localPrompt,
  };
  const d = await api('/api/collect', body);
  if (d.ok) {
    box.style.color = '#4ade80';
    box.innerHTML = `<pre>${escHtml(d.message)}</pre>` +
      `<a class="dl" href="${d.download_url}" target="_blank">⬇️ Скачать: ${escHtml(d.file)} (${d.size} байт)</a>`;
    showNote($('noteMerge'), 'Сводный файл готов.');
  } else {
    box.style.color = '#f87171';
    box.textContent = '❌ ' + escHtml(d.error || 'Ошибка');
  }
  setBusyMerge(false);
}

/* ================== Журнал ================== */
async function refreshLogs() {
  const d = await api('/api/logs?limit=80', undefined, 'GET');
  if (d.ok) $('logs').textContent = d.logs.join('\n') || '(пусто)';
}

/* ================== События ================== */
$('btnConnect').onclick = connect;
$('btnDisconnect').onclick = disconnect;
$('btnSend').onclick = sendChat;
$('btnMergeSend').onclick = mergeSend;
$('btnMergeOnly').onclick = mergeOnly;
$('btnUsePrompt').onclick = useSelectedPrompt;
$('btnResetPrompt').onclick = resetPromptToTdl;
$('btnCopy').onclick = () => {
  const el = document.querySelector('#chatLog .chat-pair:last-child .chat-a pre');
  const text = el ? el.textContent : '';
  if (text) navigator.clipboard.writeText(text).then(() => showNote($('note'), 'Ответ скопирован.'));
};
$('btnCopyMerge').onclick = () => {
  const text = $('output').textContent;
  if (text && text !== '—') navigator.clipboard.writeText(text).then(() => showNote($('noteMerge'), 'Ответ скопирован.'));
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
refreshMergePrompts();
setInterval(refreshLogs, 3000);
setInterval(refreshHealth, 5000);
