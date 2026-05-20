import re

with open("src/api/routes.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"API route definitions.\"\"\"

from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import copy
import time

from src.agent import AgentRegistry, AgentStatus
from src.orchestrator import TaskScheduler

router = APIRouter()
registry = AgentRegistry()
scheduler = TaskScheduler()

def get_current_context():
    return {"workspace_id": "ws_123", "role": "admin"}

class RunSearchService:
    @staticmethod
    def search_runs(query: str, workspace_id: str, role: str) -> List[Dict]:
        if not workspace_id:
            raise ValueError("Workspace ID is required for search indexing queries")
            
        mock_db = [
            {"id": "run_1", "workspace_id": "ws_123", "data": "test run"},
            {"id": "run_2", "workspace_id": "ws_456", "data": "other tenant run"}
        ]
        
        return [r for r in mock_db if r["workspace_id"] == workspace_id]

@router.get("/search/runs")
async def search_runs(query: str, context: Dict = Depends(get_current_context)):
    try:
        results = RunSearchService.search_runs(
            query=query, 
            workspace_id=context.get("workspace_id"),
            role=context.get("role")
        )
        return {"results": results}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/agents")
async def list_agents(status: Optional[str] = None, group: Optional[str] = None):
    status_filter = AgentStatus(status) if status else None
    return {"agents": registry.list(status=status_filter, group=group)}

@router.post("/agents")
async def register_agent(name: str, agent_type: str, config: Optional[Dict] = None):
    agent_id = registry.register(name, agent_type, config)
    return {"agent_id": agent_id, "status": "registered"}

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not registry.delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}

@router.post("/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    if not registry.update_status(agent_id, AgentStatus.RUNNING):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "started"}

@router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if not registry.update_status(agent_id, AgentStatus.PAUSED):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "stopped"}

@router.get("/agents/count")
async def agent_count():
    return {"count": registry.count()}

@router.get("/dlq/messages")
async def list_dlq_messages(
    reveal_payload: bool = False,
    operator: str = Header(None, alias="X-Operator"),
):
    messages = []
    dlq_tasks = []
    if hasattr(scheduler, "_queues") and "dead" in scheduler._queues:
        for item in getattr(scheduler._queues["dead"], "_queue", []):
            dlq_tasks.append(item[2])
            
    for task in dlq_tasks:
        safe_task = dict(task)
        if reveal_payload:
            if not operator:
                raise HTTPException(status_code=403, detail="elevated access requires operator")
            if hasattr(scheduler, "_record_audit"):
                scheduler._record_audit("dlq_raw_payload_accessed", task.get("id"), "dead", operator)
        else:
            if "payload" in safe_task:
                safe_task["payload"] = "[REDACTED]"
        messages.append(safe_task)
    return {"messages": messages}
"""

with open("src/api/routes.py", "w") as f:
    f.write(new_code + "\n" + tail)
