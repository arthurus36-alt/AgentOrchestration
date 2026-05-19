"""Task Scheduler — Priority-based task queuing and dispatch."""

import asyncio
import heapq
import time
from typing import Any, Dict, Optional, Set
from uuid import uuid4


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
        self._delayed: list = []
        self._in_flight: Dict[str, Dict] = {}
        # Fix for #42: Track terminal states durably to prevent late retries from entering the loop
        self._terminal_tasks: Set[str] = set()

    def enqueue(self, task: Dict, queue: str = "default", priority: int = 0) -> str:
        if "id" not in task:
            task["id"] = str(uuid4())
            
        # Fix for #42: Reject enqueue if the task is already terminal
        if task["id"] in self._terminal_tasks:
            raise ValueError(f"Task {task['id']} is in a terminal state and cannot be retried or enqueued.")

        if queue not in self._queues:
            self._queues[queue] = PriorityQueue()
            
        # If it's a retry, increment its attempt counter
        task["attempts"] = task.get("attempts", 0) + 1
        
        self._queues[queue].push(task, priority)
        return task["id"]

    def schedule(self, task: Dict, delay: float, queue: str = "default", priority: int = 0) -> str:
        if "id" not in task:
            task["id"] = str(uuid4())
            
        # Fix for #42: Guard delayed scheduling too
        if task["id"] in self._terminal_tasks:
            raise ValueError(f"Task {task['id']} is in a terminal state and cannot be scheduled.")
            
        execute_at = time.time() + delay
        heapq.heappush(self._delayed, (execute_at, queue, priority, task))
        return task["id"]

    async def dequeue(self, queue: str = "default", timeout: float = 1.0) -> Optional[Dict]:
        start_time = time.time()
        
        while True:
            # Process delayed tasks
            now = time.time()
            while self._delayed and self._delayed[0][0] <= now:
                _, target_queue, priority, task = heapq.heappop(self._delayed)
                if task["id"] not in self._terminal_tasks:
                    self.enqueue(task, target_queue, priority)
                
            if queue in self._queues and len(self._queues[queue]) > 0:
                task = self._queues[queue].pop()
                if task and task["id"] not in self._terminal_tasks:
                    self._in_flight[task["id"]] = task
                    return task
                    
            if time.time() - start_time >= timeout:
                return None
                
            await asyncio.sleep(0.1)

    def complete(self, task_id: str) -> bool:
        if task_id in self._in_flight:
            self._in_flight.pop(task_id)
            self._terminal_tasks.add(task_id)
            return True
        return False

    def fail(self, task_id: str, queue: str = "default") -> bool:
        task = self._in_flight.pop(task_id, None)
        if task:
            max_retries = task.get("max_retries", 0)
            if task.get("attempts", 1) <= max_retries:
                # Can retry
                try:
                    self.enqueue(task, queue)
                except ValueError:
                    return False
            else:
                # Terminal failure
                self._terminal_tasks.add(task_id)
            return True
        return False
