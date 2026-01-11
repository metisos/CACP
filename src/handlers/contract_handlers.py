from typing import Dict, Any, Optional
from datetime import datetime

from src.store import MemoryStore
from src.models import Contract, ContractVersion, Implementation
from src.models.enums import ContractType, ContractStatus, ImplementationStatus


class ContractHandlers:
    """Handlers for contract-related JSON-RPC methods."""

    def __init__(self, store: MemoryStore, agent_id: str, repo_name: str):
        self.store = store
        self.agent_id = agent_id
        self.repo_name = repo_name

    def _get_our_repo_id(self, project_id: str) -> str:
        """Get our repo_id in the given project."""
        project = self.store.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        repo = project.get_repo_by_name(self.repo_name)
        if not repo:
            raise ValueError(f"Not a member of project {project_id}")
        return repo.repo_id

    def propose(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Propose a new contract.

        Params:
            projectId: str
            type: str - api_endpoint, event_schema, data_model, config_spec, rpc_interface, custom
            name: str - Contract name
            content: Dict - Type-specific contract content
        """
        project_id = params["projectId"]
        our_repo_id = self._get_our_repo_id(project_id)

        try:
            contract_type = ContractType(params["type"])
        except ValueError:
            raise ValueError(f"Invalid contract type: {params['type']}")

        contract = Contract(
            type=contract_type,
            name=params["name"],
            content=params["content"],
            proposed_by=our_repo_id,
            # History starts empty - only populated when contract is updated
        )

        self.store.add_contract(project_id, contract)

        return {
            "contractId": contract.contract_id,
            "version": contract.version,
            "status": contract.status.value,
        }

    def respond(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Respond to a contract proposal.

        Params:
            projectId: str
            contractId: str
            action: str - agree, request_change, reject
            comment: str (optional) - Explanation
            suggestedChange: Dict (optional) - Proposed changes to content
        """
        project_id = params["projectId"]
        contract_id = params["contractId"]
        action = params["action"]

        contract = self.store.get_contract(project_id, contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        if action == "agree":
            if not contract.transition_to(ContractStatus.AGREED):
                raise ValueError(f"Cannot agree to contract in status {contract.status.value}")
            result_status = "agreed"

        elif action == "request_change":
            contract.transition_to(ContractStatus.NEGOTIATING)
            result_status = "change_requested"

        elif action == "reject":
            # Rejected contracts go back to proposed for revision
            contract.status = ContractStatus.PROPOSED
            result_status = "rejected"

        else:
            raise ValueError(f"Invalid action: {action}")

        self.store.update_contract(project_id, contract)

        return {
            "status": result_status,
            "contractVersion": contract.version,
            "contractStatus": contract.status.value,
        }

    def update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update contract content (creates new version).

        Params:
            projectId: str
            contractId: str
            content: Dict - New contract content
            changeNotes: str (optional) - Description of changes
        """
        project_id = params["projectId"]
        contract_id = params["contractId"]
        our_repo_id = self._get_our_repo_id(project_id)

        contract = self.store.get_contract(project_id, contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # Update content and increment version
        contract.increment_version(
            new_content=params["content"],
            proposed_by=our_repo_id,
            change_notes=params.get("changeNotes"),
        )

        # Reset to proposed status for re-agreement
        contract.status = ContractStatus.PROPOSED

        self.store.update_contract(project_id, contract)

        return {
            "contractId": contract.contract_id,
            "version": contract.version,
            "status": contract.status.value,
        }

    def get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get contract details.

        Params:
            projectId: str
            contractId: str
            includeHistory: bool (optional) - Include version history
        """
        contract = self.store.get_contract(params["projectId"], params["contractId"])
        if not contract:
            raise ValueError(f"Contract {params['contractId']} not found")

        result = contract.model_dump(mode="json")

        if not params.get("includeHistory", False):
            result.pop("history", None)

        return result

    def list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List contracts in a project.

        Params:
            projectId: str
            status: str (optional) - Filter by status
            type: str (optional) - Filter by type
        """
        contracts = self.store.list_contracts(params["projectId"])

        status_filter = params.get("status")
        type_filter = params.get("type")

        if status_filter:
            contracts = [c for c in contracts if c.status.value == status_filter]
        if type_filter:
            contracts = [c for c in contracts if c.type.value == type_filter]

        return {
            "contracts": [
                {
                    "contractId": c.contract_id,
                    "type": c.type.value,
                    "name": c.name,
                    "version": c.version,
                    "status": c.status.value,
                    "proposedBy": c.proposed_by,
                }
                for c in contracts
            ]
        }
