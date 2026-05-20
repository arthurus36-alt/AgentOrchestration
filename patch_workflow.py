import re

with open("src/orchestrator/workflow.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Workflow Manager — Defines and executes multi-step agent workflows.\"\"\"

from enum import Enum
from inspect import Parameter, signature
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class WorkflowStateError(RuntimeError):
    \"\"\"Raised when a workflow transition would violate lifecycle state.\"\"\"


class WorkflowStep:
    def __init__(
        self,
        name: str,
        handler: Callable,
        retries: int = 0,
        timeout: int = 300,
        compensate: Optional[Callable] = None,
    ):
        self.id = str(uuid4())
        self.name = name
        self.handler = handler
        self.compensate = compensate
        self.retries = retries
        self.timeout = timeout
        self.status = StepStatus.PENDING
        self.result: Any = None
        self.error: Optional[str] = None
        self.compensation_status = "pending" if compensate else "skipped"
        self.compensation_error: Optional[str] = None

class Workflow:
    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid4())
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self._step_map: Dict[str, WorkflowStep] = {}
        self.status = StepStatus.PENDING
        self.audit_events: List[Dict[str, Any]] = []
        self.metrics: Dict[str, int] = {
            "compensation_failures": 0,
            "downstream_blocks": 0,
            "partial_rollback_blocks": 0,
        }

    def add_step(self, step: WorkflowStep) -> "Workflow":
        if self.status != StepStatus.PENDING:
            raise WorkflowStateError("cannot add steps after workflow dispatch")
        self.steps.append(step)
        self._step_map[step.id] = step
        return self

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        return self._step_map.get(step_id)

class WorkflowManager:
    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}

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

        completed_steps: List[WorkflowStep] = []
        workflow.status = StepStatus.RUNNING
        for index, step in enumerate(workflow.steps):
            if step.status != StepStatus.PENDING:
                continue
            step.status = StepStatus.RUNNING
            try:
                result = step.handler()
                step.result = result
                step.status = StepStatus.COMPLETED
                completed_steps.append(step)
            except Exception as e:
                step.error = e.__class__.__name__
                step.status = StepStatus.FAILED
                rollback_failures = self._compensate_completed_steps(
                    workflow,
                    completed_steps,
                )
                self._block_downstream_steps(
                    workflow,
                    index + 1,
                    step,
                    e.__class__.__name__,
                    rollback_failures,
                )
                workflow.status = StepStatus.FAILED
                return False

        workflow.status = StepStatus.COMPLETED
        return True

    def _compensate_completed_steps(
        self,
        workflow: Workflow,
        completed_steps: List[WorkflowStep],
    ) -> List[WorkflowStep]:
        failed_steps: List[WorkflowStep] = []
        for step in reversed(completed_steps):
            compensate = getattr(step, "compensate", None)
            if not compensate:
                step.compensation_status = "skipped"
                continue

            step.compensation_status = "running"
            try:
                self._run_compensation(step, compensate)
                step.compensation_status = "completed"
                step.compensation_error = None
            except Exception as exc:
                step.compensation_status = "failed"
                step.compensation_error = exc.__class__.__name__
                failed_steps.append(step)
                workflow.metrics["compensation_failures"] += 1
                workflow.audit_events.append(
                    {
                        "event": "compensation_failed",
                        "workflow_id": workflow.id,
                        "step_id": step.id,
                        "step_name": step.name,
                        "error_type": exc.__class__.__name__,
                    }
                )
        return failed_steps

    def _run_compensation(
        self,
        step: WorkflowStep,
        compensate: Callable,
    ) -> None:
        if self._compensation_accepts_result(compensate):
            compensate(step.result)
        else:
            compensate()

    def _compensation_accepts_result(self, compensate: Callable) -> bool:
        try:
            parameters = signature(compensate).parameters.values()
        except (TypeError, ValueError):
            return False

        positional_kinds = {
            Parameter.POSITIONAL_ONLY,
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.VAR_POSITIONAL,
        }
        return any(
            parameter.kind in positional_kinds
            for parameter in parameters
        )

    def _block_downstream_steps(
        self,
        workflow: Workflow,
        start_index: int,
        failed_step: WorkflowStep,
        failure_type: str,
        rollback_failures: List[WorkflowStep],
    ) -> None:
        partial_rollback = bool(rollback_failures)
        reason = (
            "blocked_after_partial_rollback"
            if partial_rollback
            else "blocked_after_failure"
        )
        blocked_steps: List[WorkflowStep] = []
        for step in workflow.steps[start_index:]:
            if step.status != StepStatus.PENDING:
                continue
            step.status = StepStatus.SKIPPED
            step.error = reason
            blocked_steps.append(step)

        if not blocked_steps:
            return

        workflow.metrics["downstream_blocks"] += len(blocked_steps)
        if partial_rollback:
            workflow.metrics["partial_rollback_blocks"] += 1

        event = (
            "downstream_blocked_after_partial_rollback"
            if partial_rollback
            else "downstream_blocked_after_failure"
        )
        workflow.audit_events.append(
            {
                "event": event,
                "workflow_id": workflow.id,
                "failed_step_id": failed_step.id,
                "failed_step_name": failed_step.name,
                "failure_type": failure_type,
                "rollback_failed_step_ids": [
                    step.id for step in rollback_failures
                ],
                "rollback_failed_step_names": [
                    step.name for step in rollback_failures
                ],
                "blocked_step_ids": [step.id for step in blocked_steps],
                "blocked_step_names": [step.name for step in blocked_steps],
                "reason": (
                    "partial_rollback" if partial_rollback else "failure"
                ),
            }
        )
"""

with open("src/orchestrator/workflow.py", "w") as f:
    f.write(new_code + "\n" + tail)
