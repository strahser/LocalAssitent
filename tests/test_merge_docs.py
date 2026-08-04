"""Tests for tools/merge_docs.py"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.merge_docs import collect_files, merge_documents, merge_documents_multi, format_file_block
from pathlib import Path


class TestMergeDocs:
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

    def test_collect_files_by_extension(self):
        self._create_file("a.py", "print('hello')")
        self._create_file("b.cs", "class Foo {}")
        self._create_file("c.txt", "plain text")

        files = collect_files(str(self.root), extensions=[".py"])
        assert len(files) == 1
        assert files[0].name == "a.py"

    def test_collect_files_multiple_extensions(self):
        self._create_file("a.py", "x=1")
        self._create_file("b.cs", "y=2")
        self._create_file("c.txt", "z=3")

        files = collect_files(str(self.root), extensions=[".py", ".cs"])
        assert len(files) == 2

    def test_collect_files_excludes_dirs(self):
        self._create_file("src/main.py", "x=1")
        self._create_file("__pycache__/cached.pyc", "binary")
        self._create_file(".git/config", "git")

        files = collect_files(str(self.root), extensions=[".py", ".pyc"])
        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_collect_files_max_size(self):
        self._create_file("small.py", "x=1")
        self._create_file("big.py", "x" * 200_000)

        files = collect_files(str(self.root), extensions=[".py"], max_file_size=10_000)
        assert len(files) == 1
        assert files[0].name == "small.py"

    def test_collect_files_include_patterns(self):
        self._create_file("src/Command.cs", "cmd")
        self._create_file("src/Helper.cs", "help")
        self._create_file("src/Tests.cs", "test")

        files = collect_files(
            str(self.root), extensions=[".cs"],
            include_patterns=["*Command*"],
        )
        assert len(files) == 1
        assert files[0].name == "Command.cs"

    def test_collect_files_exclude_patterns(self):
        self._create_file("src/Foo.cs", "foo")
        self._create_file("src/FooTests.cs", "test")

        files = collect_files(
            str(self.root), extensions=[".cs"],
            exclude_patterns=["*Tests*"],
        )
        assert len(files) == 1
        assert files[0].name == "Foo.cs"

    def test_format_file_block(self):
        fp = self._create_file("hello.py", "print('hello')\nprint('world')")
        block = format_file_block(fp, self.root)
        assert "FILE: hello.py" in block
        assert "LINES: 2" in block
        assert "print('hello')" in block

    def test_merge_documents_creates_output(self):
        self._create_file("a.py", "x = 1")
        self._create_file("b.py", "y = 2")
        output = str(self.root / "output.txt")

        result = merge_documents(
            root_dir=str(self.root),
            output_file=output,
            extensions=[".py"],
        )
        assert "Готово" in result
        assert os.path.exists(output)

        content = Path(output).read_text(encoding="utf-8")
        assert "FILE: a.py" in content
        assert "FILE: b.py" in content

    def test_merge_documents_with_prompt(self):
        self._create_file("code.py", "x = 1")
        output = str(self.root / "output.txt")

        merge_documents(
            root_dir=str(self.root),
            output_file=output,
            extensions=[".py"],
            prompt="Analyze this code",
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "INSTRUCTION FOR AI" in content
        assert "Analyze this code" in content

    def test_merge_documents_with_prompt_file(self):
        self._create_file("code.py", "x = 1")
        prompt_file = self._create_file("prompt.txt", "Review this project")
        output = str(self.root / "output.txt")

        merge_documents(
            root_dir=str(self.root),
            output_file=output,
            extensions=[".py"],
            prompt_file=str(prompt_file),
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "Review this project" in content

    def test_merge_documents_no_files(self):
        output = str(self.root / "output.txt")
        result = merge_documents(
            root_dir=str(self.root),
            output_file=output,
            extensions=[".py"],
        )
        assert "не найдены" in result.lower() or "not found" in result.lower()
        assert not os.path.exists(output)

    def test_merge_documents_summary(self):
        self._create_file("a.py", "x = 1\ny = 2")
        output = str(self.root / "output.txt")

        merge_documents(
            root_dir=str(self.root),
            output_file=output,
            extensions=[".py"],
            add_summary=True,
        )
        content = Path(output).read_text(encoding="utf-8")
        assert "MERGED PROJECT CONTEXT" in content
        assert "Total files: 1" in content
        assert "Total lines: 2" in content

    def test_merge_documents_multi_two_dirs(self):
        dir_a = Path(tempfile.mkdtemp())
        dir_b = Path(tempfile.mkdtemp())
        try:
            (dir_a / "a.cs").write_text("class A {}", encoding="utf-8")
            (dir_b / "b.cs").write_text("class B {}", encoding="utf-8")
            output = str(self.root / "multi_output.txt")

            result = merge_documents_multi(
                root_dirs=[str(dir_a), str(dir_b)],
                output_file=output,
                extensions=[".cs"],
            )
            assert "Готово" in result
            assert os.path.exists(output)

            content = Path(output).read_text(encoding="utf-8")
            # оба FILE-заголовка присутствуют
            assert "FILE: a.cs" in content
            assert "FILE: b.cs" in content
            # оба DIR-заголовка присутствуют
            assert f"DIR: {dir_a.resolve()}" in content
            assert f"DIR: {dir_b.resolve()}" in content
            # содержимое обоих файлов объединено
            assert "class A {}" in content
            assert "class B {}" in content
        finally:
            shutil.rmtree(str(dir_a), ignore_errors=True)
            shutil.rmtree(str(dir_b), ignore_errors=True)

    def test_merge_documents_multi_single_dir(self):
        self._create_file("a.cs", "class A {}")
        output = str(self.root / "multi_one.txt")

        result = merge_documents_multi(
            root_dirs=[str(self.root)],
            output_file=output,
            extensions=[".cs"],
        )
        assert "Готово" in result
        content = Path(output).read_text(encoding="utf-8")
        assert "FILE: a.cs" in content
        assert f"DIR: {self.root.resolve()}" in content


def run_tests():
    test = TestMergeDocs()
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
