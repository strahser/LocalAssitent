/* LocalAssitent Web UI — вопросы-ответ, сводный файл, управление промптами, журнал */
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
  ['btnConnect', 'btnDisconnect', 'btnSend'].forEach((id) => { const el = $(id); if (el) el.disabled = busy; });
}

function setBusyMerge(busy) {
  $('busyMerge').classList.toggle('hidden', !busy);
  ['btnMergeSend', 'btnMergeOnly'].forEach((id) => ($(id).disabled = busy));
}

/* ================== Markdown (лёгкий рендер без зависимостей) ================== */
function inlineMdInline(s) {
  let out = esc(s);
  out = out.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[^*\W])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return out;
}

function isListMarker(s) {
  return /^[-*+]\s+/.test(s) || /^\d+[.)]\s+/.test(s);
}

function renderMarkdown(src) {
  if (!src) return '';
  const lines = String(src).replace(/\r\n/g, '\n').split('\n');
  const out = [];
  let list = null;
  const flushList = () => {
    if (list) {
      const tag = list.type === 'ul' ? 'ul' : 'ol';
      out.push(`<${tag}>` + list.items.map((it) => `<li>${inlineMdInline(it)}</li>`).join('') + `</${tag}>`);
      list = null;
    }
  };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // код-блок
    if (/^```/.test(trimmed)) {
      flushList();
      const buf = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i].trim())) { buf.push(lines[i]); i++; }
      i++; // закрывающие ```
      out.push(`<pre class="code"><code>${esc(buf.join('\n'))}</code></pre>`);
      continue;
    }

    // заголовок
    if (/^#{1,6}\s+/.test(trimmed)) {
      flushList();
      const level = trimmed.match(/^(#{1,6})/)[1].length;
      const text = trimmed.replace(/^#{1,6}\s+/, '').replace(/\s+#+$/, '');
      out.push(`<h${level}>${inlineMdInline(text)}</h${level}>`);
      i++;
      continue;
    }

    // горизонтальная линия
    if (/^([-*_])(\s*\1){2,}\s*$/.test(trimmed)) {
      flushList();
      out.push('<hr>');
      i++;
      continue;
    }

    // список
    if (isListMarker(trimmed)) {
      const type = /^[-*+]\s+/.test(trimmed) ? 'ul' : 'ol';
      if (!list) list = { type, items: [] };
      list.items.push(trimmed.replace(/^[-*+]\s+/, '').replace(/^\d+[.)]\s+/, ''));
      i++;
      continue;
    }

    // таблица: | a | b | + |---|---|
    if (/^\|/.test(trimmed) && i + 1 < lines.length &&
        /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('---')) {
      flushList();
      const header = trimmed.split('|').slice(1, -1).map((c) => c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|\s*.+\|/.test(lines[i].trim())) {
        const cells = lines[i].trim().split('|').slice(1, -1).map((c) => c.trim());
        rows.push(`<tr>${cells.map((c) => `<td>${inlineMdInline(c)}</td>`).join('')}</tr>`);
        i++;
      }
      out.push(`<table><thead><tr>${header.map((c) => `<th>${inlineMdInline(c)}</th>`).join('')}</tr></thead>` +
        `<tbody>${rows.join('')}</tbody></table>`);
      continue;
    }

    if (trimmed) {
      flushList();
      if (trimmed.startsWith('>')) {
        out.push(`<blockquote>${inlineMdInline(trimmed.replace(/^>\s?/, ''))}</blockquote>`);
      } else {
        out.push(`<p>${inlineMdInline(trimmed)}</p>`);
      }
    }
    i++;
  }
  flushList();
  return out.join('');
}

/* ================== Навигация ================== */
const NAV = ['chat', 'merge', 'prompts', 'logs'];
async function switchView(view) {
  NAV.forEach((v) => $('view-' + v).classList.toggle('hidden', v !== view));
  document.querySelectorAll('.nav-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.view === view);
  });
  if (view === 'merge') { await refreshMergePrompts(); ensureDefaultPrompt(); updateMergePromptCard(); }
  if (view === 'prompts') { await refreshPromptFiles(); }
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
  const credential = d[$('provider').value];
  if (!credential) return;
  const emailInput = $('email');
  if (!emailInput.value.trim() && credential.email) {
    emailInput.value = credential.email;
    emailInput.title = 'Подставлено из .env';
  }
  const passInput = $('password');
  passInput.placeholder = credential.has_password ? '•••••••• (из .env)' : '••••••••';
  passInput.title = credential.has_password ? 'Пароль будет взят из .env' : 'Пароль не задан в .env';
}

