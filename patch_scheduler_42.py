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
from typing import Any, Dict, List, Optional, Set
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
    def __init__(self, queue_capacities: Optional[Dict[str, int]] = None):
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, Dict] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._task_queues: Dict[str, str] = {}
        self._capacity_claims: Dict[str, Set[str]] = {}
        self._queue_capacities = queue_capacities or {}
        self._audit_log: List[Dict[str, Any]] = []
        self._terminal_outcomes: Dict[str, str] = {}
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
            "timestamp": time.time(),
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
        queued_task["enqueued_at"] = time.time()
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
            "due_at": time.time() + delay,
            "queue": queue,
            "priority": priority
        }
        return task_id

    async def dequeue(
        self,
        queue: str = "default",
        timeout: float = 1.0,
    ) -> Optional[Dict]:
        now = time.time()
        expired = [tid for tid, t in self._scheduled.items() if t["due_at"] <= now]
        for tid in expired:
            entry = self._scheduled.pop(tid)
            if entry["task"]:
                self.enqueue(entry["task"], entry["queue"], priority=entry["priority"])

        if queue in self._queues and len(self._queues[queue]) > 0:
            task = self._queues[queue].pop()
            if task:
                self._in_flight[task["id"]] = task
                self._task_queues[task["id"]] = queue
                return task
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
        task = self._in_flight.pop(task_id, None)
        if task:
            task["retries"] += 1
            task["run_state"] = RunState.IN_PROGRESS.name
            if task["retries"] >= self._max_retries:
                if not self._is_already_terminal(task_id):
                    self._set_terminal_outcome(task_id, RunState.TERMINAL_FAILURE.value)
                original_queue = self._task_queues.pop(task_id, queue)
                self._release_capacity(original_queue, task_id)
                self._record_audit("task_failed_terminal", task_id, original_queue)
                return False

            original_queue = self._task_queues.get(task_id, queue)
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
        return False
"""

with open("src/orchestrator/scheduler.py", "w") as f:
    f.write(new_code + "\n" + tail)
