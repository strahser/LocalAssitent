from core.interfaces import CodeExecutor, ExecutionResult

class ExecuteCodeUseCase:
    def __init__(self, executor: CodeExecutor):
        self.executor = executor

    def execute(self, code: str) -> ExecutionResult:
        return self.executor.execute(code)
