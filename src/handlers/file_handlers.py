from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import base64
import uuid

from src.store import MemoryStore


class FileHandlers:
    """Handlers for file sharing JSON-RPC methods."""

    def __init__(self, store: MemoryStore, agent_id: str, repo_name: str, workspace_path: Optional[str] = None):
        self.store = store
        self.agent_id = agent_id
        self.repo_name = repo_name
        self.workspace_path = Path(workspace_path) if workspace_path else Path("./workspace")
        self.pending_requests: Dict[str, Dict[str, Any]] = {}

    def _get_our_repo_id(self, project_id: str) -> str:
        """Get our repo_id in the given project."""
        project = self.store.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        repo = project.get_repo_by_name(self.repo_name)
        if not repo:
            raise ValueError(f"Not a member of project {project_id}")
        return repo.repo_id

    def share(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Share a file with the project.

        Params:
            projectId: str
            file: Dict with name, content (base64), contentType
            purpose: str - Why this file is being shared
            relatedContracts: List[str] (optional)
        """
        project_id = params["projectId"]
        self._get_our_repo_id(project_id)  # Validate membership

        file_data = params["file"]
        file_name = file_data["name"]
        file_content = file_data["content"]  # Base64 encoded
        content_type = file_data.get("contentType", "application/octet-stream")

        # Decode and save file
        try:
            decoded = base64.b64decode(file_content)
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {e}")

        # Check size limit (10MB)
        if len(decoded) > 10 * 1024 * 1024:
            raise ValueError("File too large (max 10MB)")

        # Create workspace directory if needed
        save_dir = self.workspace_path / project_id
        save_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename to avoid collisions
        unique_name = f"{uuid.uuid4().hex[:8]}_{file_name}"
        save_path = save_dir / unique_name

        save_path.write_bytes(decoded)

        return {
            "status": "received",
            "savedTo": str(save_path),
            "size": len(decoded),
        }

    def request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request a file from other agents.

        Params:
            projectId: str
            description: str - What file is needed
            suggestedFormat: str (optional) - json, yaml, typescript, etc.
        """
        project_id = params["projectId"]
        our_repo_id = self._get_our_repo_id(project_id)

        request_id = str(uuid.uuid4())

        self.pending_requests[request_id] = {
            "projectId": project_id,
            "requestedBy": our_repo_id,
            "description": params["description"],
            "suggestedFormat": params.get("suggestedFormat"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return {
            "status": "request_received",
            "requestId": request_id,
        }

    def list_requests(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List pending file requests.

        Params:
            projectId: str
        """
        project_id = params["projectId"]

        requests = [
            {
                "requestId": rid,
                **req_data,
            }
            for rid, req_data in self.pending_requests.items()
            if req_data["projectId"] == project_id
        ]

        return {
            "requests": requests
        }

    def fulfill_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fulfill a file request by sharing the file.

        Params:
            requestId: str
            file: Dict with name, content (base64), contentType
        """
        request_id = params["requestId"]

        if request_id not in self.pending_requests:
            raise ValueError(f"Request {request_id} not found")

        req_data = self.pending_requests[request_id]

        # Share the file
        result = self.share({
            "projectId": req_data["projectId"],
            "file": params["file"],
            "purpose": f"Fulfilling request: {req_data['description']}",
        })

        # Remove the request
        del self.pending_requests[request_id]

        return {
            "status": "fulfilled",
            **result,
        }
