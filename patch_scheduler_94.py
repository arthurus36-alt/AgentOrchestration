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
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


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
    def __init__(self):
        self._queues: Dict[str, PriorityQueue] = {}
        self._scheduled: Dict[str, Dict] = {}
        self._in_flight: Dict[str, Dict] = {}
        self._lifecycle: Dict[str, str] = {}
        self._revisions: Dict[str, int] = {}
        self._tasks: Dict[str, Dict] = {}
        self._audit_records: list = []
        self._max_retries = 3

    def _bump_revision(self, task_id: str) -> None:
        self._revisions[task_id] = self._revisions.get(task_id, 0) + 1

    def _check_revision(self, task_id: str, expected: int) -> None:
        if task_id in self._revisions and self._revisions[task_id] != expected:
            actual = self._revisions[task_id]
            logger.warning(f"Reconcile guard rejected transition for task {task_id}: revision mismatch (expected {expected}, actual {actual})")
            raise ValueError(f"Revision mismatch for task {task_id}: expected {expected}, got {actual}")

    def _check_lifecycle(self, task_id: str, valid_states: list) -> None:
        state = self._lifecycle.get(task_id)
        if state not in valid_states:
            logger.warning(f"Reconcile guard rejected transition for task {task_id}: invalid lifecycle {state}")
            raise ValueError(f"Invalid lifecycle transition for task {task_id}: current state is {state}, expected one of {valid_states}")

    def enqueue(self, task: Dict, queue: str = "default", priority: int = 0, revision: int = -1) -> str:
        if "id" not in task:
            task["id"] = str(uuid4())
        task_id = task["id"]
        
        if revision != -1:
            self._check_revision(task_id, revision)
            
        if task_id in self._lifecycle:
            self._check_lifecycle(task_id, ["scheduled", "dispatched", "failed"])

        if "enqueued_at" not in task:
            task["enqueued_at"] = time.time()
        if "retries" not in task:
            task["retries"] = 0

        self._lifecycle[task_id] = "queued"
        self._bump_revision(task_id)
        self._tasks[task_id] = task

        if queue not in self._queues:
            self._queues[queue] = PriorityQueue()
        self._queues[queue].push(task, priority)
        return task_id

    def schedule(self, task: Dict, delay: float, queue: str = "default", priority: int = 0) -> str:
        if "id" not in task:
            task["id"] = str(uuid4())
        task_id = task["id"]
        
        if task_id in self._lifecycle:
            self._check_lifecycle(task_id, ["queued", "failed"])
            
        self._lifecycle[task_id] = "scheduled"
        self._bump_revision(task_id)
        self._tasks[task_id] = task
        
        self._scheduled[task_id] = {"due_at": time.time() + delay, "queue": queue, "priority": priority}
        return task_id

    def reschedule(
        self,
        task_id: str,
        delay: float,
        queue: Optional[str] = None,
        priority: Optional[int] = None,
        expected_revision: Optional[int] = None,
    ) -> bool:
        if self._lifecycle.get(task_id) != "scheduled":
            self._audit_records.append({"decision": "reject", "reason": "task_not_scheduled", "task_id": task_id})
            return False

        if expected_revision is not None and self._revisions.get(task_id, 0) != expected_revision:
            self._audit_records.append({"decision": "reject", "reason": "stale_revision", "task_id": task_id})
            return False

        next_queue = queue or self._scheduled.get(task_id, {}).get("queue", "default")
        next_priority = priority if priority is not None else self._scheduled.get(task_id, {}).get("priority", 0)

        self._bump_revision(task_id)
        self._scheduled[task_id] = {
            "due_at": time.time() + delay,
            "queue": next_queue,
            "priority": next_priority
        }
        self._audit_records.append({"decision": "accept", "reason": "rescheduled", "task_id": task_id})
        return True

    async def dequeue(self, queue: str = "default", timeout: float = 1.0) -> Optional[Dict]:
        now = time.time()
        expired = [tid for tid, t in self._scheduled.items() if t["due_at"] <= now]
        for tid in expired:
            entry = self._scheduled.pop(tid)
            task = self._tasks.get(tid)
            if task and self._lifecycle.get(tid) == "scheduled":
                self.enqueue(task, entry["queue"], priority=entry["priority"], revision=self._revisions.get(tid, 0))

        if queue in self._queues and len(self._queues[queue]) > 0:
            task = self._queues[queue].pop()
            if task:
                task_id = task["id"]
                self._check_lifecycle(task_id, ["queued"])
                self._lifecycle[task_id] = "dispatched"
                self._in_flight[task_id] = task
                task["lifecycle"] = "in_flight"
                self._bump_revision(task_id)
                return task
        return None

    def complete(self, task_id: str, revision: int = -1) -> bool:
        if revision != -1:
            self._check_revision(task_id, revision)
            
        task = self._in_flight.pop(task_id, None)
        if task:
            self._check_lifecycle(task_id, ["dispatched"])
            self._lifecycle[task_id] = "completed"
            self._bump_revision(task_id)
            return True
        return False

    def fail(self, task_id: str, queue: str = "default", revision: int = -1) -> bool:
        if revision != -1:
            self._check_revision(task_id, revision)
            
        task = self._in_flight.pop(task_id, None)
        if task:
            self._check_lifecycle(task_id, ["dispatched"])
            task["retries"] += 1
            if task["retries"] < self._max_retries:
                self._lifecycle[task_id] = "failed"
                self._bump_revision(task_id)
                self.enqueue(task, queue, priority=task.get("priority", 0), revision=self._revisions.get(task_id, 0))
                return True
            else:
                self._lifecycle[task_id] = "failed"
                self._bump_revision(task_id)
        return False
        
    def audit_records(self) -> list:
        return self._audit_records
"""

with open("src/orchestrator/scheduler.py", "w") as f:
    f.write(new_code + "\n" + tail)
