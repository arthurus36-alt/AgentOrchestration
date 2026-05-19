"""Agent Sandbox — Isolated execution environment for agents."""

import os
import tempfile
import resource
from typing import Dict, Optional
from pathlib import Path


class ResourceLimitsError(Exception):
    """Raised when resource limits are invalid."""
    pass


class ResourceLimits:
    def __init__(self, cpu_time: int = 60, memory_mb: int = 512, disk_mb: int = 100):
        # Fix for #5: Validate that resource limits are positive numeric values
        try:
            self.cpu_time = int(cpu_time)
            self.memory_mb = int(memory_mb)
            self.disk_mb = int(disk_mb)
        except (ValueError, TypeError):
            raise ResourceLimitsError("Resource limits must be numeric values")
            
        if self.cpu_time <= 0:
            raise ResourceLimitsError(f"cpu_time must be positive, got {self.cpu_time}")
        if self.memory_mb <= 0:
            raise ResourceLimitsError(f"memory_mb must be positive, got {self.memory_mb}")
        if self.disk_mb <= 0:
            raise ResourceLimitsError(f"disk_mb must be positive, got {self.disk_mb}")


class AgentSandbox:
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path or tempfile.mkdtemp(prefix="ao_sandbox_"))
        self._sandboxes: Dict[str, Path] = {}

    def create(self, agent_id: str, limits: Optional[ResourceLimits] = None) -> Path:
        sandbox_path = self.base_path / agent_id
        sandbox_path.mkdir(parents=True, exist_ok=True)
        self._sandboxes[agent_id] = sandbox_path
        return sandbox_path

    def destroy(self, agent_id: str) -> bool:
        sandbox = self._sandboxes.pop(agent_id, None)
        if sandbox and sandbox.exists():
            import shutil
            shutil.rmtree(sandbox, ignore_errors=True)
            return True
        return False

    def get_path(self, agent_id: str) -> Optional[Path]:
        return self._sandboxes.get(agent_id)

    def apply_limits(self, agent_id: str, limits: ResourceLimits) -> None:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_time, limits.cpu_time))
            mem_bytes = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, resource.error) as e:
            pass

    def cleanup_all(self) -> None:
        for agent_id in list(self._sandboxes.keys()):
            self.destroy(agent_id)
