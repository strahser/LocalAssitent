# LocalAssitent

Локальный AI-агент для автоматизации веб-интерфейсов облачных чатов (DeepSeek Chat / Qwen Chat) через Selenium + Edge CDP.

## Возможности

- **Code scenario** — итеративная генерация и выполнение Python-кода
- **Text scenario** — пакетный Q&A (вопрос-ответ)
- **Merge scenario** — сведение файлов проекта в один TXT для передачи внешнему ИИ
- **Improve scenario** — непрерывный цикл улучшения кода: анализ → улучшение → проверка → переоценка (до отмены)
- **Pipeline** — автоматическая отправка кода проекта в DeepSeek/Qwen и сохранение ответа
- Мультипровайдерность: DeepSeek (chat.deepseek.com) и Qwen (chat.qwen.ai) через `--provider`
- Выбор модели Qwen из списка (`--model`, по умолчанию Qwen3.8-Max-Preview)
- Авторизация через браузер (автоматическая или ручная)
- Прикрепление файлов через `input[type=file]` и `Ctrl+V`

## Структура проекта

```
LocalAssitent/
├── main.py                  # Точка входа (сценарии code/text/merge/improve)
├── pipeline.py              # Pipeline: сбор → DeepSeek/Qwen → MD
├── config.py                # Конфигурация + CLI (провайдеры, модели)
├── scenarios.py             # Логика сценариев (в т.ч. ImproveScenario)
├── extractors.py            # Парсер кода из ответов
├── rules.py                 # Синтаксис + выполнение
├── logger.py                # Логгер
├── launch.py                # Быстрый запуск pipeline (dotenv + run_pipeline)
├── merge_config.json        # Пример JSON-конфига для merge_docs
│
├── agent/                   # Браузерный агент (Selenium DeepSeek/Qwen)
│   ├── client.py            # SeleniumChatClient (DeepSeek/Qwen) + select_model()
│   ├── deepseek_client.py   # Обёртка-клиент DeepSeek
│   ├── QwenClient.py        # Обёртка-клиент Qwen
│   ├── qwen_auth.py         # Авторизация Qwen (chat.qwen.ai)
│   ├── auth.py              # Авторизация
│   ├── clipboard.py         # Буфер обмена
│   ├── browser/manager.py   # Управление Edge
│   └── handlers/            # Отправка, чтение, аттач файлов
│
├── agents/                  # Плагинные агенты (registry + cli + __main__)
│   ├── base.py / registry.py / cli.py / __main__.py
│   └── web_search / page_parser / local_data / qa / browser / merge
│
├── detection/               # Поиск DOM-элементов
│   ├── element_finder.py
│   ├── selectors.py
│   ├── qwen_selectors.py    # Селекторы Qwen Chat UI
│   ├── response_ready.py
│   └── action_panel.py
│
├── tools/                   # Утилиты (registry + CLI `python -m tools`)
│   ├── registry.py / cli.py / __main__.py
│   ├── merge_docs.py        # Сведение документов (1 или несколько директорий)
│   ├── send_to_cloud.py     # Отправка файла/текста в облачный чат
│   ├── list_models.py       # Список провайдеров и моделей
│   ├── safety.py / read_file.py / write_file.py
│   ├── edit_file.py / append_file.py / delete_file.py
│   ├── search.py / execute.py / list_dir.py / merge_docs.py
│
├── qwen/                    # chat.qwen.ai автоматизация
│   ├── client.py / html_monitor.py / dnd_uploader.py / selectors.py
│
├── scripts/                 # Утилитарные скрипты
│   ├── feedback.py          # Обратная связь от DeepSeek/Qwen
│   ├── run_analysis.py
│   ├── wait_and_read.py
│   ├── read_response.py
│   ├── qwen_task.py         # Задача для chat.qwen.ai через Edge CDP
│   ├── qwen_read_all_answers.py  # Копирование ВСЕХ ответов открытого чата Qwen в MD
│   ├── qwen_send_prompt.py  # Отправка промпта в chat.qwen.ai (оверлей, nativeSetter)
│   ├── qwen_wait_answer.py  # Ожидание стабилизации ответа / маркера конца
│   ├── apply_cloud.py       # Применение ответа облачного ИИ (docs/AI_TASK_*.md)
│   └── test_send.py
│
├── .opencode/               # Контекст и скиллы агента
│   ├── context.md / status.md / todo.md / work-log.md
│   └── skills/heatloss-browser-bridge/SKILL.md  # Браузерный мост Qwen (переиспользуемый)
│
├── tests/                   # Тесты (python -m pytest tests -q)
├── docs/                    # Документация + архивы AI_TASK (спеки и ответы ИИ)
└── prompts/                 # Промпты для ИИ
    ├── analyze_project.txt
    ├── improve_analyze.txt  # Промпт 1-й итерации improve-цикла
    └── improve_review.txt   # Промпт повторных итераций
```

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
```

```
DEEPSEEK_EMAIL=your_email@gmail.com
DEEPSEEK_PASSWORD=your_password

