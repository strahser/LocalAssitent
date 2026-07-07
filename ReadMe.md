# 🤖 Local Assistant – Гибкий пайплайн для взаимодействия с DeepSeek

**Local Assistant** – это фреймворк для автоматизации работы с DeepSeek через Selenium. Позволяет создавать сценарии (пайплайны) из последовательных шагов: отправка промптов, извлечение кода, выполнение, обработка ошибок, сохранение результатов.

---

## 📦 Установка

1. **Клонируйте репозиторий**  
   ```bash
   git clone <url>
   cd LocalAssistant
   ```

2. **Создайте виртуальное окружение и установите зависимости**  
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   # или source venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

3. **Убедитесь, что установлен Microsoft Edge** (браузер используется для управления).  
   Путь к Edge должен быть:  
   - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` или  
   - `C:\Program Files\Microsoft\Edge\Application\msedge.exe`.

4. **Запустите браузер в режиме отладки** (один раз, в отдельном окне):  
   ```bash
   python start_browser.py
   ```
   Браузер откроется на странице DeepSeek. Оставьте это окно открытым.

---

## 🚀 Быстрый старт

### Режим «Текст» (обработка вопросов из файла)

1. Создайте файл `tests/questions.txt` с вопросами (каждый на новой строке).
2. Убедитесь, что в `config/config.py` установлено:  
   ```python
   SCENARIO = "text"
   ```
3. Запустите:
   ```bash
   python assistant.py
   ```
   Результат запишется в `answers.md` (вопрос + ответ в формате Markdown).

### Режим «Код» (генерация и выполнение Python-скрипта)

1. В `config/config.py` установите:  
   ```python
   SCENARIO = "code"
   ```
2. Запустите:
   ```bash
   python assistant.py
   ```
   Ассистент сгенерирует код, выполнит его и сохранит вывод в `result.txt`.

### Переопределение сценария через аргумент командной строки

```bash
python assistant.py text   # принудительно текстовый режим
python assistant.py code   # принудительно кодовый режим
```

---

## 🧩 Архитектура пайплайна

Пайплайн — это последовательность **шагов** (`Step`). Каждый шаг получает словарь `context` и возвращает его (модифицированным). Контекст — это общее хранилище данных между шагами.

### Основные компоненты:

- **`Step`** – абстрактный базовый класс. Все шаги наследуют его и реализуют метод `execute(context)`.
- **`Pipeline`** – контейнер шагов. Запускает их последовательно.
- **`PipelineFactory`** – создаёт пайплайн из конфигурации (объектов `StepConfig`).
- **`PipelineConfig`** – dataclass, описывающий список шагов.
- **`context`** – словарь, который передаётся между шагами. Стандартные ключи:
  - `prompt` – текущий вопрос/запрос.
  - `response` – ответ от DeepSeek.
  - `code` – извлечённый Python-код.
  - `error` – сообщение об ошибке (если возникла).
  - `execution_stdout`, `execution_stderr`, `execution_returncode` – результаты выполнения кода.
  - `prompts` – список вопросов (загруженных из файла).
  - `output_file_final` – итоговое имя файла (с timestamp, если задан).

---

## 📝 Как создать свой пайплайн

### 1. Опишите шаги в `pipeline_configs.py`

Вы можете использовать существующие шаги или создать новые (см. следующий раздел).  
Пример пайплайна для анализа тональности ответа:

```python
ANALYSIS_PIPELINE = PipelineConfig(
    description="Анализ тональности ответа DeepSeek",
    steps=[
        LoadPromptsStepConfig(input_file="questions.txt"),
        LoopStepConfig(
            for_each="prompts",
            steps=[
                SendPromptStepConfig(
                    prompt_template="Ответь на вопрос: {prompt}. После ответа напиши тональность (позитивная/нейтральная/негативная)."
                ),
                SaveOutputStepConfig(output_file="analysis.md", mode="a")
            ]
        )
    ]
)
```

Затем добавьте его в `PIPELINE_DEFINITIONS`:

```python
PIPELINE_DEFINITIONS = {
    "code": CODE_PIPELINE,
    "text": TEXT_PIPELINE,
    "analysis": ANALYSIS_PIPELINE   # новый сценарий
}
```

Теперь можно запускать:  
```bash
python assistant.py analysis
```

---

### 2. Добавьте новый шаг

Допустим, вы хотите шаг, который **очищает ответ от лишних пробелов**.  
Создайте класс в `core/pipeline/steps.py`:

```python
class CleanResponseStep(Step):
    def __init__(self, trim_lines: bool = True, **kwargs):
        self.trim_lines = trim_lines

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        response = context.get("response")
        if response:
            lines = response.splitlines()
            if self.trim_lines:
                lines = [line.strip() for line in lines if line.strip()]
            else:
                lines = [line.rstrip() for line in lines]
            context["response"] = "\n".join(lines)
        return context
```

#### 2.1. Добавьте конфигурацию в `pipeline_configs.py`

```python
@dataclass
class CleanResponseStepConfig(StepConfig):
    name: str = "CleanResponseStep"
    trim_lines: bool = True
