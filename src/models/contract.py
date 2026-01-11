from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from .enums import ContractType, ContractStatus, ImplementationStatus


# Valid status transitions
VALID_TRANSITIONS: Dict[ContractStatus, List[ContractStatus]] = {
    ContractStatus.PROPOSED: [ContractStatus.NEGOTIATING, ContractStatus.AGREED],
    ContractStatus.NEGOTIATING: [ContractStatus.PROPOSED, ContractStatus.AGREED],
    ContractStatus.AGREED: [ContractStatus.IMPLEMENTED, ContractStatus.PROPOSED],
    ContractStatus.IMPLEMENTED: [ContractStatus.VERIFIED, ContractStatus.AGREED],
    ContractStatus.VERIFIED: [ContractStatus.IMPLEMENTED],
}


def can_transition(from_status: ContractStatus, to_status: ContractStatus) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Implementation(BaseModel):
    repo_id: str
    agent_id: str
    status: ImplementationStatus = ImplementationStatus.PENDING
    files: List[str] = Field(default_factory=list)
    notes: str = ""
    plan: Optional[str] = None
    test_endpoint: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ContractVersion(BaseModel):
    version: int
    content: Dict[str, Any]
    proposed_by: str  # repo_id
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    change_notes: Optional[str] = None


class Contract(BaseModel):
    contract_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ContractType
    name: str
    version: int = 1
    status: ContractStatus = ContractStatus.PROPOSED
    content: Dict[str, Any]  # Type-specific schema
    proposed_by: str  # repo_id
    implementations: List[Implementation] = Field(default_factory=list)
    history: List[ContractVersion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def increment_version(self, new_content: Dict[str, Any], proposed_by: str, change_notes: Optional[str] = None):
        """Increment version and add to history."""
        self.history.append(ContractVersion(
            version=self.version,
            content=self.content,
            proposed_by=self.proposed_by,
            timestamp=self.updated_at,
            change_notes=change_notes
        ))
        self.version += 1
        self.content = new_content
        self.proposed_by = proposed_by
        self.updated_at = datetime.utcnow()

    def transition_to(self, new_status: ContractStatus) -> bool:
        """Attempt to transition to new status. Returns True if successful."""
        if can_transition(self.status, new_status):
            self.status = new_status
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_implementation(self, repo_id: str) -> Optional[Implementation]:
        return next((i for i in self.implementations if i.repo_id == repo_id), None)

    def all_implementations_complete(self, expected_repo_count: int = 0) -> bool:
        """Check if all implementations are complete.

        Args:
            expected_repo_count: Number of repos expected to implement this contract.
                                 If 0, just checks that at least one exists and all are complete.
        """
        if not self.implementations:
            return False
        if expected_repo_count > 0 and len(self.implementations) < expected_repo_count:
            return False
        return all(i.status == ImplementationStatus.COMPLETE for i in self.implementations)
