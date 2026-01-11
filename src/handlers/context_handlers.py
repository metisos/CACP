from typing import Dict, Any, Optional, List
from datetime import datetime

from src.store import MemoryStore
from src.models import ContextPacket
from src.models.enums import ContextType


class ContextHandlers:
    """Handlers for context sharing JSON-RPC methods."""

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

    def share(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Share a context packet with the project.

        Params:
            projectId: str
            type: str - code_snippet, type_definition, question, decision, etc.
            content: Dict - Type-specific content
            relatedContracts: List[str] (optional) - Related contract IDs
            replyTo: str (optional) - Packet ID for threading
        """
        project_id = params["projectId"]
        our_repo_id = self._get_our_repo_id(project_id)

        try:
            context_type = ContextType(params["type"])
        except ValueError:
            raise ValueError(f"Invalid context type: {params['type']}")

        # Validate replyTo if provided
        reply_to = params.get("replyTo")
        if reply_to:
            parent = self.store.get_context(project_id, reply_to)
            if not parent:
                raise ValueError(f"Reply target {reply_to} not found")

        packet = ContextPacket(
            from_repo=our_repo_id,
            from_agent=self.agent_id,
            type=context_type,
            content=params["content"],
            related_contracts=params.get("relatedContracts", []),
            reply_to=reply_to,
        )

        self.store.add_context(project_id, packet)

        return {
            "packetId": packet.packet_id,
            "status": "shared",
        }

    def list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List context packets.

        Params:
            projectId: str
            type: str (optional) - Filter by type
            contractId: str (optional) - Filter by related contract
            since: str (optional) - ISO timestamp, only return packets after this time
            limit: int (optional) - Max packets to return (default 50)
        """
        project_id = params["projectId"]

        type_filter = None
        if params.get("type"):
            try:
                type_filter = ContextType(params["type"])
            except ValueError:
                raise ValueError(f"Invalid context type: {params['type']}")

        since = None
        if params.get("since"):
            since = datetime.fromisoformat(params["since"].replace("Z", "+00:00"))

        packets = self.store.list_context(
            project_id=project_id,
            type_filter=type_filter,
            contract_id=params.get("contractId"),
            since=since,
            limit=params.get("limit", 50),
        )

        return {
            "packets": [p.model_dump(mode="json") for p in packets]
        }

    def get_thread(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a conversation thread.

        Params:
            projectId: str
            packetId: str - Root packet ID
        """
        thread = self.store.get_thread(params["projectId"], params["packetId"])

        return {
            "thread": [p.model_dump(mode="json") for p in thread]
        }

    # --- Helper methods for common context types ---

    def ask_question(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to ask a question.

        Params:
            projectId: str
            question: str
            options: List[str] (optional)
            urgent: bool (optional)
            relatedContracts: List[str] (optional)
        """
        return self.share({
            "projectId": params["projectId"],
            "type": "question",
            "content": {
                "question": params["question"],
                "options": params.get("options"),
                "urgent": params.get("urgent", False),
            },
            "relatedContracts": params.get("relatedContracts", []),
        })

    def record_decision(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to record a decision.

        Params:
            projectId: str
            decision: str - What was decided
            chosen: str - The choice made
            rationale: str - Why
            implications: List[str] (optional) - Impact on each repo
            relatedContracts: List[str] (optional)
        """
        return self.share({
            "projectId": params["projectId"],
            "type": "decision",
            "content": {
                "decision": params["decision"],
                "chosen": params["chosen"],
                "rationale": params["rationale"],
                "implications": params.get("implications", []),
            },
            "relatedContracts": params.get("relatedContracts", []),
        })

    def share_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to share a code snippet.

        Params:
            projectId: str
            language: str
            file: str
            snippet: str
            explanation: str
            lineStart: int (optional)
            lineEnd: int (optional)
            relatedContracts: List[str] (optional)
        """
        return self.share({
            "projectId": params["projectId"],
            "type": "code_snippet",
            "content": {
                "language": params["language"],
                "file": params["file"],
                "snippet": params["snippet"],
                "explanation": params["explanation"],
                "line_start": params.get("lineStart"),
                "line_end": params.get("lineEnd"),
            },
            "relatedContracts": params.get("relatedContracts", []),
        })

    def share_types(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to share type definitions.

        Params:
            projectId: str
            language: str
            definitions: str
            note: str (optional)
            relatedContracts: List[str] (optional)
        """
        return self.share({
            "projectId": params["projectId"],
            "type": "type_definition",
            "content": {
                "language": params["language"],
                "definitions": params["definitions"],
                "note": params.get("note"),
            },
            "relatedContracts": params.get("relatedContracts", []),
        })
