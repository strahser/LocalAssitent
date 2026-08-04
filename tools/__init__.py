"""tools — плагинная система инструментов LocalAssistant.
Импорт пакета регистрирует все инструменты (старые и новые) в реестре
tools.registry, чтобы `python -m tools --list` видел их все.
"""
from tools.registry import get_tool, list_tools, register, run_tool
from tools.read_file import read_file
from tools.write_file import write_file
from tools.search import glob_search, grep_search
from tools.list_dir import list_dir
from tools.execute import check_code_safety, execute_code
from tools.safety import is_safe_path, safe_join
from tools.merge_docs import merge_documents, merge_documents_multi
from tools.send_to_cloud import send_to_cloud
from tools.list_models import list_models
# новые инструменты: регистрируются сами через @register при импорте модулей
from tools.edit_file import edit_file
from tools.append_file import append_file
from tools.delete_file import delete_file
# явная регистрация «старых» инструментов (их модули не изменяются)
register("read_file")(read_file)
register("write_file")(write_file)
register("grep_search")(grep_search)
register("glob_search")(glob_search)
register("list_dir")(list_dir)
register("execute_code")(execute_code)
register("merge_documents")(merge_documents)
__all__ = [
    # старый API — имена сохранены
    "read_file",
    "write_file",
    "grep_search",
    "glob_search",
    "list_dir",
    "check_code_safety",
    "execute_code",
    "safe_join",
    "is_safe_path",
    "merge_documents",
    # новые инструменты
    "edit_file",
    "append_file",
    "delete_file",
    "merge_documents_multi",
    "send_to_cloud",
    "list_models",
    # реестр
    "register",
    "get_tool",
    "list_tools",
    "run_tool",
]
