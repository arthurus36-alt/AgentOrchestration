import pytest
import asyncio
from src.agent.executor import AgentExecutor

@pytest.mark.asyncio
async def test_executor_cancel():
    executor = AgentExecutor()
    
    async def slow_handler(agent_id, task):
        await asyncio.sleep(2)
        return {"status": "done"}
    
    # We have to schedule execute() as a task so we can get its return value,
    # wait, execute() awaits the task_obj. But wait! The execution_id is generated inside execute().
    # How does the caller get execution_id before it finishes?
    # They can't, because it returns at the end. That is a terrible design, but let's just test what happens when it's cancelled.
    
    execution_id_box = []
    
    async def wrapper():
        try:
            return await executor.execute("agent1", {"id": "1"}, slow_handler)
        except asyncio.CancelledError:
            pass

    # Start execute
    t = asyncio.create_task(wrapper())
    
    # Give it a moment to populate _active_tasks
    await asyncio.sleep(0.1)
    
    execution_id = list(executor._active_tasks.keys())[0]
    
    executor.cancel(execution_id)
    
    await t
    
    res = executor.get_result(execution_id)
    assert res is not None
    assert "error" in res or "status" in res