# Провайдер Qwen (chat.qwen.ai) — используется для сценария improve и --provider qwen
QWEN_EMAIL=your_qwen_email@gmail.com
QWEN_PASSWORD=your_qwen_password

# Провайдер по умолчанию: deepseek | qwen
PROVIDER=deepseek

# Модель по умолчанию для Qwen
MODEL=Qwen3.8-Max-Preview
```

### 3. Запуск

```bash
# Итеративная генерация кода
python main.py --scenario code --prompt "Напиши скрипт для бэкапа"

# Пакетный Q&A
python main.py --scenario text --input questions.txt --output answers.md

# Сведение документов для внешнего ИИ
python main.py --scenario merge --merge-dir . --ext .cs .py

# Непрерывный цикл улучшения кода (Qwen)
python main.py --scenario improve --provider qwen --model Qwen3.8-Max-Preview

# Pipeline: анализ проекта через DeepSeek
python pipeline.py
python pipeline.py --merged pipeline_output/project_context.txt

# Pipeline через Qwen
python pipeline.py --provider qwen --model Qwen3.8-Max-Preview
```

### Выбор провайдера и модели

Агент поддерживает два облачных чата:

| Провайдер | `--provider` | Чат |
|-----------|--------------|-----|
| DeepSeek  | `deepseek`   | https://chat.deepseek.com |
| Qwen      | `qwen`       | https://chat.qwen.ai |

- `--provider` — выбор провайдера (по умолчанию `deepseek`, для improve — `qwen`).
- `--model` — выбор модели (для Qwen). Список доступных моделей:
  ```bash
  python -m tools.list_models
  ```
  Модель по умолчанию: **Qwen3.8-Max-Preview**.

### 4. Веб-интерфейс (Web UI)

Браузерный интерфейс на FastAPI (каталог `webui/`): подключение к браузеру (Edge debug-mode),
выбор клиента (DeepSeek/Qwen + модель), пайплайны и журнал — без работы с консолью.

```bash
# Запуск: uvicorn 127.0.0.1:8000 + автоматическое открытие браузера
py run_ui.py

# Без открытия браузера / на другом порту
py run_ui.py --no-browser
py run_ui.py --port 8123 --host 0.0.0.0
```

Возможности интерфейса:

- **Подключиться к браузеру** — запуск/подключение Edge (debug, порт 9222) и логин в чат;
  кнопка **Отключить** закрывает клиент и браузер.
- **Клиент** — DeepSeek / Qwen (для Qwen выбирается модель из списка).
- **Пайплайны**:
  - *Чат: вопрос — ответ (Q&A)* — вопрос → структурированный ответ.
  - *Чат: вопрос — код* — задача → решение + код.
  - *Проект → контекст → облако* — `collect_context` директории → анализ в облачном чате
    (результат: `pipeline_output/ui_merged_context.txt`).
  - *Improve: анализ проекта* — один проход анализа через `prompts/improve_analyze.txt`.
- **Журнал** — последние записи `ui.log` (правый блок, обновляется автоматически).

Учётные данные берутся из переменных окружения `DEEPSEEK_EMAIL/PASSWORD` или
`QWEN_EMAIL/PASSWORD` (см. раздел «Настройка переменных окружения»).

API: `GET /api/health`, `GET /api/providers`, `POST /api/connect|disconnect|chat|run`,
`GET /api/logs?limit=N`.

## Merge Docs

Инструмент для сведения файлов проекта в один TXT — удобно для загрузки в внешний ИИ через браузер.

```bash
# Прямой запуск
python tools/merge_docs.py . --ext .cs .py --output context.txt

# Несколько директорий в один файл (C# / мульти-проект)
python tools/merge_docs.py --dirs C:\ProjA C:\ProjB --ext .cs --output combined.txt

# С промптом для ИИ
python tools/merge_docs.py . --ext .cs --prompt "Проанализируй этот код"

# С файлом промпта
python tools/merge_docs.py . --ext .py --prompt-file prompts/analyze_project.txt

