import pytest
import asyncio
from src.orchestrator.scheduler import TaskScheduler

@pytest.mark.asyncio
async def test_terminal_task_cannot_be_retried():
    scheduler = TaskScheduler()
    
    # 1. Enqueue task
    task = {"id": "test_task_1"}
    scheduler.enqueue(task)
    
    # 2. Dequeue
    dequeued = await scheduler.dequeue()
    assert dequeued["id"] == "test_task_1"
    
    # 3. Mark terminal
    scheduler.complete("test_task_1")
    
    # 4. Attempt to retry or enqueue the terminal task
    with pytest.raises(ValueError) as excinfo:
        scheduler.enqueue({"id": "test_task_1"})
        
    assert "terminal state" in str(excinfo.value)
    
    # Verify it doesn't appear in dequeue
    assert await scheduler.dequeue(timeout=0.1) is None

@pytest.mark.asyncio
async def test_scheduler_max_retries_reaches_terminal():
    scheduler = TaskScheduler()
    
    # Task with max 1 retry
    task = {"id": "retry_task", "max_retries": 1}
    scheduler.enqueue(task)
    
    # Dequeue attempt 1
    t1 = await scheduler.dequeue()
    assert t1["attempts"] == 1
    
    # Fail - should retry
    assert scheduler.fail("retry_task") == True
    
    # Dequeue attempt 2
    t2 = await scheduler.dequeue()
    assert t2["attempts"] == 2
    
    # Fail - should exceed max_retries and become terminal
    assert scheduler.fail("retry_task") == True
    
    # Queue should be empty and task terminal
    assert await scheduler.dequeue(timeout=0.1) is None
    
    with pytest.raises(ValueError):
        scheduler.enqueue({"id": "retry_task"})
