import re

with open("src/orchestrator/workflow.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Workflow Manager — Defines and executes multi-step agent workflows.\"\"\"

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

class MatrixExpansionLimitExceeded(RuntimeError):
    \"\"\"Raised when a workflow attempts to fan-out beyond allowed bounds.\"\"\"

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class WorkflowStep:
    def __init__(self, name: str, handler: Callable, retries: int = 0, timeout: int = 300, matrix: Optional[List[Any]] = None):
        self.id = str(uuid4())
        self.name = name
        self.handler = handler
        self.retries = retries
        self.timeout = timeout
        self.matrix = matrix or []
        self.status = StepStatus.PENDING
        self.result: Any = None
        self.error: Optional[str] = None

class Workflow:
    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid4())
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self._step_map: Dict[str, WorkflowStep] = {}
        self.status = StepStatus.PENDING

    def add_step(self, step: WorkflowStep) -> "Workflow":
        self.steps.append(step)
        self._step_map[step.id] = step
        return self

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        return self._step_map.get(step_id)

class WorkflowManager:
    def __init__(self, max_matrix_size: int = 256):
        self._workflows: Dict[str, Workflow] = {}
        self._max_matrix_size = max_matrix_size
        self._audit_events: List[Dict[str, Any]] = []

    def create_workflow(self, name: str, description: str = "") -> Workflow:
        workflow = Workflow(name, description)
        self._workflows[workflow.id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[Workflow]:
        return list(self._workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        return self._workflows.pop(workflow_id, None) is not None

    def execute_workflow(self, workflow_id: str) -> bool:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        # Pre-flight matrix expansion validation
        for step in workflow.steps:
            if step.matrix and len(step.matrix) > self._max_matrix_size:
                self._audit_events.append({
                    "workflow_id": workflow_id,
                    "step_id": step.id,
                    "event": "matrix_expansion_rejected",
                    "reason": f"matrix size {len(step.matrix)} exceeds limit {self._max_matrix_size}"
                })
                workflow.status = StepStatus.FAILED
                step.status = StepStatus.FAILED
                step.error = "MatrixExpansionLimitExceeded"
                raise MatrixExpansionLimitExceeded(f"Step {step.name} matrix expansion ({len(step.matrix)}) exceeds limit {self._max_matrix_size}.")

        workflow.status = StepStatus.RUNNING
        for step in workflow.steps:
            step.status = StepStatus.RUNNING
            try:
                # Mocking matrix execution by passing inputs if present
                if step.matrix:
                    results = []
                    for item in step.matrix:
                        results.append(step.handler(item))
                    step.result = results
                else:
                    step.result = step.handler()
                    
                step.status = StepStatus.COMPLETED
            except Exception as e:
                step.error = str(e)
                step.status = StepStatus.FAILED
                workflow.status = StepStatus.FAILED
                return False

        workflow.status = StepStatus.COMPLETED
        return True

    def audit_events(self) -> List[Dict[str, Any]]:
        return self._audit_events
"""

with open("src/orchestrator/workflow.py", "w") as f:
    f.write(new_code + "\n" + tail)
