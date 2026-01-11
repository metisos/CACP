from typing import Dict, Any, Optional
from datetime import datetime

from src.store import MemoryStore
from src.models import Project, RepoContext
from src.models.enums import ProjectStatus


class ProjectHandlers:
    """Handlers for project-related JSON-RPC methods."""

    def __init__(self, store: MemoryStore, agent_id: str, repo_name: str):
        self.store = store
        self.agent_id = agent_id
        self.repo_name = repo_name

    def create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new cross-repo project.

        Params:
            name: str - Project name
            objective: str - Project objective/description
            repos: List[Dict] - List of repos with name, role, language, relevantPaths, url
        """
        repos = []
        for repo_data in params.get("repos", []):
            repo = RepoContext(
                name=repo_data["name"],
                role=repo_data["role"],
                language=repo_data["language"],
                relevant_paths=repo_data.get("relevantPaths", []),
                url=repo_data.get("url"),
            )
            # Auto-assign this agent to matching repo
            if repo.name == self.repo_name:
                repo.assigned_agent = self.agent_id
            repos.append(repo)

        project = Project(
            name=params["name"],
            objective=params["objective"],
            repos=repos,
        )

        self.store.create_project(project)

        return {
            "projectId": project.project_id,
            "status": "created",
            "repoCount": len(repos),
        }

    def join(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Join an existing project and claim a repo.

        Params:
            projectId: str - Project to join
            repoName: str - Name of repo to claim
            agentEndpoint: str - This agent's HTTP endpoint
        """
        project = self.store.get_project(params["projectId"])
        if not project:
            raise ValueError(f"Project {params['projectId']} not found")

        repo = project.get_repo_by_name(params["repoName"])
        if not repo:
            raise ValueError(f"Repo {params['repoName']} not found in project")

        if repo.assigned_agent and repo.assigned_agent != self.agent_id:
            raise ValueError(f"Repo {params['repoName']} already claimed by another agent")

        # Claim the repo
        repo.assigned_agent = self.agent_id
        repo.agent_endpoint = params.get("agentEndpoint")

        self.store.update_project(project)

        return {
            "status": "joined",
            "repoId": repo.repo_id,
            "projectName": project.name,
        }

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get full project details.

        Params:
            projectId: str - Project ID
        """
        project = self.store.get_project(params["projectId"])
        if not project:
            raise ValueError(f"Project {params['projectId']} not found")

        return project.model_dump(mode="json")

    def list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all projects (summary view).

        Params: None
        """
        projects = self.store.list_projects()

        return {
            "projects": [
                {
                    "projectId": p.project_id,
                    "name": p.name,
                    "status": p.status.value,
                    "repoCount": len(p.repos),
                    "contractCount": len(p.contracts),
                    "createdAt": p.created_at.isoformat(),
                }
                for p in projects
            ]
        }

    def update_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update project status.

        Params:
            projectId: str
            status: str - planning, implementing, integrating, complete
        """
        project = self.store.get_project(params["projectId"])
        if not project:
            raise ValueError(f"Project {params['projectId']} not found")

        try:
            project.status = ProjectStatus(params["status"])
        except ValueError:
            raise ValueError(f"Invalid status: {params['status']}")

        self.store.update_project(project)

        return {
            "projectId": project.project_id,
            "status": project.status.value,
        }

    def add_repo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new repo to an existing project.

        Params:
            projectId: str
            repo: Dict with name, role, language, relevantPaths, url
        """
        project = self.store.get_project(params["projectId"])
        if not project:
            raise ValueError(f"Project {params['projectId']} not found")

        repo_data = params["repo"]
        repo = RepoContext(
            name=repo_data["name"],
            role=repo_data["role"],
            language=repo_data["language"],
            relevant_paths=repo_data.get("relevantPaths", []),
            url=repo_data.get("url"),
        )

        self.store.add_repo(params["projectId"], repo)

        return {
            "repoId": repo.repo_id,
            "status": "added",
        }
