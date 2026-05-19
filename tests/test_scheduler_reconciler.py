import pytest
import asyncio
from src.orchestrator.scheduler import TaskScheduler

class TestTaskSchedulerReconciler:
    def setup_method(self):
        self.scheduler = TaskScheduler()

    def test_reconcile_guard_revision_mismatch(self):
        task_id = self.scheduler.enqueue({"type": "test"})
        task = asyncio.run(self.scheduler.dequeue())
        
        with pytest.raises(ValueError, match="Revision mismatch"):
            self.scheduler.complete(task_id, revision=999)

    def test_reconcile_guard_lifecycle_invalid_transition(self):
        task_id = self.scheduler.enqueue({"type": "test"})
        task = asyncio.run(self.scheduler.dequeue())
        
        # Manually complete the task
        self.scheduler.complete(task_id)
        
        # Try to fail it after it's already completed - should raise error
        # but complete() popped it from in_flight.
        # Wait, if it is popped, fail() will just return False.
        # Let's test a lifecycle mismatch by trying to enqueue a dispatched task.
        with pytest.raises(ValueError, match="Invalid lifecycle transition"):
            self.scheduler.enqueue(task, revision=-1)

    def test_partial_dispatch_failure(self):
        # Simulate partial dispatch failure where the task is still in dispatched state
        # but someone tries to fail it with a wrong revision
        task_id = self.scheduler.enqueue({"type": "test"})
        task = asyncio.run(self.scheduler.dequeue())
        
        with pytest.raises(ValueError, match="Revision mismatch"):
            self.scheduler.fail(task_id, revision=999)
            
        assert self.scheduler.complete(task_id) is True

    def test_schedule_then_enqueue(self):
        task_id = self.scheduler.schedule({"type": "test"}, 0.01)
        import time
        time.sleep(0.02)
        task = asyncio.run(self.scheduler.dequeue())
        assert task is not None
        assert self.scheduler._lifecycle[task_id] == "dispatched"
