from fastapi import Request

def verify_workspace_access(request: Request, project_id: str):
    auth_workspace = request.headers.get("X-Workspace-ID")
    if auth_workspace and auth_workspace != project_id:
        return False
    return True
