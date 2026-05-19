"""Agent Registry — Manages agent lifecycle and metadata."""

import json
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

class ResolutionError(Exception):
    """Raised when a pinned handler is deregistered or becomes stale."""
    pass

class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentRegistry:
    def __init__(self, storage_backend: str = "memory"):
        self.storage_backend = storage_backend
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, List[str]] = {}
        self._version: int = 1

    def register(self, name: str, agent_type: str, config: Optional[Dict] = None) -> str:
        self._version += 1
        agent_id = str(uuid.uuid4())
        timestamp = time.time()
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "type": agent_type,
            "status": AgentStatus.PENDING.value,
            "config": config or {},
            "created_at": timestamp,
            "updated_at": timestamp,
            "version": "1.0.0",
            "registry_version": self._version,
            "metrics": {"tasks_completed": 0, "errors": 0, "uptime": 0},
        }
        group = agent_type.split(".")[0]
        if group not in self._index:
            self._index[group] = []
        self._index[group].append(agent_id)
        return agent_id
        
    def deregister(self, agent_id: str) -> bool:
        self._version += 1
        return self.delete(agent_id)

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)
        
    def resolve_pinned(self, agent_id: str, expected_version: int) -> Dict[str, Any]:
        agent = self.get(agent_id)
        if not agent:
            raise ResolutionError(f"Agent {agent_id} has been deregistered mid-run")
        if agent["registry_version"] != expected_version:
            raise ResolutionError(f"Agent {agent_id} configuration became stale mid-run")
        return agent

    def list(self, status: Optional[AgentStatus] = None, group: Optional[str] = None) -> List[Dict[str, Any]]:
        agents = self._agents.values()
        if status:
            agents = [a for a in agents if a["status"] == status.value]
        if group:
            agent_ids = self._index.get(group, [])
            agents = [a for a in agents if a["id"] in agent_ids]
        return list(agents)

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        if agent_id not in self._agents:
            return False
        self._version += 1
        self._agents[agent_id]["status"] = status.value
        self._agents[agent_id]["updated_at"] = time.time()
        self._agents[agent_id]["registry_version"] = self._version
        return True

    def delete(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        agent = self._agents.pop(agent_id)
        group = agent["type"].split(".")[0]
        if group in self._index and agent_id in self._index[group]:
            self._index[group].remove(agent_id)
        return True

    def count(self) -> int:
        return len(self._agents)
