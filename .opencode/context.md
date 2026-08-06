# Project Context

## Environment
- Python 3.13; pytest. Repo: e:\ПлагиныРевит\LocalAssitent, ветка v1
- Suite: `python -m pytest tests -q` → **216 passed** (offline; test_selenium_live.py НЕ входит в pytest, запускается отдельно `python tests/test_selenium_live.py`)

## Пифолы
1. НЕ редактировать .py через PowerShell (mojibake). Только write/edit UTF-8.
2. Порты: 8080 = LocalAssitent UI (запущен PID 31356), 9222 = Edge debug (открыт Qwen chat.qwen.ai, CDP работает), 3000 = Open WebUI.
3. Контекст КРИТИЧЕН — компакции каждые 2-3 шага, минимум вывода.
4. Сервер НЕ hot-reload — после правок перезапуск.
5. БД: data/localassistant.db — ПЕРЕСОЗДАНА новым сидингом (5 промптов): qa/first/1, code/first/2, merge/first/3, improve/first/4(analyze), improve/subsequent/5(review). CONFIG: qa{1,1}, code{2,2}, merge{3,3}, improve{4,5}.
6. **Qwen UI (2026-08-06)**: кнопка «Копировать» = `div[role=button][aria-label=Копировать]` в `div.response-message-footer`, СКРЫТА классом `response-message-footer-none` до hover → в `extract_answer` сначала `_reveal_response_footer()` (hover + JS-снятие класса). Блок ответа = `div.qwen-chat-message-assistant` (НЕ `.chat.assistant`/`article` — пустой контейнер). Буфер с `\r\n`/дублями пустых строк → `normalize_answer_text()`. Полная документация: README «Известные проблемы Qwen UI».
7. Скрипт чтения всех ответов открытого чата: `python scripts/qwen_read_all_answers.py` → `pipeline_output/qwen_chat_all_answers.md` (методы `QwenClient.extract_all_answers/save_all_answers`).

## ЗАВЕРШЕНО (todo.md 100% [x], pytest 213 passed):
- M1-M6 все закрыты (Open WebUI, детекция, SQLite-промпты, UI-редизайн, верификация, промпты из хардкода→БД)

## ТЕКУЩАЯ ЗАДАЧА (жалоба: «не вижу промптов в UI» + «сделай тесты через Selenium» + «расширь справку») — Selenium-ЧАСТЬ ГОТОВА:
- Старый сервер убит, БД пересоздана (см. выше), сервер перезапущен (8080 OK).
- Создан tests/test_selenium_live.py: подключается к открытому Edge 9222 (Qwen), берёт промпты из БД (get_prompt_for first/both), отправляет через клиент SeleniumQwenClient, ждёт ответ через CombinedStrategy, отчёт. Файлы не отправляет. Запуск: `python tests/test_selenium_live.py [pipes...]` (по умолчанию все 4). Использует SeleniumConfig(debug_port=9222, response_strategy="combined", selectors=QWEN_SELECTORS, stable_duration=1.5).
- **НАЙДЕН И ИСПРАВЛЕН БАГ**: Qwen-селектор assistant_messages находил пустой контейнер (chat+assistant). В detection/qwen_selectors.py ПЕРВЫМ добавлен `//div[contains(@class, 'qwen-chat-message-assistant')]` — реальный элемент с текстом.
- **SELENIUM-TEСТЫ ПРОЙДЕНЫ (все 4 пайплайна)**:
  - qa: OK, 135 симв., ~101с
  - code: OK, 162 симв., ~101с
  - merge: OK, 74 симв., ~101с
  - improve: OK, 94 симв., ~101с
  - Детекция: «стабилизация текста и HTML» (M2 работает); ранее также видно «кнопки копирования стабильны». Кнопка копирования сообщения у Qwen не находится (warning) → фолбэк на .text работает.
  - Примечание: ответ ~100с — это время думания Qwen, не задержка детекции.

## ОСТАЛОСЬ (2-я часть задачи пользователя):
1. **Расширить справку UI** (index.html → #helpModal): подробно объяснить:
   - Как использовать вкладку «🧠 Промпты»: форма «Новый промпт» (pipeline: qa/code/merge/improve; stage: both/first/subsequent; name; content; кнопка Создать), таблица со списком, кнопки действий: ✏️ редактировать, 🗑️ удалить, 1️⃣ назначить как промпт ПЕРВОГО сообщения (first), 2️⃣ назначить для ПОСЛЕДУЮЩИХ (subsequent).
   - Что такое маппинг: prompt_config связывает пайплайн ↔ промпты first/subsequent; при отправке сообщения из Чат/Пайплайны: первое сообщение сессии → промпт first, последующие → subsequent; если не назначен → фолбэк на stage='both'; если нет → «Ответь на вопрос.»
   - Новый чат (чекбокс) сбрасывает счётчик → следующее сообщение снова first.
   - Вкладка «⚙️ Пайплайны»: выбор пайплайна (qa/code/merge/improve), директория для merge/improve (пусто = проект), «Новый чат», «Выполнить» — промпт подставляется из БД автоматически по маппингу; merge = «общий файл проектов» (собирает контекст через collect_context + промпт из БД).
   - Вкладка «💬 Чат»: простой Q&A, промпт qa из БД.
   - Креды: пусто = из .env (префилл автоматический).
2. Обновить index.html (helpModal + возможно добавить подсказки в секцию Промпты).
3. Проверить: сервер 8080 отдаёт новый HTML (перезапуск не нужен — статика читается с диска).
4. Финальный ответ пользователю: Selenium-тесты (qa/code/merge/improve OK, найденный баг селектора Qwen исправлен), справка расширена, как пользоваться маппингом.

## Pending (порядок)
1. Расширить helpModal в webui/static/index.html (текст про маппинг/промпты/пайплайны)
2. Проверить 8080 (GET / содержит новую справку)
3. Ответить пользователю с итогами