/* ================== Подключение ================== */
async function connect() {
  setBusy(true);
  showToast('Подключаюсь к браузеру... (Edge + авторизация, до 2–3 минут)');
  const provider = $('provider').value;
  const body = { provider, model: provider === 'qwen' ? $('model').value : null };
  const email = $('email').value.trim();
  const password = $('password').value;
  if (email) body.email = email;
  if (password) body.password = password;
  const d = await api('/api/connect', body);
  if (d.ok) showToast(`✅ Подключено: ${d.provider} / ${d.model || 'default'}`);
  else showToast('❌ ' + (d.error || 'Ошибка подключения'), true);
  await refreshHealth();
  setBusy(false);
}

async function disconnect() {
  setBusy(true);
  const d = await api('/api/disconnect', {});
  showToast(d.ok ? 'Отключено.' : '❌ ' + (d.error || 'Ошибка'), !d.ok);
  await refreshHealth();
  setBusy(false);
}

/* ================== Q&A конвейер ================== */
function setBusyQa(busy) {
  $('busyQa').classList.toggle('hidden', !busy);
  $('btnQaRun').disabled = busy;
}

function qaAnswerHtml(text) { return text; }

async function qaRun() {
  const prompt = $('qaPrompt').value.trim();
  const inputFile = $('qaInputFile').value.trim();
  const outputFile = $('qaOutputFile').value.trim();
  if (!inputFile) { showNote($('noteQa'), 'Укажите файл с вопросами (input_file).', true); return; }
  setBusyQa(true);
  $('qaHistory').innerHTML = '';
  showNote($('noteQa'), 'Запускаю построчный конвейер...');
  const body = { prompt, input_file: inputFile, output_file: outputFile, new_chat: $('qaNewChat').checked };
  const d = await api('/api/qa-file', body);
  if (d.ok) {
    const hist = d.history || [];
    $('qaHistory').innerHTML = hist.map((it) =>
      '<div class="chat-pair">' +
      '<div class="chat-msg chat-q">' + escapeHtml(it.q) + '</div>' +
      '<div class="chat-msg chat-a md-body">' + renderMarkdown(it.a) + '</div>' +
      '</div>').join('');
    window.__lastHistory = hist;
    const dl = d.download_url ? ` <a class="dl" href="${d.download_url}" target="_blank">⬇️ Скачать ответы</a>` : '';
    showNote($('noteQa'), `✅ Готово: ${d.total} ответов → ${d.output_file}${dl}`);
  } else {
    showNote($('noteQa'), '❌ ' + (d.error || 'Ошибка'), true);
  }
  setBusyQa(false);
}

/* ================== Сводный файл (merge) ================== */
let __promptsCache = [];

async function refreshMergePrompts() {
  const d = await api('/api/prompts', undefined, 'GET');
  if (!d.ok) return;
  __promptsCache = d.prompts || [];
}

function ensureDefaultPrompt() {
  if ($('mergePrompt').value.trim()) return;
  const tpl = __promptsCache.find((p) => p.pipeline === 'merge' && p.stage === 'first');
  if (tpl) $('mergePrompt').value = tpl.content;
}

async function useSelectedPrompt() {
  const file = __selectedPromptFile;
  if (!file) { showToast('Сначала откройте промпт на вкладке «Промпты» (клик по строке).', true); return; }
  const d = await api('/api/prompt-file?path=' + encodeURIComponent(file), undefined, 'GET');
  if (d.ok) {
    $('mergePrompt').value = d.content || '';
    updateMergePromptCard();
    showToast('Промпт «' + file + '» вставлен ✓');
  } else {
    showToast('❌ ' + (d.error || 'Ошибка'), true);
  }
}

function resetPromptToTdl() {
  const tpl = __promptsCache.find((p) => p.pipeline === 'merge' && p.stage === 'first');
  $('mergePrompt').value = tpl ? tpl.content : '';
  updateMergePromptCard();
}

