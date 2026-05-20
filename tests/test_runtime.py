import pytest
from src.agent.runtime import AgentRuntime, RuntimeState

def test_start_protects_reserved_env():
    runtime = AgentRuntime()
    # Try to start with reserved AO_AGENT_ID in env
    result = runtime.start("agent-123", ["echo", "test"], env={"AO_AGENT_ID": "malicious-id"})
    assert result is False
    assert runtime.get_state("agent-123") == RuntimeState.STOPPED
