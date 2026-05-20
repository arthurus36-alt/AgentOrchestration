import re

with open("src/agent/registry.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Agent Registry — Manages agent lifecycle and metadata.\"\"\"

import json
import time
import uuid
import os
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

class ResolutionError(Exception):
    pass

class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"

class RegistryError(Exception):
    pass

class AgentRegistry:
    def __init__(self, storage_backend: str = "memory"):
        self.storage_backend = storage_backend
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, List[str]] = {}
        self._version: int = 1
        self._pinned_handlers: Dict[str, int] = {}
        self._audit_records: List[Dict[str, Any]] = []
        self.metadata_root = Path("/tmp/ao_metadata")
        self.metadata_root.mkdir(parents=True, exist_ok=True)

    def _validate_handler_name(self, name: str) -> None:
        if ".." in name or "/" in name or "\\\\" in name:
            raise RegistryError(f"Invalid handler name: path traversal attempt detected in '{name}'")
            
    def _build_artifact_path(self, agent_id: str, handler_name: str) -> Path:
        self._validate_handler_name(handler_name)
        
        agent_dir = self.metadata_root / agent_id
        agent_dir.mkdir(exist_ok=True)
        
        artifact_path = agent_dir / f"{handler_name}.json"
        
        try:
            artifact_path.resolve().relative_to(self.metadata_root.resolve())
        except ValueError:
            raise RegistryError("Path traversal violation: constructed path escapes metadata root")
            
        return artifact_path

    def save_plugin_metadata(self, agent_id: str, handler_name: str, data: Dict) -> bool:
        if agent_id not in self._agents:
            return False
            
        try:
            path = self._build_artifact_path(agent_id, handler_name)
            with open(path, "w") as f:
                json.dump(data, f)
            return True
        except RegistryError:
            raise

    def load_plugin_metadata(self, agent_id: str, handler_name: str) -> Optional[Dict]:
        if agent_id not in self._agents:
            return None
            
        try:
            path = self._build_artifact_path(agent_id, handler_name)
            if not path.exists():
                return None
                
            with open(path, "r") as f:
                return json.load(f)
        except RegistryError:
            raise

    def _record_audit(self, event: str, agent_id: str, reason: str = "") -> None:
        self._audit_records.append({
            "event": event,
            "agent_id": agent_id,
            "reason": reason,
            "timestamp": time.time(),
        })

    def audit_records(self) -> List[Dict[str, Any]]:
        return list(self._audit_records)

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

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def resolve(self, agent_id: str, attempt: str) -> Dict[str, Any]:
        agent = self.get(agent_id)
        if not agent:
            self._record_audit("resolution_rejected", agent_id, "agent_not_found")
            raise ResolutionError(f"Agent {agent_id} not found")
            
        pin_key = f"{agent_id}::{attempt}"
        pinned_version = self._pinned_handlers.get(pin_key)

        if pinned_version is not None:
            if pinned_version != agent.get("registry_version"):
                self._record_audit("resolution_rejected", agent_id, "stale_registry_version")
                raise ResolutionError(f"Agent {agent_id} registry version changed during attempt")
        else:
            self._pinned_handlers[pin_key] = agent.get("registry_version")
            self._record_audit("handler_pinned", agent_id, f"attempt_{attempt}")

        return dict(agent)

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
            
        agent_dir = self.metadata_root / agent_id
        if agent_dir.exists():
            import shutil
            shutil.rmtree(agent_dir, ignore_errors=True)
            
        return True

    def count(self) -> int:
        return len(self._agents)
"""

with open("src/agent/registry.py", "w") as f:
    f.write(new_code + "\n" + tail)
