import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Обновлён: {path}")


steps_path = PROJECT_ROOT / "core" / "pipeline" / "steps.py"
if steps_path.exists():
    content = read_file(steps_path)

    # Заменяем класс SaveOutputStep на исправленную версию
    new_save_step = '''class SaveOutputStep(Step):
    def __init__(self, writer: OutputWriter, output_file: str = None, mode: str = "a"):
        self.writer = writer
        self.output_file = output_file
        self.mode = mode

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        final_file = context.get("output_file_final", self.output_file)
        if final_file is None:
            raise ValueError("Не указан файл для сохранения")
        response = context.get("response") or ""
        prompt = context.get("prompt") or ""
        if response:
            block = f"## Вопрос\\n\\n{prompt}\\n\\n## Ответ\\n\\n{response}\\n\\n---\\n"
            self.writer.write(block, final_file, self.mode)
        return context
'''
    # Заменяем старый класс
    pattern = r'class SaveOutputStep\(Step\):.*?(?=class |$)'
    content = re.sub(pattern, new_save_step, content, flags=re.DOTALL)
    write_file(steps_path, content)
else:
    print("⚠️ core/pipeline/steps.py не найден")

print("✅ SaveOutputStep исправлен: используется правильный f-string с \\n.")
print("📌 Запустите python assistant.py снова.")