"""Tests for tools/collect_context.py"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.collect_context import (
    detect_project_types,
    get_extensions,
    is_temp_file,
    build_general_task,
    collect_context,
    TEMP_FILE_PATTERNS,
)


class TestCollectContext:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, rel_path, content=""):
        fp = self.root / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return fp

    def _task_file(self):
        tf = self._create_file("task.txt", "ОБЩЕЕ ЗАДАНИЕ ДЛЯ ОБЛАЧНОГО ИИ\nпроверка")
        return str(tf)

    # --- detect_project_types ---

    def test_detect_project_type_cs(self):
        self._create_file("Proj/Proj.csproj", "<Project/>")
        self._create_file("Proj/Program.cs", "class Program {}")
        types = detect_project_types([str(self.root / "Proj")])
        assert types[str(self.root / "Proj")] == "cs"

    def test_detect_project_type_py(self):
        self._create_file("pyproj/requirements.txt", "selenium")
        self._create_file("pyproj/main.py", "print(1)")
        types = detect_project_types([str(self.root / "pyproj")])
        assert types[str(self.root / "pyproj")] == "py"

    def test_detect_project_type_mixed(self):
        self._create_file("mix/A.cs", "class A {}")
        self._create_file("mix/b.py", "x=1")
        types = detect_project_types([str(self.root / "mix")])
        assert types[str(self.root / "mix")] == "mixed"

    def test_detect_project_type_unknown(self):
        self._create_file("empty/readme.txt", "hi")
        types = detect_project_types([str(self.root / "empty")])
        assert types[str(self.root / "empty")] == "unknown"

    # --- get_extensions ---

    def test_get_extensions_cs(self):
        exts = get_extensions("cs")
        assert ".cs" in exts and ".xaml" in exts and ".csproj" in exts
        assert ".py" not in exts

    def test_get_extensions_py(self):
        exts = get_extensions("py")
        assert ".py" in exts and ".toml" in exts
        assert ".cs" not in exts

    def test_get_extensions_mixed(self):
        exts = get_extensions("mixed")
        assert ".cs" in exts and ".py" in exts

    # --- is_temp_file ---

    def test_is_temp_file_patterns(self):
        assert is_temp_file(".gigacode/plans/a.plan.md") is True
        assert is_temp_file("obj/Debug/x.AssemblyAttributes.cs") is True
        assert is_temp_file("src/tmp.log") is True
        assert is_temp_file("src/backup.bak") is True
        assert is_temp_file("user.suo") is True
        assert is_temp_file("cache.pyc") is True
        assert is_temp_file("gen.g.cs") is True

    def test_is_temp_file_normal(self):
        assert is_temp_file("src/Program.cs") is False
        assert is_temp_file("src/util.py") is False
        assert is_temp_file("View/UserControls/Foo.xaml.cs") is False  # "Combin"-подобные ложные срабатывания
        assert is_temp_file("Proj.csproj") is False

    # --- build_general_task ---

    def test_build_general_task_missing_file(self):
        assert build_general_task(str(self.root / "nope.txt")) == ""

    def test_build_general_task_returns_block(self):
        tf = self._task_file()
        block = build_general_task(tf)
        assert "ОБЩЕЕ ЗАДАНИЕ" in block
        assert block.startswith("\n" + "=" * 72)

    # --- collect_context ---

    def test_collect_context_prepends_general_task(self):
        self._create_file("code.py", "x = 1")
        tf = self._task_file()
        output = str(self.root / "out.txt")
        collect_context(
            [str(self.root)], output_file=output,
            extensions=[".py"], add_task=True, task_file=tf,
            add_summary=False,
        )
        content = Path(output).read_text(encoding="utf-8")
        # общее задание должно быть в НАЧАЛЕ
        assert "ОБЩЕЕ ЗАДАНИЕ" in content.splitlines()[2]
        # код идёт ПОСЛЕ задания
        assert content.index("ОБЩЕЕ ЗАДАНИЕ") < content.index("FILE: code.py")

    def test_collect_context_no_task(self):
        self._create_file("code.py", "x = 1")
        output = str(self.root / "out.txt")
        collect_context(
            [str(self.root)], output_file=output,
            extensions=[".py"], add_task=False, add_summary=False,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "ОБЩЕЕ ЗАДАНИЕ" not in content
        assert "FILE: code.py" in content

    def test_collect_context_excludes_temp_files(self):
        self._create_file("src/A.cs", "class A {}")
        self._create_file("obj/Debug/gen.AssemblyAttributes.cs", "// gen")
        self._create_file(".gigacode/plans/z.plan.md", "# plan")
        self._create_file("logs/debug.log", "log")
        output = str(self.root / "out.txt")
        collect_context(
            [str(self.root)], output_file=output,
            extensions=[".cs", ".md", ".log"], add_task=False, add_summary=False,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert f"FILE: src{os.sep}A.cs" in content
        assert "gen.AssemblyAttributes.cs" not in content
        assert "z.plan.md" not in content
        assert "debug.log" not in content

    def test_collect_context_project_type_py_extensions(self):
        self._create_file("main.py", "print(1)")
        self._create_file("main.cs", "class C {}")
        output = str(self.root / "out.txt")
        collect_context(
            [str(self.root)], output_file=output,
            project_types={str(self.root): "py"}, add_task=False, add_summary=False,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "FILE: main.py" in content
        assert "main.cs" not in content

    def test_collect_context_max_size_skip(self):
        self._create_file("small.cs", "class S {}")
        self._create_file("big.cs", "x" * 200_000)
        output = str(self.root / "out.txt")
        result = collect_context(
            [str(self.root)], output_file=output,
            extensions=[".cs"], add_task=False, add_summary=False,
            max_file_size=10_000,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "FILE: small.cs" in content
        assert "big.cs" not in content
        assert "по размеру" in result

    def test_collect_context_multi_dir(self):
        dir_a = Path(tempfile.mkdtemp())
        dir_b = Path(tempfile.mkdtemp())
        try:
            (dir_a / "a.cs").write_text("class A {}", encoding="utf-8")
            (dir_b / "b.cs").write_text("class B {}", encoding="utf-8")
            output = str(self.root / "multi.txt")
            collect_context(
                [str(dir_a), str(dir_b)], output_file=output,
                extensions=[".cs"], add_task=False, add_summary=False,
            )
            content = Path(output).read_text(encoding="utf-8")
            assert "FILE: a.cs" in content
            assert "FILE: b.cs" in content
            assert f"DIR: {dir_a.resolve()}" in content
            assert f"DIR: {dir_b.resolve()}" in content
        finally:
            shutil.rmtree(str(dir_a), ignore_errors=True)
            shutil.rmtree(str(dir_b), ignore_errors=True)

    def test_collect_context_summary(self):
        self._create_file("a.cs", "class A {}")
        output = str(self.root / "out.txt")
        collect_context(
            [str(self.root)], output_file=output,
            extensions=[".cs"], add_task=False, add_summary=True,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "CLOUD PROJECT CONTEXT" in content
        assert "Total files: 1" in content

    def test_temp_file_patterns_not_empty(self):
        assert len(TEMP_FILE_PATTERNS) > 5
        assert "*.plan.md" in TEMP_FILE_PATTERNS


def run_tests():
    test = TestCollectContext()
    passed = 0
    total = 0

    for method_name in dir(test):
        if not method_name.startswith("test_"):
            continue
        total += 1
        test.setup_method()
        try:
            getattr(test, method_name)()
            print(f"  [PASS] {method_name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {method_name}: {e}")
        except Exception as e:
            print(f"  [ERROR] {method_name}: {e}")
        finally:
            test.teardown_method()

    print(f"\nRESULT: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)