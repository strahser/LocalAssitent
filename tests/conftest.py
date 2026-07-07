import shutil
import tempfile
from pathlib import Path

import pytest

from config.pipeline_configs import PIPELINE_DEFINITIONS
from core.pipeline.factory import PipelineFactory
from core.utils.file_io import FilePromptLoader, FileOutputWriter
from tests.mocks.browser_mock import MockBrowserDriver


@pytest.fixture
def temp_dir():
    """Создаёт временную директорию для тестов и удаляет её после."""
    dirpath = tempfile.mkdtemp(prefix="assistant_test_")
    yield Path(dirpath)
    shutil.rmtree(dirpath)

@pytest.fixture
def mock_driver():
    return MockBrowserDriver()

@pytest.fixture
def pipeline_factory():
    def _factory(pipeline_name: str, driver: MockBrowserDriver, loader=None, writer=None):
        if loader is None:
            loader = FilePromptLoader()
        if writer is None:
            writer = FileOutputWriter()
        pipeline_config = PIPELINE_DEFINITIONS.get(pipeline_name)
        if pipeline_config is None:
            raise ValueError(f"Неизвестный пайплайн: {pipeline_name}")
        return PipelineFactory.create_from_config(
            pipeline_config,
            driver=driver,
            loader=loader,
            writer=writer
        )
    return _factory

@pytest.fixture
def setup_code_test(temp_dir):
    logs_dir = temp_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / "file1.txt").write_text("data1")
    (logs_dir / "file2.log").write_text("log data")
    result_file = temp_dir / "result.txt"
    return {"logs_dir": logs_dir, "result_file": result_file}
