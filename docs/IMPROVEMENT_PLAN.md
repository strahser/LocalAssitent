# План улучшений LocalAssitent

## Приоритет 1: Безопасность (Критический)

### 1.1 Создать tools/safety.py
- Санитизация путей через safe_join()
- Проверка выхода за пределы проекта

### 1.2 Обновить tools/read_file.py
- Использовать safe_join() вместо os.path.abspath

### 1.3 Обновить tools/write_file.py
- Использовать safe_join() для записи

### 1.4 Обновить tools/search.py
- Ограничить корень проекта для grep_search и glob_search

### 1.5 Обновить tools/execute.py
- Добавить проверку опасных паттернов
- Ограничить модули

---

## Приоритет 2: Архитектура (Высокий)

### 2.1 Создать agent/browser/manager.py
- BrowserManager для запуска и подключения Edge

### 2.2 Создать agent/handlers/message_sender.py
- MessageSender для отправки сообщений

### 2.3 Создать agent/handlers/response_reader.py
- ResponseReader для извлечения ответов

### 2.4 Создать agent/handlers/file_attacher.py
- FileAttacher для прикрепления файлов

### 2.5 Обновить agent/selenium_client.py
- Сделать фасадом, использующим новые классы

---

## Приоритет 3: Тесты (Высокий)

### 3.1 tests/test_extractors.py
- Тесты извлечения кода из ответов

### 3.2 tests/test_config.py
- Тесты парсинга аргументов

### 3.3 tests/test_tools.py
- Тесты инструментов (read, write, search)

### 3.4 tests/test_safety.py
- Тесты санитизации путей

---

## Приоритет 4: Надёжность (Средний)

### 4.1 Добавить retry_on_stale декоратор
- Для ElementFinder методов

### 4.2 Улучшить логирование
- Заменить except: pass на логирование

### 4.3 Оптимизировать ожидания
- Заменить time.sleep на WebDriverWait

---

## Приоритет 5: Инфраструктура (Средний)

### 5.1 Создать .env.example
- Документировать переменные окружения

### 5.2 Обновить requirements.txt
- Добавить pytest, pytest-mock, python-dotenv

### 5.3 Создать .github/workflows/test.yml
- CI/CD для тестов и линтинга
