from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
import uuid

from .enums import ProjectStatus


class RepoContext(BaseModel):
    repo_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    role: str  # "frontend", "backend", "mobile", "shared"
    language: str
    relevant_paths: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    assigned_agent: Optional[str] = None
    agent_endpoint: Optional[str] = None


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    objective: str
    status: ProjectStatus = ProjectStatus.PLANNING
    repos: List[RepoContext] = Field(default_factory=list)
    contracts: List[Any] = Field(default_factory=list)  # List[Contract] - forward ref
    context_history: List[Any] = Field(default_factory=list)  # List[ContextPacket]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_repo_by_name(self, name: str) -> Optional[RepoContext]:
        return next((r for r in self.repos if r.name == name), None)

    def get_repo_by_id(self, repo_id: str) -> Optional[RepoContext]:
        return next((r for r in self.repos if r.repo_id == repo_id), None)

    def get_contract_by_id(self, contract_id: str) -> Optional[Any]:
        return next((c for c in self.contracts if c.contract_id == contract_id), None)
