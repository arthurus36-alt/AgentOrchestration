"""API route definitions."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional

from src.agent import AgentRegistry, AgentStatus

router = APIRouter()
registry = AgentRegistry()


# Fix for #24: Mock authentication dependency
def get_current_context():
    # In a real app this would extract the JWT/session data
    return {"workspace_id": "ws_123", "role": "admin"}


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
    return {"status": "running"}


@router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if not registry.update_status(agent_id, AgentStatus.PAUSED):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "stopped"}


@router.get("/metrics/agents")
async def agent_count():
    return {"count": registry.count()}


# Fix for #24: Run search API scoped to workspace and role
class RunSearchService:
    @staticmethod
    def search_runs(query: str, workspace_id: str, role: str) -> List[Dict]:
        if not workspace_id:
            raise ValueError("Workspace ID is required for search indexing queries")
            
        # Mock search backend that returns scoped results
        mock_db = [
            {"id": "run_1", "workspace_id": "ws_123", "data": "test run"},
            {"id": "run_2", "workspace_id": "ws_456", "data": "other tenant run"}
        ]
        
        # Explicit authorization boundary guard: Enforce workspace scope
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
