# LocalAssitent

Локальный AI-агент для автоматизации веб-интерфейса DeepSeek Chat через Selenium + Edge CDP.

## Возможности

- **Code scenario** — итеративная генерация и выполнение Python-кода
- **Text scenario** — пакетный Q&A (вопрос-ответ)
- **Merge scenario** — сведение файлов проекта в один TXT для передачи внешнему ИИ
- **Pipeline** — автоматическая отправка кода проекта в DeepSeek и сохранение ответа
- Авторизация через браузер (автоматическая или ручная)
- Прикрепление файлов через `input[type=file]` и `Ctrl+V`

## Структура проекта

```
LocalAssitent/
├── main.py                  # Точка входа (сценарии code/text/merge)
├── pipeline.py              # Pipeline: сбор → DeepSeek → MD
├── config.py                # Конфигурация + CLI
├── scenarios.py             # Логика сценариев
├── extractors.py            # Парсер кода из ответов
├── rules.py                 # Синтаксис + выполнение
├── logger.py                # Логгер
│
├── agent/                   # Браузерный агент
│   ├── client.py            # SeleniumDeepSeekClient
│   ├── DeepSeekClient.py    # Обёртка-клиент
│   ├── auth.py              # Авторизация
│   ├── clipboard.py         # Буфер обмена
│   ├── browser/manager.py   # Управление Edge
│   └── handlers/            # Отправка, чтение, аттач файлов
│
├── detection/               # Поиск DOM-элементов
│   ├── element_finder.py
│   ├── selectors.py
│   ├── response_ready.py
│   └── action_panel.py
│
├── tools/                   # Утилиты
│   ├── registry.py / cli.py / __main__.py   # Реестр + CLI `python -m tools`
│   ├── safety.py / read_file.py / write_file.py
│   ├── edit_file.py / append_file.py / delete_file.py
│   ├── search.py / execute.py / list_dir.py / merge_docs.py
│
├── scripts/                 # Утилитарные скрипты
│   ├── feedback.py          # Обратная связь от DeepSeek
│   ├── run_analysis.py
│   ├── wait_and_read.py
│   ├── read_response.py
│   ├── qwen_task.py         # Задача для chat.qwen.ai через Edge CDP
│   ├── apply_cloud.py       # Применение ответа облачного ИИ (docs/AI_TASK_*.md)
│   └── test_send.py
│
├── tests/                   # Тесты
├── docs/                    # Документация + архивы AI_TASK (спеки и ответы ИИ)
└── prompts/                 # Промпты для ИИ
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
```

### 3. Запуск

```bash
# Итеративная генерация кода
python main.py --scenario code --prompt "Напиши скрипт для бэкапа"

# Пакетный Q&A
python main.py --scenario text --input questions.txt --output answers.md

# Сведение документов для внешнего ИИ
python main.py --scenario merge --merge-dir . --ext .cs .py

# Pipeline: анализ проекта через DeepSeek
python pipeline.py
python pipeline.py --merged pipeline_output/project_context.txt
```

## Merge Docs

Инструмент для сведения файлов проекта в один TXT — удобно для загрузки в внешний ИИ через браузер.

```bash
# Прямой запуск
python tools/merge_docs.py . --ext .cs .py --output context.txt

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

Pipeline автоматически собирает файлы проекта, отправляет их в DeepSeek и сохраняет ответ в `pipeline_output/deepseek_analysis.md`.

```bash
# Стандартный pipeline (собирает файлы из PIPELINE_FILES)
python pipeline.py

# Из merged-файла
python pipeline.py --merged pipeline_output/project_context.txt

# Свои credentials
python pipeline.py --email user@mail.com --password pass
```

## Зависимости

- Python 3.10+
- selenium >= 4.0.0
- pywin32 >= 300
- python-dotenv >= 1.0.0
- pytest >= 7.0.0

## Лицензия

MIT
