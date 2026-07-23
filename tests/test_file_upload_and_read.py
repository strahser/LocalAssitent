"""
End-to-end test: upload files → send prompt → verify AI reads and responds.
"""
import sys, os, time
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

    # ── 1. Attach files ──────────────────────────────────
    test_files = [
        "config.py",
        "main.py",
    ]
    logger.log(f"📎 Тест: прикрепление файлов: {test_files}")

    ok = client.attach_files(test_files)
    if not ok:
        logger.log("❌ attach_files вернул False", "ERROR")
        return False
    logger.log("✅ attach_files OK")

    # ── 2. Send prompt ───────────────────────────────────
    prompt = (
        "Прочитай прикрепленные файлы config.py и main.py. "
        "Кратко опиши, что делает каждый файл (1-2 предложения на файл)."
    )
    logger.log(f"📤 Отправка запроса: {prompt}")

    result = client.send_prompt_with_code(prompt)
    if result is None:
        logger.log("❌ Не удалось получить ответ", "ERROR")
        return False

    full_text, code_text = result
    logger.log(f"✅ Ответ получен ({len(full_text)} символов)")
    logger.log(f"--- НАЧАЛО ОТВЕТА ---\n{full_text}\n--- КОНЕЦ ОТВЕТА ---")

    # ── 3. Verify files were referenced ──────────────────
    if ("config.py" in full_text or "config" in full_text.lower()) and \
       ("main.py" in full_text or "main" in full_text.lower()):
        logger.log("✅ AI упомянул оба файла")
    else:
        logger.log("⚠️ AI мог не прочитать файлы (не найдены имена в ответе)", "WARNING")

    client.close()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
