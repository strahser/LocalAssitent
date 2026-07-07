from typing import List, Dict, Any
from core.pipeline.step import Step

class Pipeline:
    def __init__(self, steps: List[Step], context: Dict[str, Any] = None):
        self.steps = steps
        self.context = context or {}

    def run(self) -> Dict[str, Any]:
        for step in self.steps:
            try:
                self.context = step.execute(self.context)
            except Exception as e:
                # Можно логировать или пробрасывать дальше
                raise
        return self.context