# С JSON-конфигом
python tools/merge_docs.py . --config merge_config.json
```

### Опции

| Опция | Описание |
|-------|----------|
| `--dirs` | Несколько корневых директорий (файлы объединяются в один TXT, с заголовками по каждой директории) |
| `--ext` | Расширения файлов (по умолчанию: .cs .py .xaml .csproj и др.) |
| `--output`, `-o` | Выходной файл |
| `--max-size` | Макс. размер файла в байтах |
| `--include` | Glob-паттерны для включения |
| `--exclude` | Glob-паттерны для исключения |
| `--exclude-dir` | Директории для исключения |
| `--prompt` | Текст промпта для ИИ |
| `--prompt-file` | Файл с промптом |
| `--config` | JSON-конфигурационный файл |
| `--no-summary` | Без сводной таблицы |

## Tools CLI

Пакет `tools/` имеет единый CLI через реестр (`tools/registry.py`):

```bash
# Список инструментов
python -m tools --list

# Чтение файла (позиционные аргументы маппятся по сигнатуре)
python -m tools read_file tools/safety.py

# Поиск с флагами (--name value / --name=value / --flag; дефисы → подчёркивания)
python -m tools grep_search TODO --include "*.py" --max-results 10

# Точечное редактирование / дозапись / удаление (через safe_join из tools/safety.py)
python -m tools edit_file --path src/x.py --old-text "a" --new-text "b"
python -m tools append_file --path notes.md --content "текст"
python -m tools delete_file --path tmp.txt
```

Все файловые операции проходят через `tools/safety.py` (`safe_join` / `is_safe_path`), запрещающий выход за пределы корня проекта.

## Collect Context (сбор контекста для облачного ИИ)

Скрипт для передачи содержимого файлов из выбранных директорий облачному ИИ:
сводит код проекта в один TXT **с «общим заданием» в начале** и **без временных файлов**.

```bash
# Один проект (C#, автоопределение типа)
py tools/collect_context.py d:\Projects\HeatLossRevit2 --output context.txt

# Несколько директорий
py tools/collect_context.py --dirs D:\ProjA D:\ProjB --project-type cs --output cs_context.txt

# Python-проект
py tools/collect_context.py . --project-type py
```

### Что делает

- **Общее задание в начале** — перед кодом вставляется шаблон `prompts/general_task.txt`
  (скопирован с `revit-skills/.opencode/skills/cloud-ai-bridge`): контекст (C#/.NET и/или Python),
  цель, строгий формат ответа (решения таблицей, скрипты, риски), **контракт полноты**
  (`### SUMMARY` + `// END OF FILE`), ограничения (не переписывать файлы целиком, кодировка ASCII).
- **Автоопределение типа проекта** (`auto`): по наличию `.cs/.csproj/.sln` → `cs`,
  `.py/requirements.txt/pyproject.toml` → `py`, оба → `mixed`.
- **Фильтр временных файлов** — исключает содержимое по директориям и по именам:
  `bin/ obj/ .git/ .gigacode/ .idea/ .vs/ __pycache__/ node_modules/ venv/ build/ dist/
  packages/ TestResults/ log/ logs/ publish/ .opencode/`, а также `*.tmp *.log *.user *.suo
  *.bak *.orig *.rej *.nupkg *.cache *.pyc *.plan.md *AssemblyAttributes.cs *.g.cs *.g.i.cs ...`.
- **Прозрачный отчёт** — в конце выводится, сколько файлов исключено по имени (временные)
  и по размеру (файлы больше `--max-size`, по умолчанию 100 KB — напр. большие
  Revit-репозитории данных, которые облачному ИИ обычно не нужны).

### Опции

| Опция | Описание |
|-------|----------|
| `--dirs` | Несколько корневых директорий |
| `--project-type` | `auto` (по умолчанию) \| `cs` \| `py` |
| `--ext` | Явные расширения (переопределяет автодетект) |
| `--output` / `-o` | Выходной файл (по умолчанию `cloud_context.txt`) |
| `--max-size` | Макс. размер файла в байтах (по умолчанию 100000) |
| `--include` / `--exclude` | Glob-паттерны включения/исключения |
| `--exclude-dir` | Дополнительные директории для исключения |
| `--no-task` | Не вставлять «общее задание» в начало |
| `--task` | Свой файл «общего задания» |
| `--no-summary` | Без сводной таблицы |
| `--config` | JSON-конфиг (см. `tools/collect_context_config.json`) |
| `--encoding` | Кодировка (по умолчанию `utf-8`) |

