# Как скачивать картинки из Qwen Chat (chat.qwen.ai)

Два скрипта в `scripts/`, оба работают через Edge в debug-режиме (CDP, порт 9222)
и браузер после работы **не закрывают** (флаг `--close` — закрыть).

## 0. Поднять мост

```bash
# Edge с отдельным профилем + нужный чат:
msedge --user-data-dir=%LOCALAPPDATA%\QwenDebugProfile --remote-debugging-port=9222 https://chat.qwen.ai/c/<chat_id>
# проверка:
curl http://127.0.0.1:9222/json/list
```

Зайти в Qwen в этом окне (залогиниться). Скрипты сами переключаются
на вкладку с `chat.qwen.ai`, даже если активной была другая.

## 0b. Отправить запрос в чат — `qwen_send.py`

Вставляет текст из файла в поле ввода (нативный setter + `input`-ивент,
React подхватывает) и эмулирует Enter. Проверяет, что сообщение ушло
(поле очистилось, текст виден в чате). Режимы переключать не нужно.

```bash
python scripts\qwen_send.py --text-file d:\Projects\Demiurges\QWEN_ORDER_battlefield.txt
python scripts\qwen_send.py --text-file prompt.txt --no-verify   # без проверки
```

Абсолютные ссылки на готовые запросы лежат рядом с игрой
(`d:\Projects\Demiurges\QWEN_ORDER_*.txt`). После генерации картинок —
скачать их скриптами из п. 1–2.

## 1. Быстро: превью из `<img>` — `qwen_download_images.py`

Тянет прямые `src` картинок из ответов ассистента с куками сессии.
Поддерживает `http(s)`, `blob:`, `data:`. Аватарки/иконки отсекаются
по ширине (`--min-width`, по умолч. 256) и весу (`--min-bytes`, 20 КБ).

```bash
python scripts\qwen_download_images.py --output d:\Projects\Demiurges\assets\new
python scripts\qwen_download_images.py --limit 5 --min-width 512
```

Имена — unix-timestamp как у Qwen (`1788692438.png`, коллизии — `_1`),
рядом `manifest_<ts>.json` (файл → URL → размер).

⚠️ Даёт ужатые превью (~500 КБ). Для оригиналов — п. 2.

## 2. Качественно: оригиналы через кнопку download — `qwen_download_full.py`

Кликает штатные кнопки `div.qwen-chat-package-comp-new-action-control-container-download`
(по одной на картинку, внутри `div.image-tool-container`), каталог приёма
задаётся через CDP `Browser.setDownloadBehavior` — диалогов нет.
Даёт исходники (~2 МБ) с серверными именами.

```bash
python scripts\qwen_download_full.py --output d:\Projects\Demiurges\assets\full
python scripts\qwen_download_full.py --probe          # только посчитать кнопки
python scripts\qwen_download_full.py --limit 2        # проба на 2 файлах
python scripts\qwen_download_full.py --offset 2       # докачать остальное
```

## 3. После скачивания: сверка и раскладка

Порядок кнопок/картинок в чате может не совпадать с порядком генерации —
обязательно сверить содержимое (пример: собрать контакт-лист через PIL
и посмотреть глазами), затем разложить с понятными именами.
Шаблон таблицы соответствия — `d:\Projects\Demiurges\ASSETS.md`.

Проверено 2026-09-06: 22/22 превью + 22/22 оригинала из одного чата,
`pytest tests/test_qwen_images.py tests/test_qwen_full.py` — 10 passed.
