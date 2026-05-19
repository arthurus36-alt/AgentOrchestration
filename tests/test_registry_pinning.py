import pytest
import asyncio
from src.agent.registry import AgentRegistry, AgentStatus, ResolutionError
from src.orchestrator.engine import OrchestrationEngine

@pytest.mark.asyncio
async def test_registry_pinning_detects_stale_update():
    engine = OrchestrationEngine()
    agent_id = engine.registry.register("test_agent", "dummy.type", {})
    
    task = {"id": "task_1", "target_agent": agent_id}
    
    # Hook to modify registry mid-run
    async def mid_run_modifier(hook_task):
        engine.registry.update_status(agent_id, AgentStatus.STOPPED)
        
    engine.register_hook("pre_execute", mid_run_modifier)
    
    # Run the task - should catch ResolutionError internally and route to on_error
    error_caught = []
    async def error_hook(hook_task, err):
        error_caught.append(err)
        
    engine.register_hook("on_error", error_hook)
    
    await engine._execute_task(task)
    
    assert len(error_caught) > 0
    assert isinstance(error_caught[0], ResolutionError)
    assert "became stale mid-run" in str(error_caught[0])

@pytest.mark.asyncio
async def test_registry_pinning_detects_deregister():
    engine = OrchestrationEngine()
    agent_id = engine.registry.register("test_agent", "dummy.type", {})
    
    task = {"id": "task_1", "target_agent": agent_id}
    
    # Hook to deregister mid-run
    async def mid_run_modifier(hook_task):
        engine.registry.deregister(agent_id)
        
    engine.register_hook("pre_execute", mid_run_modifier)
    
    error_caught = []
    async def error_hook(hook_task, err):
        error_caught.append(err)
        
    engine.register_hook("on_error", error_hook)
    
    await engine._execute_task(task)
    
    assert len(error_caught) > 0
    assert isinstance(error_caught[0], ValueError) # Failed before update_status in pre_execute

@pytest.mark.asyncio
async def test_registry_pinning_success_path():
    engine = OrchestrationEngine()
    agent_id = engine.registry.register("test_agent", "dummy.type", {})
    
    task = {"id": "task_1", "target_agent": agent_id}
    
    success_caught = []
    async def success_hook(hook_task, res):
        success_caught.append(res)
        
    engine.register_hook("post_execute", success_hook)
    
    await engine._execute_task(task)
    
    assert len(success_caught) == 1
    assert success_caught[0]["status"] == "completed"
