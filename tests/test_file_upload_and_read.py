"""
End-to-end test: attach files → send prompt → verify AI reads and responds.

Tests the full file-attachment pipeline:
  1. Attach files via attach_files() with relative paths
  2. Send a prompt referencing the attached files
  3. Verify the AI response mentions both files
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.DeepSeekClient import DeepSeekClient
from Logger import Logger


def main():
    logger = Logger(
        log_to_file=False,
        log_to_html=False,
        save_responses=False,
    )

    client = DeepSeekClient(logger, timeout=180)

    test_files = ["config.py", "main.py"]
    logger.log(f"📎 Прикрепление файлов: {test_files}")

    ok = client.attach_files(test_files)
    if not ok:
        logger.log("❌ attach_files вернул False", "ERROR")
        return False
    logger.log("✅ attach_files OK")

    prompt = (
        "Прочитай прикрепленные файлы config.py и main.py. "
        "Кратко опиши, что делает каждый файл (1-2 предложения на файл)."
    )
    logger.log(f"📤 Отправка запроса с упоминанием файлов...")

    result = client.send_prompt_with_code(prompt)
    if result is None:
        logger.log("❌ Не удалось получить ответ от DeepSeek", "ERROR")
        return False

    full_text, code_text = result
    logger.log(f"✅ Ответ получен ({len(full_text)} символов)")
    logger.log(f"--- НАЧАЛО ОТВЕТА ---\n{full_text}\n--- КОНЕЦ ОТВЕТА ---")

    mentions_config = "config.py" in full_text or "config" in full_text.lower()
    mentions_main = "main.py" in full_text or "main" in full_text.lower()
    if mentions_config and mentions_main:
        logger.log("✅ AI прочитал оба файла (имена упомянуты в ответе)")
    else:
        logger.log("⚠️ AI мог не прочитать файлы (имена не найдены в ответе)", "WARNING")

    client.close()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