Проверено на `d:\Projects\HeatLossRevit2`: 801 исходный `.cs` файл из 802 собрано
(один большой `ClimateDataRepository.cs` исключён по `--max-size`, как не нужный
облачному ИИ), временные файлы `bin/ obj/ .gigacode/ .idea/ *.plan.md`
в контекст не попадают.

## Improve Scenario (цикл улучшения кода)

Непрерывный цикл улучшения кода с внешним ИИ — работает до отмены пользователем:

```
анализ кода → рекомендации/улучшения (tool-блоки) → применение →
проверка (py_compile + pytest) → переоценка → повтор
```

```bash
# Запуск с Qwen (модель по умолчанию Qwen3.8-Max-Preview)
python main.py --scenario improve --provider qwen --model Qwen3.8-Max-Preview

# Ограничить число итераций
python main.py --scenario improve --max-iterations 10
```

- На каждой итерации агент собирает код проекта (merge_docs), отправляет его в облачный чат и применяет изменения через tool-блоки (`tool:read`, `tool:write`, `tool:exec`, `tool:grep`, `tool:glob`, `tool:ls`, `tool:merge`, `tool:send_to_cloud`, `tool:list_models`).
- После применения изменений запускается проверка: `py_compile` + `pytest`, результат возвращается ИИ для переоценки.
- Остановка: ответ ИИ содержит `NO_IMPROVEMENTS` / `TASK_COMPLETE`, достигнут лимит `--max-iterations` (по умолчанию `0` = бесконечно), либо `Ctrl+C`.
- Промпты цикла: `prompts/improve_analyze.txt` (первая итерация) и `prompts/improve_review.txt` (повторные итерации).
- Результаты каждой итерации сохраняются в `pipeline_output/improve_iteration_NNN.md`.

## Tools

Утилиты доступны как отдельные CLI-команды и как инструменты AI-сценариев (блоки ```tool:<имя>```).

```bash
# Список провайдеров и моделей облачных чатов
python -m tools.list_models

# Отправка файла/merged-текста выбранному провайдеру и модели
python -m tools.send_to_cloud --provider qwen --model Qwen3.8-Max-Preview --file merged.txt
python -m tools.send_to_cloud --text "анализируй: ..." --provider deepseek
python -m tools.send_to_cloud merged.txt --provider qwen --model Qwen3.8-Max-Preview --output feedback.md

# Сведение документов (1 или несколько директорий)
python tools/merge_docs.py --dirs . D:\Other\Proj --ext .cs --output combined.txt
```

| Инструмент | CLI | Описание |
|------------|-----|----------|
| `merge_docs` | `python tools/merge_docs.py ...` | Сведение файлов из одной или нескольких директорий в один TXT |
| `collect_context` | `python tools/collect_context.py ...` | Контекст для облачного ИИ: файлы C#/Python + «общее задание» в начале + фильтр временных файлов |
| `send_to_cloud` | `python -m tools.send_to_cloud ...` | Отправка файла/текста в облачный чат (DeepSeek/Qwen), сохранение ответа в `pipeline_output/` |
| `list_models` | `python -m tools.list_models` | Список доступных провайдеров и моделей |

## Тесты

```bash
# Все тесты безопасности
python -m pytest tests/test_safety.py -v

# Тесты merge_docs
python tests/test_merge_docs.py

# Тесты селекторов
python tests/test_selectors.py
```

## Pipeline

Pipeline автоматически собирает файлы проекта, отправляет их в облачный чат (DeepSeek/Qwen) и сохраняет ответ.

```bash
# Стандартный pipeline (DeepSeek, собирает файлы из PIPELINE_FILES)
python pipeline.py

# Через Qwen (ответ в pipeline_output/qwen_analysis.md)
python pipeline.py --provider qwen --model Qwen3.8-Max-Preview

# Из merged-файла
python pipeline.py --merged pipeline_output/project_context.txt

# Свои credentials
python pipeline.py --email user@mail.com --password pass
```

## Известные проблемы Qwen UI (chat.qwen.ai)

**ВАЖНО для агентов и разработчиков:** UI Qwen часто меняется. Наблюдаемый DOM (2026-08-06):

1. **Кнопка «Копировать» скрыта до наведения мыши.**
   Футер ответа имеет класс `response-message-footer-none` (CSS `display: none`),
   кнопка появляется только при hover на сообщение.
   - Реальный элемент: `div[role='button'][aria-label='Копировать']` внутри `div.response-message-footer`.
   - Голый `button.copy-response-button` — это **не** кликабельный контрол (пустой, скрыт).
   - Решение: hover по блоку `div.qwen-chat-message-assistant` + снять класс скрытия JS:
     ```js
     document.querySelectorAll('div.response-message-footer')
       .forEach(el => el.classList.remove('response-message-footer-none'));
     ```
   Реализовано в `QwenClient._reveal_response_footer()` (qwen/client.py).

