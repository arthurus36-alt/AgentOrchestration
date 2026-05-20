from fastapi.testclient import TestClient
from src.api.server import create_app

def test_cross_project_artifact_lookup_returns_404():
    app = create_app()
    client = TestClient(app)
    # The middleware requires API key or Bearer
    
    # Valid workspace
    response = client.get(
        "/api/v2/projects/proj-123/artifacts/art-456",
        headers={"X-Workspace-ID": "proj-123", "Authorization": "Bearer TEST"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": "art-456", "project_id": "proj-123", "data": "artifact content"}

    # Invalid cross-project workspace
    response = client.get(
        "/api/v2/projects/proj-123/artifacts/art-456",
        headers={"X-Workspace-ID": "proj-999", "Authorization": "Bearer TEST"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"