```

#### 2.2. Зарегистрируйте шаг в фабрике (`factory.py`)

В методе `_get_step_class` добавьте:

```python
mapping = {
    ...
    "CleanResponseStep": CleanResponseStep,
}
```

И импортируйте `CleanResponseStep`.

#### 2.3. Используйте в пайплайне

Вставьте шаг в нужное место, например, после получения ответа:

```python
steps=[
    SendPromptStepConfig(...),
    CleanResponseStepConfig(trim_lines=True),
    SaveOutputStepConfig(...)
]
```

---

## 🧪 Тестирование пайплайна

Вы можете запускать пайплайн как самостоятельный скрипт (используя `assistant.py`) или напрямую в Python-коде:

```python
from core.pipeline.factory import PipelineFactory
from core.browser.deepseek_driver import DeepSeekBrowserDriver
from core.utils.file_io import FilePromptLoader, FileOutputWriter
from config.pipeline_configs import CODE_PIPELINE
from config import config

driver = DeepSeekBrowserDriver(...)
loader = FilePromptLoader()
writer = FileOutputWriter()

pipeline = PipelineFactory.create_from_config(
    CODE_PIPELINE,
    driver=driver,
    loader=loader,
    writer=writer
)
context = {"prompt": "Напиши скрипт для сортировки списка"}
result_context = pipeline.run()
print(result_context.get("code"))
```

---

## 🛠️ Доступные шаги (из коробки)

| Шаг | Назначение | Параметры |
|-----|------------|-----------|
| `NewChatStep` | Создаёт новый чат в DeepSeek | `enabled` (bool) |
| `SendPromptStep` | Отправляет промпт, получает ответ → записывает `response` в контекст | `prompt_template` (строка, может содержать `{key}`) |
| `ExtractCodeStep` | Извлекает Python-код из `response` → записывает `code` | `extractor_type` (`"regex"` или `"simple"`) |
| `ExecuteCodeStep` | Выполняет код из `code` → записывает `execution_*` ключи | `timeout` (сек) |
| `SaveOutputStep` | Сохраняет `response` в файл | `output_file`, `mode` (`"w"`, `"a"`) |
| `IfErrorStep` | Выполняет подпайплайн, если в контексте есть `error` | `sub_steps` (список конфигов) |
| `LoadPromptsStep` | Загружает вопросы из файла → записывает `prompts` | `input_file` |
| `InitOutputFileStep` | Генерирует имя выходного файла с timestamp → записывает `output_file_final` | `output_file`, `suffix` (bool) |
| `LoopStep` | Итерирует по элементам из `context[for_each]` и выполняет вложенные шаги для каждого | `for_each` (ключ контекста), `steps` |

---

## ⚙️ Управление конфигурацией

Все строковые идентификаторы (названия сценариев, типы экстракторов, стратегии) вынесены в **перечисления** (enum) в `config/constants.py`. Это обеспечивает безопасность типов и упрощает рефакторинг.

**Пример:**

```python
from config.constants import ScenarioType, ExtractorType

# Используйте в коде:
scenario = ScenarioType.TEXT.value   # "text"
extractor = ExtractorType.REGEX.value  # "regex"
```

При создании новых значений всегда добавляйте их в соответствующий Enum.

---

## 📚 Примеры сложных пайплайнов

### 1. Пайплайн с повторной попыткой при ошибке

```python
RETRY_PIPELINE = PipelineConfig(
    steps=[
        SendPromptStepConfig(prompt_template="Сгенерируй код для ..."),
        ExtractCodeStepConfig(extractor_type="regex"),
        ExecuteCodeStepConfig(timeout=30),
        IfErrorStepConfig(
            sub_steps=[
                SendPromptStepConfig(
                    prompt_template="Ошибка: {error}. Исправь код и верни только исправленный код."
                ),
                ExtractCodeStepConfig(extractor_type="regex"),
                ExecuteCodeStepConfig(timeout=30)
            ]
        ),
        SaveOutputStepConfig(output_file="result.txt")
    ]
)
```

### 2. Пайплайн с предобработкой промпта

```python
class PreprocessPromptStep(Step):
    def execute(self, context):
        prompt = context.get("prompt", "")
        prompt = prompt.strip().capitalize()
        context["prompt"] = prompt
        return context

# Затем включить в любой пайплайн перед SendPromptStep.
```

---

## ❗ Часто задаваемые вопросы

**Q: Как изменить таймаут для выполнения кода?**  
A: В конфигурации `ExecuteCodeStepConfig` задайте параметр `timeout` (в секундах).

**Q: Могу ли я использовать свой браузер, кроме Edge?**  
A: Да, но нужно реализовать класс, наследующий `BrowserDriver`, и заменить `DeepSeekBrowserDriver` в `assistant.py`.

**Q: Где хранятся логи?**  
A: По умолчанию в `assistant.log`. Можно настроить уровень логирования в `config.py`.

**Q: Как запустить без графического интерфейса (headless)?**  
A: В `deepseek_driver.py` добавьте опцию `--headless` при создании драйвера, но учтите, что DeepSeek может блокировать headless-режим.

---

## 🤝 Вклад

Если вы хотите улучшить проект – создавайте pull request или открывайте issue.  
При добавлении новых шагов следуйте архитектуре:

- Один шаг – одна ответственность.
- Используйте контекст для передачи данных.
- Добавляйте параметры через dataclass-конфигурации.

---

## 📄 Лицензия

MIT