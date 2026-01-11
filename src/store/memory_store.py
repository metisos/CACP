from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import json

from src.models import (
    Project,
    Contract,
    ContextPacket,
    RepoContext,
    ContractVersion,
    Implementation,
)
from src.models.enums import ProjectStatus, ContractType, ContractStatus, ContextType


class MemoryStore:
    """In-memory state store with optional JSON file persistence."""

    def __init__(self, persist_path: Optional[str] = None):
        self.projects: Dict[str, Project] = {}
        self.persist_path = Path(persist_path) if persist_path else None

        if self.persist_path and self.persist_path.exists():
            self._load()

    # --- Project Operations ---

    def create_project(self, project: Project) -> Project:
        self.projects[project.project_id] = project
        self._save()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        return self.projects.get(project_id)

    def update_project(self, project: Project) -> Project:
        project.updated_at = datetime.utcnow()
        self.projects[project.project_id] = project
        self._save()
        return project

    def list_projects(self) -> List[Project]:
        return list(self.projects.values())

    def delete_project(self, project_id: str) -> bool:
        if project_id in self.projects:
            del self.projects[project_id]
            self._save()
            return True
        return False

    # --- Contract Operations ---

    def add_contract(self, project_id: str, contract: Contract) -> Contract:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        project.contracts.append(contract)
        self.update_project(project)
        return contract

    def get_contract(self, project_id: str, contract_id: str) -> Optional[Contract]:
        project = self.get_project(project_id)
        if not project:
            return None
        return project.get_contract_by_id(contract_id)

    def update_contract(self, project_id: str, contract: Contract) -> Contract:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        contract.updated_at = datetime.utcnow()
        project.contracts = [
            c if c.contract_id != contract.contract_id else contract
            for c in project.contracts
        ]
        self.update_project(project)
        return contract

    def list_contracts(self, project_id: str) -> List[Contract]:
        project = self.get_project(project_id)
        if not project:
            return []
        return project.contracts

    # --- Context Operations ---

    def add_context(self, project_id: str, packet: ContextPacket) -> ContextPacket:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        project.context_history.append(packet)
        self.update_project(project)
        return packet

    def get_context(self, project_id: str, packet_id: str) -> Optional[ContextPacket]:
        project = self.get_project(project_id)
        if not project:
            return None
        return next(
            (p for p in project.context_history if p.packet_id == packet_id),
            None
        )

    def list_context(
        self,
        project_id: str,
        type_filter: Optional[ContextType] = None,
        contract_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[ContextPacket]:
        project = self.get_project(project_id)
        if not project:
            return []

        packets = project.context_history

        if type_filter:
            packets = [p for p in packets if p.type == type_filter]
        if contract_id:
            packets = [p for p in packets if contract_id in p.related_contracts]
        if since:
            packets = [p for p in packets if p.timestamp > since]

        # Return most recent, up to limit
        return packets[-limit:]

    def get_thread(self, project_id: str, packet_id: str) -> List[ContextPacket]:
        """Get all packets in a thread (replies to a packet)."""
        project = self.get_project(project_id)
        if not project:
            return []

        # Find the root packet
        root = self.get_context(project_id, packet_id)
        if not root:
            return []

        # Get all replies
        thread = [root]
        replies = [p for p in project.context_history if p.reply_to == packet_id]
        thread.extend(replies)

        # Sort by timestamp
        thread.sort(key=lambda p: p.timestamp)
        return thread

    # --- Repo Operations ---

    def add_repo(self, project_id: str, repo: RepoContext) -> RepoContext:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        project.repos.append(repo)
        self.update_project(project)
        return repo

    def update_repo(self, project_id: str, repo: RepoContext) -> RepoContext:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        project.repos = [
            r if r.repo_id != repo.repo_id else repo
            for r in project.repos
        ]
        self.update_project(project)
        return repo

    # --- Persistence ---

    def _save(self):
        if not self.persist_path:
            return

        data = {}
        for pid, project in self.projects.items():
            data[pid] = project.model_dump(mode="json")

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.persist_path.write_text(json.dumps(data, indent=2, default=str))

    def _load(self):
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            data = json.loads(self.persist_path.read_text())
            for pid, project_data in data.items():
                # Reconstruct nested objects
                project_data["repos"] = [
                    RepoContext(**r) for r in project_data.get("repos", [])
                ]
                project_data["contracts"] = [
                    self._reconstruct_contract(c) for c in project_data.get("contracts", [])
                ]
                project_data["context_history"] = [
                    ContextPacket(**p) for p in project_data.get("context_history", [])
                ]
                self.projects[pid] = Project(**project_data)
        except Exception as e:
            print(f"Warning: Failed to load persisted state: {e}")

    def _reconstruct_contract(self, data: dict) -> Contract:
        """Reconstruct a Contract from dict, handling nested objects."""
        data["implementations"] = [
            Implementation(**i) for i in data.get("implementations", [])
        ]
        data["history"] = [
            ContractVersion(**v) for v in data.get("history", [])
        ]
        return Contract(**data)

    def clear(self):
        """Clear all data (useful for testing)."""
        self.projects = {}
        self._save()