function renderOutput(el, text) {
  if (el.dataset.raw === '1' || !$('mdToggle').checked) {
    el.innerHTML = '<pre>' + escapeHtml(text) + '</pre>';
  } else {
    el.innerHTML = renderMarkdown(text);
  }
}

async function mergeSend() {
  const localPrompt = $('mergePrompt').value.trim();
  const dirs = splitPaths($('mergeDirs').value);
  const filename = $('mergeFilename').value.trim() || 'cloud_context.txt';
  if (!localPrompt) { showNote($('noteMerge'), 'Введите локальный промпт (или нажмите «По умолчанию TDL»).', true); return; }
  if (!dirs.length) { showNote($('noteMerge'), 'Укажите хотя бы один путь (директорию или файл).', true); return; }
  setBusyMerge(true);
  $('output').innerHTML = '';
  showNote($('noteMerge'), 'Собираю сводный файл + отправляю в ИИ…');
  const body = {
    pipeline: 'merge',
    message: localPrompt,
    directories: dirs,
    project_type: $('mergeType').value || 'auto',
    filename,
    new_chat: $('mergeNewChat').checked,
  };
  const d = await api('/api/run', body);
  if (d.ok) {
    let out = d.response || '(пустой ответ)';
    if (d.code) out += '\n\n════════ КОД ════════\n' + d.code;
    renderOutput($('output'), out);
    window.__lastAnswer = out;
    showNote($('noteMerge'), d.note || 'Готово.');
  } else {
    showNote($('noteMerge'), '❌ ' + (d.error || 'Ошибка'), true);
    $('output').innerHTML = '';
  }
  setBusyMerge(false);
}

function splitPaths(text) {
  return String(text || '').split(/\r?\n/).map((s) => s.trim().replace(/^"|"$/g, '')).filter(Boolean);
}

async function mergeOnly() {
  const dirs = splitPaths($('mergeDirs').value);
  if (!dirs.length) { showNote($('noteMerge'), 'Укажите хотя бы один путь (директорию или файл).', true); return; }
  const box = $('mergeResult');
  box.innerHTML = '<span>⏳ Собираю файлы…</span>';
  box.style.color = '#4ade80';
  setBusyMerge(true);
  const body = {
    directories: dirs,
    project_type: $('mergeType').value || 'auto',
    filename: $('mergeFilename').value.trim() || 'cloud_context.txt',
    local_prompt: $('mergePrompt').value.trim(),
  };
  const d = await api('/api/collect', body);
  if (d.ok) {
    box.style.color = '#4ade80';
    box.innerHTML = `<pre>${escapeHtml(d.message)}</pre>` +
      `<a class="dl" href="${d.download_url}" target="_blank">⬇️ Скачать: ${escapeHtml(d.file)} (${d.size} байт)</a>`;
    showNote($('noteMerge'), 'Сводный файл готов.');
  } else {
    box.style.color = '#f87171';
    box.textContent = '❌ ' + escapeHtml(d.error || 'Ошибка');
  }
  setBusyMerge(false);
}

/* ================== Промпты (вкладка) ================== */
let __promptFiles = [];
let __selectedPromptFile = null;
let __lastFileContent = null;

async function refreshPromptFiles() {
  const d = await api('/api/prompt-files', undefined, 'GET');
  if (d.ok) setPromptFiles(d.files || [], d.prompts_dir || '');
  else showToast(d.error || 'Ошибка', true);
}

