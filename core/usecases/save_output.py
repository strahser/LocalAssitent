from core.interfaces import OutputWriter

class SaveOutputUseCase:
    def __init__(self, writer: OutputWriter):
        self.writer = writer

    def execute(self, data: str, destination: str, mode: str = "w") -> None:
        self.writer.write(data, destination, mode)
