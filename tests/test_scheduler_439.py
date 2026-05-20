import pytest
import asyncio
from src.orchestrator.scheduler import TaskScheduler

def test_task_finalization_transaction():
    scheduler = TaskScheduler()
    
    # Enqueue and dequeue a task
    task_id = scheduler.enqueue({"type": "test_finalization"})
    task = asyncio.run(scheduler.dequeue())
    assert task is not None
    assert task["id"] == task_id
    
    # Complete the task with an artifact manifest
    artifacts = ["s3://bucket/art1.json", "s3://bucket/art2.json"]
    success = scheduler.complete(task_id, artifacts=artifacts)
    assert success is True
    assert task["status"] == "completed"
    assert task["artifact_manifest"] == artifacts

def test_task_finalization_transaction_failure():
    scheduler = TaskScheduler()
    task_id = scheduler.enqueue({"type": "test_failure"})
    task = asyncio.run(scheduler.dequeue())
    
    # If a failure happens during manifest gathering or whatever, it shouldn't be popped or marked completed
    success = scheduler.complete("invalid_task_id")
    assert success is False
    assert "status" not in task
    assert "artifact_manifest" not in task
    assert task_id in scheduler._in_flight
