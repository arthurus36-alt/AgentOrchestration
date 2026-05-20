import re

with open("src/api/routes.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"API route definitions.\"\"\"

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional

from src.agent import AgentRegistry, AgentStatus
from src.api.agent_config import AgentConfigUpdateError, update_agent_config

router = APIRouter()
registry = AgentRegistry()

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

@router.patch("/agents/{agent_id}/config")
async def patch_agent_config(
    agent_id: str,
    payload: Dict,
    if_match: Optional[str] = Header(None, alias="If-Match"),
):
    try:
        result = update_agent_config(registry, agent_id, payload, if_match)
    except AgentConfigUpdateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        
    response = JSONResponse(
        content={"agent_id": result["agent_id"], "config": result["config"]},
        status_code=200,
    )
    response.headers["ETag"] = result["etag"]
    return response

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
"""

with open("src/api/routes.py", "w") as f:
    f.write(new_code + "\n" + tail)
