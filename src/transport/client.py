import httpx
import uuid
from typing import Dict, Any, Optional, List
import asyncio


class CACPClient:
    """Client for communicating with CACP agents."""

    def __init__(
        self,
        endpoint: str,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize CACP client.

        Args:
            endpoint: Base URL of the CACP agent (e.g., "http://localhost:8080")
            agent_id: Optional agent ID for X-Agent-ID header
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.endpoint = endpoint.rstrip("/")
        self.agent_id = agent_id
        self.api_key = api_key
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.agent_id:
            headers["X-Agent-ID"] = self.agent_id
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a JSON-RPC call to the agent.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            Result from the method call

        Raises:
            Exception: If the call fails or returns an error
        """
        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            error = data["error"]
            raise Exception(f"RPC Error {error.get('code')}: {error.get('message')}")

        return data.get("result", {})

    def call_sync(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous version of call()."""
        return asyncio.run(self.call(method, params))

    async def get_agent_card(self) -> Dict[str, Any]:
        """Fetch the agent's card."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.endpoint}/.well-known/agent.json",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> Dict[str, str]:
        """Check agent health."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.endpoint}/health",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    # --- Project convenience methods ---

    async def create_project(
        self,
        name: str,
        objective: str,
        repos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a new project."""
        return await self.call("cacp/project/create", {
            "name": name,
            "objective": objective,
            "repos": repos,
        })

    async def join_project(
        self,
        project_id: str,
        repo_name: str,
        agent_endpoint: str,
    ) -> Dict[str, Any]:
        """Join an existing project."""
        return await self.call("cacp/project/join", {
            "projectId": project_id,
            "repoName": repo_name,
            "agentEndpoint": agent_endpoint,
        })

    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """Get project details."""
        return await self.call("cacp/project/get", {"projectId": project_id})

    async def list_projects(self) -> Dict[str, Any]:
        """List all projects."""
        return await self.call("cacp/project/list", {})

    # --- Contract convenience methods ---

    async def propose_contract(
        self,
        project_id: str,
        contract_type: str,
        name: str,
        content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Propose a new contract."""
        return await self.call("cacp/contract/propose", {
            "projectId": project_id,
            "type": contract_type,
            "name": name,
            "content": content,
        })

    async def respond_to_contract(
        self,
        project_id: str,
        contract_id: str,
        action: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Respond to a contract."""
        params = {
            "projectId": project_id,
            "contractId": contract_id,
            "action": action,
        }
        if comment:
            params["comment"] = comment
        return await self.call("cacp/contract/respond", params)

    async def get_contract(
        self,
        project_id: str,
        contract_id: str,
        include_history: bool = False,
    ) -> Dict[str, Any]:
        """Get contract details."""
        return await self.call("cacp/contract/get", {
            "projectId": project_id,
            "contractId": contract_id,
            "includeHistory": include_history,
        })

    # --- Context convenience methods ---

    async def share_context(
        self,
        project_id: str,
        context_type: str,
        content: Dict[str, Any],
        related_contracts: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Share a context packet."""
        params = {
            "projectId": project_id,
            "type": context_type,
            "content": content,
        }
        if related_contracts:
            params["relatedContracts"] = related_contracts
        if reply_to:
            params["replyTo"] = reply_to
        return await self.call("cacp/context/share", params)

    async def ask_question(
        self,
        project_id: str,
        question: str,
        options: Optional[List[str]] = None,
        urgent: bool = False,
    ) -> Dict[str, Any]:
        """Ask a question to other agents."""
        return await self.call("cacp/context/askQuestion", {
            "projectId": project_id,
            "question": question,
            "options": options,
            "urgent": urgent,
        })

    async def record_decision(
        self,
        project_id: str,
        decision: str,
        chosen: str,
        rationale: str,
        implications: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record a decision."""
        return await self.call("cacp/context/recordDecision", {
            "projectId": project_id,
            "decision": decision,
            "chosen": chosen,
            "rationale": rationale,
            "implications": implications or [],
        })

    async def list_context(
        self,
        project_id: str,
        context_type: Optional[str] = None,
        contract_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List context packets."""
        params = {"projectId": project_id, "limit": limit}
        if context_type:
            params["type"] = context_type
        if contract_id:
            params["contractId"] = contract_id
        return await self.call("cacp/context/list", params)

    # --- Implementation convenience methods ---

    async def start_implementation(
        self,
        project_id: str,
        contract_id: str,
        plan: str,
        estimated_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Start implementing a contract."""
        return await self.call("cacp/implementation/start", {
            "projectId": project_id,
            "contractId": contract_id,
            "plan": plan,
            "estimatedFiles": estimated_files or [],
        })

    async def complete_implementation(
        self,
        project_id: str,
        contract_id: str,
        files: List[str],
        notes: Optional[str] = None,
        test_endpoint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete an implementation."""
        params = {
            "projectId": project_id,
            "contractId": contract_id,
            "files": files,
        }
        if notes:
            params["notes"] = notes
        if test_endpoint:
            params["testEndpoint"] = test_endpoint
        return await self.call("cacp/implementation/complete", params)

    async def verify_implementation(
        self,
        project_id: str,
        contract_id: str,
        result: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify an implementation."""
        params = {
            "projectId": project_id,
            "contractId": contract_id,
            "result": result,
        }
        if notes:
            params["notes"] = notes
        return await self.call("cacp/implementation/verify", params)
