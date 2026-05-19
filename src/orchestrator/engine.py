"""Orchestration Engine — Core execution and coordination logic."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from src.agent import AgentRegistry, AgentStatus
from src.agent.registry import ResolutionError
from src.orchestrator.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


class OrchestrationEngine:
    def __init__(self, max_workers: int = 10, agent_timeout: int = 300):
        self.registry = AgentRegistry()
        self.scheduler = TaskScheduler()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.agent_timeout = agent_timeout
        self._running = False
        self._hooks: Dict[str, List[Callable]] = {
            "pre_execute": [],
            "post_execute": [],
            "on_error": [],
            "on_complete": [],
        }

    def register_hook(self, event: str, callback: Callable) -> None:
        if event in self._hooks:
            self._hooks[event].append(callback)

    async def start(self) -> None:
        self._running = True
        logger.info("Orchestration engine started")
        while self._running:
            task = await self.scheduler.dequeue()
            if task:
                asyncio.create_task(self._execute_task(task))
            await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False
        logger.info("Orchestration engine stopped")

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        task_id = task["id"]
        agent_id = task["target_agent"]
        logger.info(f"Executing task {task_id} on agent {agent_id}")

        for hook in self._hooks["pre_execute"]:
            await hook(task)

        try:
            # Fix for #8: Get the agent and its version, explicitly pinning it
            agent = self.registry.get(agent_id)
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            expected_version = agent.get("registry_version", 0)

            self.registry.update_status(agent_id, AgentStatus.RUNNING)
            
            # Re-resolve pinned to detect if deregistered or stale during state change
            pinned_agent = self.registry.resolve_pinned(agent_id, expected_version + 1) # +1 because update_status increments

            result = await asyncio.wait_for(
                self._run_agent_task(pinned_agent, task),
                timeout=self.agent_timeout,
            )
            
            # Re-resolve again before committing final state to ensure mid-run safety
            pinned_agent = self.registry.resolve_pinned(agent_id, expected_version + 1)
            self.registry.update_status(agent_id, AgentStatus.PAUSED)

            for hook in self._hooks["post_execute"]:
                await hook(task, result)

            logger.info(f"Task {task_id} completed successfully")

        except ResolutionError as e:
            logger.error(f"Task {task_id} safely aborted due to registry resolution violation: {e}")
            for hook in self._hooks["on_error"]:
                await hook(task, e)
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            for hook in self._hooks["on_error"]:
                await hook(task, e)

    async def _run_agent_task(self, agent: Dict, task: Dict) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._execute_in_thread,
            agent,
            task,
        )

    def _execute_in_thread(self, agent: Dict, task: Dict) -> Any:
        # Simulate some delay to allow mid-run changes during tests
        import time
        time.sleep(0.01)
        return {"status": "completed", "output": f"Task {task['id']} processed by {agent['name']}"}
