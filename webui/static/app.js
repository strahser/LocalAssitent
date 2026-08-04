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

function showNote(text, isError) {
  const n = $('note');
  n.textContent = text || '';
  n.style.color = isError ? '#f87171' : '#4ade80';
}

function setBusy(busy) {
  $('busy').classList.toggle('hidden', !busy);
  ['btnConnect', 'btnDisconnect', 'btnRun'].forEach((id) => ($(id).disabled = busy));
}

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

async function connect() {
  setBusy(true);
  showNote('Подключаюсь к браузеру... (Edge + авторизация, до 2–3 минут)');
  const provider = $('provider').value;
  const body = { provider, model: provider === 'qwen' ? $('model').value : null };
  const email = $('email').value.trim();
  const password = $('password').value;
  if (email) body.email = email;
  if (password) body.password = password;
  const d = await api('/api/connect', body);
  if (d.ok) showNote(`✅ Подключено: ${d.provider} / ${d.model || 'default'}`);
  else showNote('❌ ' + (d.error || 'Ошибка подключения'), true);
  await refreshHealth();
  setBusy(false);
}

async function disconnect() {
  setBusy(true);
  const d = await api('/api/disconnect', {});
  showNote(d.ok ? 'Отключено.' : '❌ ' + (d.error || 'Ошибка'), !d.ok);
  await refreshHealth();
  setBusy(false);
}

async function run() {
  const message = $('message').value.trim();
  if (!message) {
    showNote('Введите вопрос/задачу.', true);
    return;
  }
  setBusy(true);
  $('output').textContent = '…';
  showNote('Запущено…');
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
    showNote(d.note || 'Готово.');
  } else {
    showNote('❌ ' + (d.error || 'Ошибка'), true);
    $('output').textContent = '';
  }
  setBusy(false);
}

async function refreshLogs() {
  const d = await api('/api/logs?limit=80', undefined, 'GET');
  if (d.ok) $('logs').textContent = d.logs.join('\n') || '(пусто)';
}

/* события */
$('btnConnect').onclick = connect;
$('btnDisconnect').onclick = disconnect;
$('btnRun').onclick = run;
$('btnCopy').onclick = () => {
  const text = $('output').textContent;
  if (text && text !== '—') {
    navigator.clipboard.writeText(text).then(() => showNote('Ответ скопирован.'));
  }
};
$('provider').onchange = updateModelVisibility;

/* старт */
refreshProviders();
refreshHealth();
refreshLogs();
setInterval(refreshLogs, 3000);
setInterval(refreshHealth, 5000);
