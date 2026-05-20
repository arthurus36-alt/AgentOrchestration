from fastapi import Request
from src.agent import AgentStatus

def verify_run_state_for_approval(registry, agent_id: str):
    agent = registry.get(agent_id)
    if not agent:
        return False
    # Only PAUSED/PENDING/RUNNING runs are generally valid for a step approval context, but 
    # to "Check run state before approving human step", if it's already TERMINATED or FAILED, we shouldn't approve.
    if agent.get("status") in [AgentStatus.TERMINATED.value, AgentStatus.FAILED.value, AgentStatus.STOPPED.value]:
        return False
    return True
