import pytest
import asyncio
import time
from src.orchestrator.scheduler import TaskScheduler

def test_extend_visibility_timeout():
    scheduler = TaskScheduler()
    task_id = scheduler.enqueue({"type": "test", "payload": {}})
    
    # Dequeue the task so it's in flight
    task = asyncio.run(scheduler.dequeue())
    assert task is not None
    assert task["id"] == task_id
    
    # Test extending visibility
    success = scheduler.extend_visibility_timeout(task_id, 600)
    assert success is True
    assert scheduler._in_flight[task_id]["visibility_timeout"] >= time.time() + 500

    # Ensure task is not dequeued while visibility is extended
    task2 = asyncio.run(scheduler.dequeue())
    assert task2 is None

def test_visibility_timeout_expiration():
    scheduler = TaskScheduler()
    task_id = scheduler.enqueue({"type": "test", "payload": {}})
    
    task = asyncio.run(scheduler.dequeue())
    assert task is not None
    
    # Force expiration
    scheduler._in_flight[task_id]["visibility_timeout"] = time.time() - 1
    
    # Next dequeue should pick up the expired task
    task2 = asyncio.run(scheduler.dequeue())
    assert task2 is not None
    assert task2["id"] == task_id
