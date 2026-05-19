import pytest
from fastapi.testclient import TestClient
from src.api.server import create_app
from src.api.routes import get_current_context

def test_run_search_scoped_to_workspace():
    app = create_app()
    client = TestClient(app)
    
    # Authorized client should only see ws_123 runs
    response = client.get("/api/v2/search/runs?query=test")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["workspace_id"] == "ws_123"

def test_run_search_unauthorized_boundary():
    app = create_app()
    
    # Mock an unauthorized context without a workspace_id
    def override_context():
        return {"role": "guest", "workspace_id": None}
        
    app.dependency_overrides[get_current_context] = override_context
    client = TestClient(app)
    
    response = client.get("/api/v2/search/runs?query=test")
    assert response.status_code == 403
    assert "Workspace ID is required" in response.json()["detail"]