function setPromptFiles(files, dir) {
  __promptFiles = files;
  $('promptsDirHint').textContent =
    `Папка: ${dir} — ${files.length} файлов. Клик по строке — просмотр, кнопки: просмотр / редактирование / удаление / вставить.`;
  const body = $('promptFilesBody');
  body.innerHTML = files.map((f) =>
    `<tr data-file="${escapeHtml(f.file)}">
       <td><strong>${escapeHtml(f.name)}</strong><div class="sub">${escapeHtml(f.file)}</div></td>
       <td>${escapeHtml(f.description || '—')}</td>
       <td>${f.created_at ? f.created_at.replace('T', ' ') : '—'}</td>
       <td>${f.modified_at ? f.modified_at.replace('T', ' ') : '—'}</td>
       <td class="num">${formatSize(f.size)}</td>
       <td class="actions">
         <button class="btn-mini" data-act="view" data-file="${esc(f.file)}" title="Просмотреть">👁️</button>
         <button class="btn-mini" data-act="edit" data-file="${esc(f.file)}" title="Редактировать">✏️</button>
         <button class="btn-mini" data-act="del" data-file="${esc(f.file)}" title="Удалить">🗑️</button>
         <button class="btn-mini" data-act="insert" data-file="${esc(f.file)}" title="Вставить в сводный файл">📋</button>
       </td>
     </tr>`).join('');
  if (!files.length) body.innerHTML = '<tr><td colspan="6">Промпты не найдены.</td></tr>';
}

function formatSize(b) {
  if (b == null) return '—';
  if (b < 1024) return b + ' Б';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' КБ';
  return (b / (1024 * 1024)).toFixed(1) + ' МБ';
}

async function promptLoad(file) {
  const d = await api('/api/prompt-file?path=' + encodeURIComponent(file), undefined, 'GET');
  if (d.ok) {
    __lastFileContent = { file, content: d.content || '' };
    return __lastFileContent;
  }
  showToast('❌ ' + (d.error || 'Ошибка'), true);
  return null;
}

async function insertSelectedPromptToMerge() {
  let src = __lastFileContent || (__selectedPromptFile ? await promptLoad(__selectedPromptFile) : null);
  if (!src || !src.content) { showToast('Сначала откройте промпт (клик по строке).', true); return; }
  $('mergePrompt').value = src.content;
  showToast('Промпт «' + src.file + '» → сводный файл ✓');
  switchView('merge');
}

/* ---------- Модальное окно промпта ---------- */
let __pmMode = 'view'; // view | edit | new | merge

function pmSetView(view) {
  $('pmGrid').dataset.view = view;
  document.querySelectorAll('.pm-viewswitch button').forEach((b) => {
    b.classList.toggle('active', b.dataset.pmview === view);
  });
}

function pmShow(mode, file) {
  __pmMode = mode || 'view';
  const isMerge = mode === 'merge';
  $('promptModalTitle').textContent =
    isMerge ? '📝 Промпт для сводного файла'
      : mode === 'new' ? '➕ Новый промпт'
      : mode === 'edit' ? '✏️ Редактирование: ' + (file || '')
      : '👁️ Просмотр: ' + (file || '');
  $('pmNameRow').style.display = isMerge ? 'none' : '';
  $('pmName').readOnly = mode !== 'new';
  $('pmName').value = isMerge ? '' : (mode === 'new' ? '' : (file || ''));
  $('btnPromptSave').classList.toggle('hidden', mode === 'view');
  $('btnPromptCloseFooter').classList.toggle('hidden', false);
  $('pmContent').value = isMerge ? ($('mergePrompt').value || '') : '';
  $('pmContent').readOnly = mode === 'view';
  $('pmPreview').innerHTML = '';
  $('promptModal').classList.remove('hidden');
  const mc = $('promptModal').querySelector('.modal-content');
  if (window.__pmWasMaximized) mc.classList.add('maximized');
  pmSetView('preview');
  pmPreview();
  $('pmContent').focus();
}

function pmToggleMaximize() {
  const mc = $('promptModal').querySelector('.modal-content');
  mc.classList.toggle('maximized');
  window.__pmWasMaximized = mc.classList.contains('maximized');
  $('btnMaximizePrompt').textContent = window.__pmWasMaximized ? '🗗' : '⛶';
}

function pmClose() {
  $('promptModal').classList.add('hidden');
}

async function pmOpenView(file) {
  __selectedPromptFile = file;
  document.querySelectorAll('#promptFilesBody tr').forEach((tr) => {
    tr.classList.toggle('sel', tr.dataset.file === file);
  });
  pmShow('view', file);
  const src = await promptLoad(file);
  if (src) { $('pmContent').value = src.content; pmPreview(); }
}

