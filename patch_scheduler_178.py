import re

with open("src/orchestrator/scheduler.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Task Scheduler — Priority-based task queuing and dispatch.\"\"\"

import asyncio
import heapq
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

from src.common.metrics import metrics

class RunState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    TERMINAL_SUCCESS = "terminal_success"
    TERMINAL_FAILURE = "terminal_failure"

class QueueCapacityExceeded(RuntimeError):
    \"\"\"Raised when a queue has no available scheduler capacity.\"\"\"

class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._counter = 0

    def push(self, item: Any, priority: int = 0) -> None:
        heapq.heappush(self._queue, (-priority, self._counter, item))
        self._counter += 1

    def pop(self) -> Optional[Any]:
        if self._queue:
            return heapq.heappop(self._queue)[2]
        return None

    def peek(self) -> Optional[Any]:
        if self._queue:
            return self._queue[0][2]
        return None

    def __len__(self) -> int:
        return len(self._queue)

class TaskScheduler:
    def __init__(self, queue_capacities: Optional[Dict[str, int]] = None, time_fn: Optional[Callable[[], float]] = None):
        self._time_fn = time_fn or time.time
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, Dict] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._task_queues: Dict[str, str] = {}
        self._capacity_claims: Dict[str, Set[str]] = {}
        self._queue_capacities = queue_capacities or {}
        self._audit_log: List[Dict[str, Any]] = []
        self._terminal_outcomes: Dict[str, str] = {}
        self._dispatch_metrics: Dict[str, int] = {"blackout_deferrals": 0}
        self._max_retries = 3

    def _is_terminal(self, task: Dict) -> bool:
        state = task.get("run_state", RunState.PENDING.name)
        return state in (RunState.TERMINAL_SUCCESS.name, RunState.TERMINAL_FAILURE.name)

    def _set_terminal_outcome(self, task_id: str, outcome: str) -> None:
        self._terminal_outcomes[task_id] = outcome

    def _is_already_terminal(self, task_id: str) -> bool:
        return task_id in self._terminal_outcomes

    def _reserve_capacity(self, queue: str, task_id: str) -> None:
        claims = self._capacity_claims.setdefault(queue, set())
        limit = self._queue_capacities.get(queue)
        if limit is not None and len(claims) >= limit:
            self._record_audit("enqueue_rejected_capacity", task_id, queue)
            metrics.increment("scheduler.enqueue.capacity_rejected")
            raise QueueCapacityExceeded(f"Queue {queue} capacity exceeded")
        claims.add(task_id)

    def _release_capacity(self, queue: str, task_id: str) -> None:
        claims = self._capacity_claims.get(queue)
        if claims and task_id in claims:
            claims.remove(task_id)

    def _record_audit(self, decision: str, task_id: str, queue: str, reason: str = "") -> None:
        self._audit_log.append({
            "decision": decision,
            "task_id": task_id,
            "queue": queue,
            "reason": reason,
            "timestamp": self._time_fn(),
        })

    def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit_log)
        
    def capacity_snapshot(self) -> Dict[str, Dict[str, Optional[int]]]:
        queues = set(self._queue_capacities) | set(self._capacity_claims)
        return {
            queue: {
                "used": len(self._capacity_claims.get(queue, set())),
                "limit": self._queue_capacities.get(queue),
            }
            for queue in sorted(queues)
        }

    def _push_queued_task(self, task: Dict, queue: str, priority: int) -> None:
        if queue not in self._queues:
            self._queues[queue] = PriorityQueue()
        self._queues[queue].push(task, priority)

    def _float_or_none(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _blackout_windows(self, task: Dict) -> List[Tuple[float, float]]:
        policy = task.get("dispatch_policy") or {}
        workflow = task.get("workflow") or {}
        workflow_policy = workflow.get("dispatch_policy") or {}
        candidates = (
            workflow_policy.get("blackout_windows")
            or workflow.get("blackout_windows")
            or policy.get("blackout_windows")
            or task.get("blackout_windows")
            or []
        )
        windows: List[Tuple[float, float]] = []
        for candidate in candidates:
            if isinstance(candidate, dict):
                start = self._float_or_none(candidate.get("start"))
                end = self._float_or_none(candidate.get("end"))
                if start is not None and end is not None:
                    windows.append((start, end))
        return windows

    def _active_blackout(self, task: Dict, now: float) -> Optional[Tuple[float, float]]:
        for start, end in self._blackout_windows(task):
            if start <= now < end:
                return start, end
        return None

    def _record_blackout(self, task: Dict, queue: str, blackout: Tuple[float, float]) -> None:
        self._dispatch_metrics["blackout_deferrals"] += 1
        self._audit_log.append(
            {
                "decision": "dispatch_deferred_blackout",
                "task_id": task.get("id"),
                "queue": queue,
                "window_start": blackout[0],
                "window_end": blackout[1],
                "reason": "workflow_blackout_window",
            }
        )

    def enqueue(
        self,
        task: Dict,
        queue: str = "default",
        priority: int = 0,
    ) -> str:
        task_id = task.get("id")
        if task_id and self._is_already_terminal(task_id):
            return task_id

        task_id = task_id or str(uuid4())
        queued_task = dict(task)
        queued_task["id"] = task_id
        queued_task["enqueued_at"] = self._time_fn()
        queued_task["retries"] = task.get("retries", 0)
        queued_task["priority"] = priority
        queued_task["run_state"] = RunState.PENDING.name

        self._reserve_capacity(queue, task_id)
        try:
            self._push_queued_task(queued_task, queue, priority)
        except Exception as exc:
            self._release_capacity(queue, task_id)
            self._record_audit(
                "enqueue_rolled_back",
                task_id,
                queue,
                type(exc).__name__,
            )
            metrics.increment("scheduler.enqueue.rollback")
            raise

        task.update(queued_task)
        self._task_queues[task_id] = queue
        self._record_audit("enqueue_committed", task_id, queue)
        metrics.increment("scheduler.enqueue.committed")
        return task_id

    def schedule(
        self,
        task: Dict,
        delay: float,
        queue: str = "default",
        priority: int = 0,
    ) -> str:
        task_id = task.get("id") or str(uuid4())
        task["id"] = task_id
        task["run_state"] = RunState.PENDING.name
        self._scheduled[task_id] = {
            "task": task,
            "due_at": self._time_fn() + delay,
            "queue": queue,
            "priority": priority
        }
        return task_id

    def _promote_ready_scheduled(self, queue: str, now: float) -> None:
        ready_ids = [
            task_id
            for task_id, entry in self._scheduled.items()
            if entry["queue"] == queue and entry["due_at"] <= now
        ]
        for task_id in ready_ids:
            entry = self._scheduled[task_id]
            task = entry["task"]
            blackout = self._active_blackout(task, now)
            if blackout:
                self._record_blackout(task, queue, blackout)
                entry["due_at"] = blackout[1]
                continue
            self._scheduled.pop(task_id, None)
            # Re-enqueue without generating a new ID or modifying limits manually since schedule() hasn't claimed capacity.
            # However, original PR 181 doesn't use `self.enqueue`. It uses `self._queue_task(task, queue, entry["priority"])`.
            # We must maintain integration with our capacity limits. So we will call enqueue directly with the task which has an id.
            self.enqueue(task, queue, priority=entry["priority"])

    async def dequeue(
        self,
        queue: str = "default",
        timeout: float = 1.0,
    ) -> Optional[Dict]:
        now = self._time_fn()
        self._promote_ready_scheduled(queue, now)

        if queue in self._queues and len(self._queues[queue]) > 0:
            deferred: List[Dict] = []
            while len(self._queues[queue]) > 0:
                task = self._queues[queue].pop()
                if not task:
                    continue
                blackout = self._active_blackout(task, now)
                if blackout:
                    self._record_blackout(task, queue, blackout)
                    deferred.append(task)
                    continue

                # Found an eligible task. Push deferred tasks back.
                for deferred_task in deferred:
                    self._push_queued_task(
                        deferred_task,
                        queue,
                        deferred_task.get("priority", 0),
                    )
                self._in_flight[task["id"]] = task
                self._task_queues[task["id"]] = queue
                return task

            # Restore deferred tasks if no eligible task was found
            for deferred_task in deferred:
                self._push_queued_task(
                    deferred_task,
                    queue,
                    deferred_task.get("priority", 0),
                )
        return None

    def complete(self, task_id: str) -> bool:
        task = self._in_flight.pop(task_id, None)
        if task is None:
            return False
        
        if not self._is_already_terminal(task_id):
            self._set_terminal_outcome(task_id, RunState.TERMINAL_SUCCESS.value)

        queue = self._task_queues.pop(task_id, task.get("queue", "default"))
        self._release_capacity(queue, task_id)
        self._record_audit("task_completed", task_id, queue)
        metrics.increment("scheduler.task.completed")
        return True

    def fail(self, task_id: str, queue: str = "default") -> bool:
        task = self._in_flight.get(task_id)
        if not task:
            if self._is_already_terminal(task_id) and self._terminal_outcomes.get(task_id) == RunState.TERMINAL_FAILURE.value:
                self._record_audit("dead_letter_idempotent", task_id, queue)
            return False

        task["retries"] += 1
        task["run_state"] = RunState.IN_PROGRESS.name
        original_queue = self._task_queues.get(task_id, queue)

        if task["retries"] >= self._max_retries:
            task = self._in_flight.pop(task_id)
            if not self._is_already_terminal(task_id):
                self._set_terminal_outcome(task_id, RunState.TERMINAL_FAILURE.value)
            
            if queue != original_queue and queue != "default":
                try:
                    self._reserve_capacity(queue, task_id)
                    self._push_queued_task(task, queue, priority=task.get("priority", 0))
                except Exception as exc:
                    self._release_capacity(queue, task_id)
                    self._record_audit("dead_letter_write_failed", task_id, queue, type(exc).__name__)
                    self._terminal_outcomes.pop(task_id, None)
                    task["retries"] -= 1
                    self._in_flight[task_id] = task
                    raise
                self._task_queues[task_id] = queue
            
            self._task_queues.pop(task_id, None)
            self._release_capacity(original_queue, task_id)
            self._record_audit("task_failed_terminal", task_id, original_queue)
            return False

        task = self._in_flight.pop(task_id)
        transfer_reserved = False
        try:
            if queue != original_queue:
                self._reserve_capacity(queue, task_id)
                transfer_reserved = True
            self._push_queued_task(
                task,
                queue,
                task.get("priority", 0),
            )
        except Exception as exc:
            if transfer_reserved:
                self._release_capacity(queue, task_id)
            task["retries"] -= 1
            self._in_flight[task_id] = task
            self._task_queues[task_id] = original_queue
            self._record_audit(
                "retry_enqueue_rolled_back",
                task_id,
                queue,
                type(exc).__name__,
            )
            metrics.increment("scheduler.enqueue.rollback")
            raise
            
        if transfer_reserved:
            self._release_capacity(original_queue, task_id)
        self._task_queues[task_id] = queue
        self._record_audit("retry_enqueued", task_id, queue)
        metrics.increment("scheduler.retry.enqueued")
        return True
"""

with open("src/orchestrator/scheduler.py", "w") as f:
    f.write(new_code + "\n" + tail)
