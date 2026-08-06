# Mission: LocalAssitent — UI-редизайн, детекция ответа, SQLite-промпты

## Project Context
- Репозиторий: e:\ПлагиныРевит\LocalAssitent (ветка v1, origin: github.com/strahser/LocalAssitent)
- Полный контекст: .opencode/context.md
- Полная проверка: `python -m pytest tests -q` (213 passed)

## M6: Промпты из хардкода → БД | status: completed
### T6.1: Выпилить хардкод промптов из webui/app.py | agent:Worker | status: completed
- [x] S6.1.1: merge-промпт («общий файл проектов») добавлен в сидинг prompts_db.py (stage='first', name='default merge') + маппинг в prompt_config | size:M | verified
- [x] S6.1.2: _pipeline_message(): убран фолбэк на SCENARIO_CONFIGS, промпт берётся из БД (get_prompt_for stage→both) | size:M | verified
- [x] S6.1.3: run_pipeline(): merge и improve берут промпты из БД (get_prompt_for), убрано чтение prompts/improve_analyze.txt | size:M | verified
- [x] S6.1.4: SCENARIO_CONFIGS удалён из импорта app.py | size:S | verified
- [x] S6.1.5: Тесты test_prompts_db.py обновлены под merge-сидинг; pytest tests -q = 213 passed | size:M | verified

## M1: Запуск Open WebUI | status: completed
### T1.1: Запуск Open WebUI на порту 3000 | agent:Worker | status: completed
- [x] S1.1.1: open-webui serve --host 127.0.0.1 --port 3000 (Start-Process detached) | size:S | verified
- [x] S1.1.2: Проверить http://127.0.0.1:3000/ отвечает 200 | size:S | verified: HTTP 200

## M2: Оптимизация детекции готовности ответа | status: completed
### T2.1: Стратегии response_ready.py + селекторы | agent:Worker | status: completed
- [x] S2.1.1: Стратегии используют config.selectors вместо глобального SELECTORS (ResponseReadyStrategyFactory + ResponseReader.wait_ready) | size:M | verified
- [x] S2.1.2: Добавить HTML/текст-стабилизацию (innerHTML length) в TextStabilizationStrategy | size:M | verified
- [x] S2.1.3: Новая CopyButtonCountStrategy: счётчик кнопок копирования стабилен >0 → готово (deepseek: div.ds-button__background, span.code-info-button-text) | size:M | verified
- [x] S2.1.4: CombinedStrategy: быстрый возврат при непустом ответе + кнопках; MIN_CONTENT_LENGTH снижен | size:M | verified
- [x] S2.1.5: detection/selectors.py: copy_button += div.ds-button__background; detection/qwen_selectors.py: добавить copy_button и copy_message_button (Qwen) | size:S | verified
- [x] S2.1.6: Тесты tests/test_response_ready_optimized.py (fake-элементы, offline) | size:M | verified
- [x] S2.1.7: pytest tests -q зелёный | size:S | verified: 213 passed

## M3: SQLite + CRUD промптов | status: completed
### T3.1: Бэкенд webui/prompts_db.py + API | agent:Worker | status: completed
- [x] S3.1.1: webui/prompts_db.py: sqlite3, нормализация (pipelines / prompts / prompt_config FK), сидинг из SCENARIO_CONFIGS | size:L | verified
- [x] S3.1.2: CRUD-функции (get_all/create/update/delete) + get_prompt_for(pipeline, stage) | size:M | verified
- [x] S3.1.3: webui/app.py: GET/POST /api/prompts, PUT/DELETE /api/prompts/{id}, GET/POST /api/prompt-config, GET /api/credentials | size:M | verified
- [x] S3.1.4: Интеграция: выбор first/subsequent промпта в send_message/run_pipeline (счётчик сообщений сессии, сброс при new_chat) | size:M | verified
- [x] S3.1.5: Тесты tests/test_prompts_db.py + tests/test_prompts_api.py (tmp db, offline) | size:M | verified
- [x] S3.1.6: .gitignore += *.db | size:S | verified

## M4: Редизайн UI | status: completed
### T4.1: webui/static (index.html, style.css, app.js) | agent:Worker | status: completed
- [x] S4.1.1: Вертикальное меню (Чат/Пайплайны/Сбор файлов/Промпты/Журнал) + горизонтальный хедер | size:L | verified
- [x] S4.1.2: Чат: пары вопрос-ответ рядом, индикатор «✅ Получено HH:MM:SS» / «⏳...», busy | size:L | verified
- [x] S4.1.3: Секция Промпты: CRUD-таблица + форма (pipeline, stage, name, content, активен, назначить first/subsequent) | size:L | verified
- [x] S4.1.4: Префилл кредов из /api/credentials + подсказка «пусто = из .env» | size:S | verified
- [x] S4.1.5: Сохранить текст «Подключиться к браузеру» в HTML (тест test_webui ищет «подключиться») | size:S | verified

## M5: Верификация | status: completed
### T5.1: Полный прогон Reviewer | agent:Reviewer | status: completed
- [x] S5.1.1: pytest tests -q (все passed) | size:M | verified: 213 passed in 30.91s
- [x] S5.1.2: py_compile изменённых файлов | size:S | verified: COMPILE_ALL_OK
- [x] S5.1.3: Порты: 8080 (LocalAssitent UI), 3000 (Open WebUI) живы | size:S | verified: оба HTTP 200
