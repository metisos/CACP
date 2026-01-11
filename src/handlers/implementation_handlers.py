from typing import Dict, Any, Optional
from datetime import datetime

from src.store import MemoryStore
from src.models import Implementation
from src.models.enums import ContractStatus, ImplementationStatus


class ImplementationHandlers:
    """Handlers for implementation tracking JSON-RPC methods."""

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

    def start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signal start of implementation for a contract.

        Params:
            projectId: str
            contractId: str
            plan: str - Implementation plan
            estimatedFiles: List[str] (optional) - Files expected to be modified
        """
        project_id = params["projectId"]
        contract_id = params["contractId"]
        our_repo_id = self._get_our_repo_id(project_id)

        contract = self.store.get_contract(project_id, contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # Contract must be agreed (or in progress - IMPLEMENTED means some repos done but not all)
        if contract.status not in (ContractStatus.AGREED, ContractStatus.IMPLEMENTED):
            raise ValueError(f"Contract must be agreed before implementation. Current status: {contract.status.value}")

        # Check if we already have an implementation record
        impl = contract.get_implementation(our_repo_id)
        if impl:
            impl.status = ImplementationStatus.IN_PROGRESS
            impl.plan = params.get("plan")
            impl.files = params.get("estimatedFiles", [])
            impl.started_at = datetime.utcnow()
        else:
            impl = Implementation(
                repo_id=our_repo_id,
                agent_id=self.agent_id,
                status=ImplementationStatus.IN_PROGRESS,
                plan=params.get("plan"),
                files=params.get("estimatedFiles", []),
                started_at=datetime.utcnow(),
            )
            contract.implementations.append(impl)

        self.store.update_contract(project_id, contract)

        return {
            "status": "started",
            "implementationId": f"{contract_id}:{our_repo_id}",
        }

    def complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signal completion of implementation.

        Params:
            projectId: str
            contractId: str
            files: List[str] - Files that were modified
            notes: str (optional) - Implementation notes
            testEndpoint: str (optional) - Endpoint for integration testing
        """
        project_id = params["projectId"]
        contract_id = params["contractId"]
        our_repo_id = self._get_our_repo_id(project_id)

        project = self.store.get_project(project_id)
        contract = self.store.get_contract(project_id, contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        impl = contract.get_implementation(our_repo_id)
        if not impl:
            raise ValueError(f"No implementation started for this contract")

        impl.status = ImplementationStatus.COMPLETE
        impl.files = params["files"]
        impl.notes = params.get("notes", "")
        impl.test_endpoint = params.get("testEndpoint")
        impl.completed_at = datetime.utcnow()

        # Check if all implementations are complete (all repos in project should implement)
        expected_repo_count = len(project.repos) if project else 0
        if contract.all_implementations_complete(expected_repo_count):
            contract.transition_to(ContractStatus.IMPLEMENTED)

        self.store.update_contract(project_id, contract)

        return {
            "status": "complete",
            "contractStatus": contract.status.value,
        }

    def verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify integration between implementations.

        Params:
            projectId: str
            contractId: str
            result: str - success, failure, partial
            notes: str (optional)
            failureDetails: Dict (optional) - Details if verification failed
        """
        project_id = params["projectId"]
        contract_id = params["contractId"]

        contract = self.store.get_contract(project_id, contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        if contract.status != ContractStatus.IMPLEMENTED:
            raise ValueError(f"Contract must be implemented before verification. Current status: {contract.status.value}")

        result = params["result"]

        if result == "success":
            contract.transition_to(ContractStatus.VERIFIED)
            status = "verified"
        elif result == "failure":
            # Mark implementations as needing revision
            for impl in contract.implementations:
                impl.status = ImplementationStatus.NEEDS_REVISION
            contract.transition_to(ContractStatus.AGREED)  # Back to agreed for re-implementation
            status = "failed"
        elif result == "partial":
            status = "partial"
        else:
            raise ValueError(f"Invalid result: {result}")

        self.store.update_contract(project_id, contract)

        return {
            "status": status,
            "contractStatus": contract.status.value,
        }

    def get_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get implementation status for a contract.

        Params:
            projectId: str
            contractId: str
        """
        contract = self.store.get_contract(params["projectId"], params["contractId"])
        if not contract:
            raise ValueError(f"Contract {params['contractId']} not found")

        return {
            "contractId": contract.contract_id,
            "contractStatus": contract.status.value,
            "implementations": [
                {
                    "repoId": impl.repo_id,
                    "agentId": impl.agent_id,
                    "status": impl.status.value,
                    "files": impl.files,
                    "startedAt": impl.started_at.isoformat() if impl.started_at else None,
                    "completedAt": impl.completed_at.isoformat() if impl.completed_at else None,
                }
                for impl in contract.implementations
            ],
        }
