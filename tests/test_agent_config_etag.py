import pytest
from fastapi.testclient import TestClient

from src.agent import AgentRegistry
from src.api import routes
from src.api.agent_config import AgentConfigUpdateError, update_agent_config
from src.api.server import create_app


AUTH = {"Authorization": "Bearer test-token"}

class LookupGuardRegistry:
    def get(self, _agent_id):
        raise AssertionError("registry lookup should not run")


def make_client():
    routes.registry = AgentRegistry()
    return TestClient(create_app())


def register_agent(config=None):
    return routes.registry.register(
        "test-agent",
        "worker.processor",
        config or {"retries": 1, "mode": "safe"},
    )


def test_authorized_config_update_returns_next_etag():
    client = make_client()
    agent_id = register_agent()

    response = client.patch(
        f"/api/v2/agents/{agent_id}/config",
        headers={**AUTH, "If-Match": '"1"'},
        json={"config": {"retries": 2}},
    )

    assert response.status_code == 200
    assert response.headers["etag"] == '"2"'
    assert response.json() == {"agent_id": agent_id, "config": {"retries": 2}}
    assert routes.registry.get(agent_id)["config"] == {"retries": 2}
    assert routes.registry.get(agent_id)["config_version"] == 2


def test_stale_etag_cannot_overwrite_newer_agent_config():
    client = make_client()
    agent_id = register_agent()

    first = client.patch(
        f"/api/v2/agents/{agent_id}/config",
        headers={**AUTH, "If-Match": '"1"'},
        json={"config": {"retries": 2}},
    )
    assert first.status_code == 200

    stale = client.patch(
        f"/api/v2/agents/{agent_id}/config",
        headers={**AUTH, "If-Match": '"1"'},
        json={"config": {"retries": 99}},
    )

    assert stale.status_code == 412
    assert stale.json()["detail"] == "Stale agent config ETag"
    assert routes.registry.get(agent_id)["config"] == {"retries": 2}
    assert routes.registry.get(agent_id)["config_version"] == 2
