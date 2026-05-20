from fastapi.testclient import TestClient
from src.agent import AgentRegistry
from src.api import routes
from src.api.server import create_app

routes.registry = AgentRegistry()
client = TestClient(create_app())
agent_id = routes.registry.register("test-agent", "worker.processor", {"retries": 1, "mode": "safe"})
response = client.patch(
    f"/api/v2/agents/{agent_id}/config",
    headers={"Authorization": "Bearer test-token", "If-Match": '"1"'},
    json={"config": {"retries": 2}},
)
print("status:", response.status_code)
print("json:", response.json())