async function pmOpenEdit(file) {
  __selectedPromptFile = file;
  document.querySelectorAll('#promptFilesBody tr').forEach((tr) => {
    tr.classList.toggle('sel', tr.dataset.file === file);
  });
  pmShow('edit', file);
  const src = await promptLoad(file);
  if (src) { $('pmContent').value = src.content; pmPreview(); }
}

function pmOpenNew() {
  pmShow('new', '');
  $('pmName').value = new Date().toISOString().slice(0, 10) + '_prompt.txt';
}

function pmPreview() {
  const raw = $('pmContent').value || '';
  const box = $('pmPreview');
  if (raw.trim().startsWith('<') || /<\s*(h[1-6]|div|p|table|ul|ol|code)\b/i.test(raw)) {
    box.innerHTML = raw;
  } else if (raw.trim()) {
    box.innerHTML = renderMarkdown(raw);
  } else {
    box.innerHTML = 'Введите текст — предпросмотр появится здесь.';
  }
}

async function pmSave() {
  const name = $('pmName').value.trim();
  const content = $('pmContent').value;
  if (__pmMode === 'merge') {
    $('mergePrompt').value = content;
    updateMergePromptCard();
    pmClose();
    showToast('Промпт для сводного файла сохранён ✓');
    return;
  }
  if (__pmMode === 'new') {
    if (!name) { showToast('Укажите имя файла.', true); return; }
    const d = await api('/api/prompt-file', { name, content });
    if (!d.ok) { showToast('❌ ' + (d.error || 'Ошибка'), true); return; }
    __selectedPromptFile = d.file ? d.file.file : name;
    showToast('Промпт «' + name + '» создан ✓');
  } else {
    if (!__selectedPromptFile) { showToast('Не выбран файл для редактирования.', true); return; }
    const d = await api('/api/prompt-file?path=' + encodeURIComponent(__selectedPromptFile), { content }, 'PUT');
    if (!d.ok) { showToast('❌ ' + (d.error || 'Ошибка'), true); return; }
    __lastFileContent = { file: __selectedPromptFile, content };
    showToast('Промпт сохранён ✓');
  }
  pmClose();
  refreshPromptFiles();
}

/* ---------- Карточка промпта сводного файла ---------- */
function updateMergePromptCard() {
  const v = ($('mergePrompt').value || '').trim();
  const card = $('mergePromptCard');
  if (!card) return;
  if (!v) {
    $('mergePromptEmpty').style.display = '';
    $('mergePromptPreview').style.display = 'none';
    $('mergePromptPreview').innerHTML = '';
    return;
  }
  $('mergePromptEmpty').style.display = 'none';
  const box = $('mergePromptPreview');
  box.style.display = '';
  if (v.trim().startsWith('<') || /<\s*(h[1-6]|div|p|table|ul|ol|code)\b/i.test(v)) {
    box.innerHTML = v;
  } else {
    box.innerHTML = renderMarkdown(v);
  }
}

function pmOpenMerge() {
  pmShow('merge', '');
}

async function pmDelete(file) {
  if (!confirm('Удалить промпт «' + file + '»?')) return;
  const d = await api('/api/prompt-file?path=' + encodeURIComponent(file), undefined, 'DELETE');
  if (!d.ok) { showToast('❌ ' + (d.error || 'Ошибка'), true); return; }
  if (__selectedPromptFile === file) { __selectedPromptFile = null; __lastFileContent = null; }
  showToast('Промпт «' + file + '» удалён ✓');
  refreshPromptFiles();
}

async function insertFilePromptToMerge(file) {
  const src = await promptLoad(file);
  if (src) { $('mergePrompt').value = src.content; updateMergePromptCard(); switchView('merge'); }
}

function renderQaRaw() {}

/* ================== Прочее (UI-хелперы) ================== */
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
function escapeHtml(s) { return esc(s); }
function escapeHtmlSafe(s) { return esc(s); }

let __toastTimer = null;
function showToast(msg, isErr) {
  const t = $('toastMsg');
  if (!t) return;
  t.textContent = msg;
  t.style.color = isErr ? '#f87171' : '#4ade80';
  t.classList.remove('hidden');
  clearTimeout(__toastTimer);
  __toastTimer = setTimeout(() => t.classList.add('hidden'), 4000);
}

