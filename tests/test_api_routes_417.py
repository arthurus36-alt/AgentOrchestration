from fastapi.testclient import TestClient
from src.api.server import create_app
from src.api.routes import registry
from src.agent import AgentStatus

def test_check_run_state_before_approving_human_step():
    app = create_app()
    client = TestClient(app)
    
    # Create valid agent
    valid_id = registry.register("Test Valid", "type1")
    registry.update_status(valid_id, AgentStatus.PAUSED)
    
    response = client.post(
        f"/api/v2/agents/{valid_id}/approve",
        headers={"Authorization": "Bearer TEST"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Create invalid agent
    invalid_id = registry.register("Test Invalid", "type1")
    registry.update_status(invalid_id, AgentStatus.FAILED)
    
    response = client.post(
        f"/api/v2/agents/{invalid_id}/approve",
        headers={"Authorization": "Bearer TEST"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Run state invalid for approval"
    
    # Missing agent
    response = client.post(
        f"/api/v2/agents/missing-id/approve",
        headers={"Authorization": "Bearer TEST"}
    )
    assert response.status_code == 400