2. **Блок ответа ассистента** — `div.qwen-chat-message-assistant`
   (НЕ `.chat.assistant` и НЕ `article` — такие селекторы находят пустой контейнер).
   Первым селектором `assistant_messages` в `detection/qwen_selectors.py` должен быть
   `//div[contains(@class, 'qwen-chat-message-assistant')]`.

3. **Текст из буфера обмена приходит с `\r\n` и дублями пустых строк.**
   В markdown это превращается в «растянутый» текст с лишними пустыми строками.
   Всегда прогоняйте текст через `QwenClient.normalize_answer_text()`
   (CRLF→LF, удаление одиночных `\r`, схлопывание дублей пустых строк).

4. **«Завершено размышление»** — это плашка в начале блока ассистента, часть `.text`.
   При копировании через кнопку она в текст не попадает (копируется только сам ответ).

### Как скопировать ВСЕ ответы открытого чата

Если чат уже открыт в Edge (debug, порт 9222) — запустите:

```bash
python scripts/qwen_read_all_answers.py
# опции: --port 9222, --output pipeline_output/qwen_chat_all_answers.md
```

Скрипт использует `QwenClient.extract_all_answers()`: для каждого ответа ассистента
наводится мышь, снимается класс скрытия футера, кликается кнопка «Копировать»,
читается буфер обмена, текст нормализуется. Все ответы сохраняются одним файлом
markdown (`## Ответ N`). Утилитарный скрипт `qwen/client.py` также имеет
`save_all_answers(answers, output_file, chat_id)`.

### Готовые скрипты Агента-3 (браузерный мост)

Все три — в `scripts\`, переиспользуй (не создавай заново):

| Скрипт | Что делает | Команда |
|---|---|---|
| `qwen_send_prompt.py` | Отправка промпта в текущую вкладку chat.qwen.ai: убирает блокирующий оверлей `.page-loading` (z=49), вставка nativeSetter, отправка, проверка очистки поля | `python scripts\qwen_send_prompt.py --file <файл задания>` (формат конвейера: строка 1 — путь ответа, строки 4+ — промпт) |
| `qwen_wait_answer.py` | Ожидание стабилизации ответа (2 замера), распознавание «Сетевая ошибка» (код 3 → ретрай), опционально маркер конца | `python scripts\qwen_wait_answer.py --timeout 600 --marker КОНЕЦ_ТЗ` |
| `qwen_read_all_answers.py` | Копирование ВСЕХ ответов через кнопки «Копировать» в один markdown | `python scripts\qwen_read_all_answers.py` |
| `qwen_download_images.py` | Скачивание ВСЕХ изображений открытого чата в папку (имена unix-timestamp как у Qwen + `manifest_<ts>.json`; куки сессии, blob:/data: поддерживаются, браузер остаётся открыт) | `python scripts\qwen_download_images.py --output d:\Projects\Demiurges\assets\new` |

**Скилл браузерного моста** (`heatloss-browser-bridge`) — в `.opencode\skills\heatloss-browser-bridge\SKILL.md`:
роль «передача текста между проектом и Qwen», поток работы, обработка «Сетевой ошибки» (ретраи),
блокирующий оверлей. Копируется на новые проекты (в HeatLossRevit2 это Агент-3 конвейера).

**Блокирующий оверлей `.page-loading`** (найдено 2026-08-06): после загрузки страницы он
висит над полем ввода (z-index 49, pointer-events: auto) и ломает React-ввод — текст вставляется,
но кнопка send disabled и поле не очищается. Решение в `qwen_send_prompt.py`:
`el.style.pointerEvents='none'; el.style.display='none'`, затем nativeSetter + input/change.

---

## Обратная связь (feedback)

Скрипт отправки файлов проекта в облачный чат для получения обратной связи:

```bash
# DeepSeek, текущий чат
python scripts/feedback.py

# Новый чат
python scripts/feedback.py --new-chat

# Через Qwen (ответ в pipeline_output/qwen_feedback.md)
python scripts/feedback.py --provider qwen --model Qwen3.8-Max-Preview
```

## Зависимости

- Python 3.10+
- selenium >= 4.0.0
- pywin32 >= 300
- python-dotenv >= 1.0.0
- pytest >= 7.0.0

## Лицензия

MIT