/* ================== Журнал ================== */
async function refreshLogs() {
  const d = await api('/api/logs?limit=80', undefined, 'GET');
  if (d.ok) $('logs').textContent = d.logs.join('\n') || '(пусто)';
}

/* ================== События ================== */
window.addEventListener('DOMContentLoaded', () => {
  $('btnConnect').onclick = connect;
  $('btnDisconnect').onclick = disconnect;
  $('btnQaRun').onclick = qaRun;
  $('btnQaCopy').onclick = () => {
    const hist = window.__lastHistory || [];
    const text = hist.map((it) => 'Вопрос: ' + it.q + '\n\nОтвет: ' + it.a).join('\n\n---\n\n');
    if (text) navigator.clipboard.writeText(text).then(() => showToast('История скопирована.'));
  };
  $('btnMergeSend').onclick = mergeSend;
  $('btnMergeOnly').onclick = mergeOnly;
  $('btnUsePrompt').onclick = useSelectedPrompt;
  $('btnResetPrompt').onclick = resetPromptToTdl;
  $('mergePromptCard').onclick = pmOpenMerge;
  document.querySelectorAll('.pm-viewswitch button').forEach((b) => {
    b.onclick = () => { pmSetView(b.dataset.pmview); $('pmContent').focus(); };
  });
  $('btnCopyMerge').onclick = () => {
    const text = $('output').textContent;
    if (text && text !== '—') navigator.clipboard.writeText(text).then(() => showToast('Ответ скопирован.'));
  };
  $('provider').onchange = () => { updateModelVisibility(); refreshCredentials(); };

  // Промпты: файлы
  $('btnPromptRefresh').onclick = refreshPromptFiles;
  $('btnPromptNew').onclick = pmOpenNew;
  $('btnPromptView').onclick = () => {
    if (!__selectedPromptFile) { showToast('Сначала выберите промпт (клик по строке).', true); return; }
    pmOpenView(__selectedPromptFile);
  };
  $('btnPromptLoadMerge').onclick = insertSelectedPromptToMerge;
  $('promptFilesBody').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-act]');
    if (btn) {
      const file = btn.dataset.file;
      if (btn.dataset.act === 'view') pmOpenView(file);
      if (btn.dataset.act === 'edit') pmOpenEdit(file);
      if (btn.dataset.act === 'del') pmDelete(file);
      if (btn.dataset.act === 'insert') insertFilePromptToMerge(file);
      return;
    }
    const tr = e.target.closest('tr[data-file]');
    if (tr) pmOpenView(tr.dataset.file);
  });

  // Модальное окно промпта
  $('btnClosePrompt').onclick = pmClose;
  $('btnMaximizePrompt').onclick = pmToggleMaximize;
  $('btnPromptCloseFooter').onclick = pmClose;
  $('promptModal').onclick = (e) => { if (e.target === $('promptModal')) pmClose(); };
  $('btnPromptSave').onclick = pmSave;
  $('pmContent').addEventListener('input', pmPreview);
  document.querySelectorAll('.pm-toolbar button').forEach((b) => {
    b.onclick = () => {
      const t = $('pmContent');
      const before = (b.dataset.before || '').replace(/&#10;/g, '\n');
      const after = (b.dataset.after || '').replace(/&#10;/g, '\n');
      const s = t.selectionStart, e = t.selectionEnd;
      const text = t.value.slice(s, e) || '';
      t.value = t.value.slice(0, s) + before + text + after + t.value.slice(e);
      t.selectionStart = s + before.length; t.selectionEnd = s + before.length + text.length;
      t.focus(); pmPreview();
    };
  });

  // Модалка справки
  $('btnHelp').onclick = () => $('helpModal').classList.remove('hidden');
  $('btnCloseHelp').onclick = () => $('helpModal').classList.add('hidden');
  $('helpModal').onclick = (e) => { if (e.target === $('helpModal')) $('helpModal').classList.add('hidden'); };
});

/* старт */
window.addEventListener('DOMContentLoaded', () => {
  updateMergePromptCard();
});
refreshProviders();
refreshHealth();
refreshCredentials();
refreshLogs();
refreshMergePrompts();
refreshPromptFiles();
setInterval(refreshLogs, 3000);
setInterval(refreshHealth, 5000);