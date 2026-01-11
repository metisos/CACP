from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from .enums import ContextType


class ContextPacket(BaseModel):
    packet_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_repo: str  # repo_id
    from_agent: str  # agent_id
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    type: ContextType
    content: Dict[str, Any]  # Type-specific content
    related_contracts: List[str] = Field(default_factory=list)  # contract_ids
    reply_to: Optional[str] = None  # packet_id for threading


# Content type schemas for validation/reference

class QuestionContent(BaseModel):
    question: str
    options: Optional[List[str]] = None
    urgent: bool = False


class DecisionContent(BaseModel):
    decision: str
    chosen: str
    rationale: str
    implications: List[str] = Field(default_factory=list)


class CodeSnippetContent(BaseModel):
    language: str
    file: str
    snippet: str
    explanation: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None


class TypeDefinitionContent(BaseModel):
    language: str
    definitions: str
    note: Optional[str] = None


class ApiSpecContent(BaseModel):
    spec: Dict[str, Any]  # OpenAPI or similar
    note: Optional[str] = None


class ErrorCatalogContent(BaseModel):
    errors: List[Dict[str, Any]]  # List of {code, name, description}


class TestCaseContent(BaseModel):
    name: str
    description: str
    steps: List[str]
    expected_result: str


class DependencyInfoContent(BaseModel):
    dependencies: Dict[str, str]  # package -> version
    note: Optional[str] = None


class ImplementationStatusContent(BaseModel):
    contract_id: str
    status: str
    progress: Optional[str] = None
    blockers: Optional[List[str]] = None
