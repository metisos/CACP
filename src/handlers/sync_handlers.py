"""
Sync Handlers for CACP Peer-to-Peer State Propagation

These handlers receive state updates from peer agents and apply them
to the local store. They implement the "receiver" side of state sync.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from src.store import MemoryStore
from src.models import Project, Contract, ContextPacket, RepoContext
from src.models.contract import ContractVersion, Implementation
from src.models.enums import ContractStatus

logger = logging.getLogger(__name__)


class SyncHandlers:
    """
    Handlers for receiving state sync from peer agents.

    When a peer agent makes a change (e.g., creates a project, proposes a contract),
    it broadcasts to all peers. These handlers receive those broadcasts and apply
    them to the local store.
    """

    def __init__(self, store: MemoryStore, agent_id: str, repo_name: str):
        self.store = store
        self.agent_id = agent_id
        self.repo_name = repo_name

    def project_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive and store a project from a peer.

        Params:
            project: Full project data (serialized)
            source_agent: Agent that sent this sync
        """
        project_data = params["project"]
        source_agent = params.get("source_agent", "unknown")

        logger.info(f"Receiving project sync from {source_agent}: {project_data.get('project_id')}")

        # Reconstruct the project
        project_data["repos"] = [RepoContext(**r) for r in project_data.get("repos", [])]
        project_data["contracts"] = [
            self._reconstruct_contract(c) for c in project_data.get("contracts", [])
        ]
        project_data["context_history"] = [
            ContextPacket(**p) for p in project_data.get("context_history", [])
        ]

        project = Project(**project_data)

        # Check if we already have this project
        existing = self.store.get_project(project.project_id)
        if existing:
            # Update if the incoming data is newer
            if project.updated_at > existing.updated_at:
                self.store.update_project(project)
                return {"status": "updated", "projectId": project.project_id}
            else:
                return {"status": "skipped", "reason": "local version is newer"}
        else:
            # Create new
            self.store.create_project(project)
            return {"status": "created", "projectId": project.project_id}

    def contract_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive and store a contract update from a peer.

        Params:
            projectId: Project the contract belongs to
            contract: Full contract data (serialized)
            source_agent: Agent that sent this sync
        """
        project_id = params["projectId"]
        contract_data = params["contract"]
        source_agent = params.get("source_agent", "unknown")

        logger.info(f"Receiving contract sync from {source_agent}: {contract_data.get('contract_id')}")

        project = self.store.get_project(project_id)
        if not project:
            return {"status": "error", "reason": f"Project {project_id} not found"}

        contract = self._reconstruct_contract(contract_data)

        # Check if we already have this contract
        existing = project.get_contract_by_id(contract.contract_id)
        if existing:
            # Update if newer version or newer timestamp
            if contract.version > existing.version or contract.updated_at > existing.updated_at:
                self.store.update_contract(project_id, contract)
                return {"status": "updated", "contractId": contract.contract_id, "version": contract.version}
            else:
                return {"status": "skipped", "reason": "local version is newer or same"}
        else:
            # Add new contract
            self.store.add_contract(project_id, contract)
            return {"status": "created", "contractId": contract.contract_id}

    def context_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive and store a context packet from a peer.

        Params:
            projectId: Project the context belongs to
            packet: Full context packet data (serialized)
            source_agent: Agent that sent this sync
        """
        project_id = params["projectId"]
        packet_data = params["packet"]
        source_agent = params.get("source_agent", "unknown")

        logger.info(f"Receiving context sync from {source_agent}: {packet_data.get('packet_id')}")

        project = self.store.get_project(project_id)
        if not project:
            return {"status": "error", "reason": f"Project {project_id} not found"}

        packet = ContextPacket(**packet_data)

        # Check if we already have this packet
        existing = self.store.get_context(project_id, packet.packet_id)
        if existing:
            return {"status": "skipped", "reason": "already exists"}
        else:
            self.store.add_context(project_id, packet)
            return {"status": "created", "packetId": packet.packet_id}

    def repo_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive repo assignment update from a peer.

        Params:
            projectId: Project ID
            repo: Repo data with assignment info
            source_agent: Agent that sent this sync
        """
        project_id = params["projectId"]
        repo_data = params["repo"]
        source_agent = params.get("source_agent", "unknown")

        logger.info(f"Receiving repo sync from {source_agent}: {repo_data.get('name')}")

        project = self.store.get_project(project_id)
        if not project:
            return {"status": "error", "reason": f"Project {project_id} not found"}

        repo = RepoContext(**repo_data)

        # Find and update the repo
        existing = project.get_repo_by_id(repo.repo_id)
        if existing:
            self.store.update_repo(project_id, repo)
            return {"status": "updated", "repoId": repo.repo_id}
        else:
            self.store.add_repo(project_id, repo)
            return {"status": "created", "repoId": repo.repo_id}

    def peer_announce(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive announcement from a new peer.

        Params:
            agentId: The announcing agent's ID
            endpoint: The announcing agent's endpoint
            repoName: The repo it manages
        """
        # This is informational - the peer registry handles actual registration
        return {
            "status": "acknowledged",
            "myAgentId": self.agent_id,
            "myRepoName": self.repo_name,
        }

    def _reconstruct_contract(self, data: dict) -> Contract:
        """Reconstruct a Contract from dict, handling nested objects."""
        data["implementations"] = [
            Implementation(**i) for i in data.get("implementations", [])
        ]
        data["history"] = [
            ContractVersion(**v) for v in data.get("history", [])
        ]
        return Contract(**data)
