"""
Integration test for two-agent communication.

This test runs two CACP agents in-memory and verifies they can coordinate.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
import httpx

import sys
sys.path.insert(0, ".")

from src.store import MemoryStore
from src.transport import create_app, CACPClient


class InMemoryClient:
    """Client that talks directly to a TestClient instead of HTTP."""

    def __init__(self, test_client: TestClient, agent_id: str):
        self.client = test_client
        self.agent_id = agent_id

    def call_sync(self, method: str, params: dict) -> dict:
        response = self.client.post("/", json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": "test",
        })
        data = response.json()
        if "error" in data:
            raise Exception(f"RPC Error: {data['error']['message']}")
        return data.get("result", {})


@pytest.fixture
def backend_agent():
    """Create a backend agent."""
    store = MemoryStore()
    app = create_app(
        agent_id="agent-backend",
        repo_name="backend-api",
        repo_role="backend",
        language="python",
        store=store,
    )
    return TestClient(app), store


@pytest.fixture
def frontend_agent():
    """Create a frontend agent."""
    store = MemoryStore()
    app = create_app(
        agent_id="agent-frontend",
        repo_name="frontend-app",
        repo_role="frontend",
        language="typescript",
        store=store,
    )
    return TestClient(app), store


@pytest.fixture
def shared_store():
    """Create a shared store for both agents (simulates distributed state)."""
    return MemoryStore()


@pytest.fixture
def backend_with_shared_store(shared_store):
    """Backend agent with shared store."""
    app = create_app(
        agent_id="agent-backend",
        repo_name="backend-api",
        repo_role="backend",
        language="python",
        store=shared_store,
    )
    return TestClient(app)


@pytest.fixture
def frontend_with_shared_store(shared_store):
    """Frontend agent with shared store."""
    app = create_app(
        agent_id="agent-frontend",
        repo_name="frontend-app",
        repo_role="frontend",
        language="typescript",
        store=shared_store,
    )
    return TestClient(app)


class TestAgentHealth:
    """Test basic agent functionality."""

    def test_health_check(self, backend_agent):
        client, _ = backend_agent
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agentId"] == "agent-backend"

    def test_agent_card(self, backend_agent):
        client, _ = backend_agent
        response = client.get("/.well-known/agent.json")
        assert response.status_code == 200
        data = response.json()
        assert data["protocols"]["cacp"] == "2.0"
        assert data["extensions"]["cacp"]["repo"] == "backend-api"

    def test_list_methods(self, backend_agent):
        client, _ = backend_agent
        response = client.get("/methods")
        assert response.status_code == 200
        methods = response.json()["methods"]
        assert "cacp/project/create" in methods
        assert "cacp/contract/propose" in methods


class TestTwoAgentCoordination:
    """Test two agents coordinating on a project."""

    def test_full_coordination_flow(self, backend_with_shared_store, frontend_with_shared_store):
        backend = InMemoryClient(backend_with_shared_store, "agent-backend")
        frontend = InMemoryClient(frontend_with_shared_store, "agent-frontend")

        # Step 1: Backend creates project
        project_result = backend.call_sync("cacp/project/create", {
            "name": "Test Project",
            "objective": "Test coordination",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project_result["projectId"]
        assert project_result["status"] == "created"

        # Step 2: Frontend joins
        join_result = frontend.call_sync("cacp/project/join", {
            "projectId": project_id,
            "repoName": "frontend-app",
            "agentEndpoint": "http://frontend:8081",
        })
        assert join_result["status"] == "joined"

        # Step 3: Backend proposes contract
        contract_result = backend.call_sync("cacp/contract/propose", {
            "projectId": project_id,
            "type": "api_endpoint",
            "name": "Test Endpoint",
            "content": {
                "method": "POST",
                "path": "/api/test",
                "requestBody": {"type": "object"},
                "responseBody": {"type": "object"},
            },
        })
        contract_id = contract_result["contractId"]
        assert contract_result["status"] == "proposed"

        # Step 4: Frontend agrees
        response_result = frontend.call_sync("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "agree",
        })
        assert response_result["status"] == "agreed"

        # Step 5: Backend shares context
        context_result = backend.call_sync("cacp/context/share", {
            "projectId": project_id,
            "type": "code_snippet",
            "content": {
                "language": "python",
                "file": "test.py",
                "snippet": "print('hello')",
                "explanation": "Test code",
            },
            "relatedContracts": [contract_id],
        })
        assert context_result["status"] == "shared"

        # Step 6: Frontend asks question
        question_result = frontend.call_sync("cacp/context/askQuestion", {
            "projectId": project_id,
            "question": "What format for the response?",
            "options": ["JSON", "XML"],
        })
        assert question_result["status"] == "shared"

        # Step 7: Backend records decision
        decision_result = backend.call_sync("cacp/context/recordDecision", {
            "projectId": project_id,
            "decision": "Response format",
            "chosen": "JSON",
            "rationale": "Industry standard",
            "implications": ["Frontend parses JSON", "Backend returns JSON"],
        })
        assert decision_result["status"] == "shared"

        # Step 8: Both implement
        backend.call_sync("cacp/implementation/start", {
            "projectId": project_id,
            "contractId": contract_id,
            "plan": "Implement endpoint",
        })
        backend.call_sync("cacp/implementation/complete", {
            "projectId": project_id,
            "contractId": contract_id,
            "files": ["src/api.py"],
        })

        frontend.call_sync("cacp/implementation/start", {
            "projectId": project_id,
            "contractId": contract_id,
            "plan": "Implement client",
        })
        complete_result = frontend.call_sync("cacp/implementation/complete", {
            "projectId": project_id,
            "contractId": contract_id,
            "files": ["src/client.ts"],
        })
        assert complete_result["contractStatus"] == "implemented"

        # Step 9: Verify
        verify_result = backend.call_sync("cacp/implementation/verify", {
            "projectId": project_id,
            "contractId": contract_id,
            "result": "success",
        })
        assert verify_result["contractStatus"] == "verified"

        # Final check
        project = backend.call_sync("cacp/project/get", {"projectId": project_id})
        assert len(project["contracts"]) == 1
        assert project["contracts"][0]["status"] == "verified"
        assert len(project["context_history"]) == 3  # code, question, decision


class TestContractNegotiation:
    """Test contract negotiation flow."""

    def test_request_change_flow(self, backend_with_shared_store, frontend_with_shared_store):
        backend = InMemoryClient(backend_with_shared_store, "agent-backend")
        frontend = InMemoryClient(frontend_with_shared_store, "agent-frontend")

        # Create project
        project = backend.call_sync("cacp/project/create", {
            "name": "Negotiation Test",
            "objective": "Test negotiation",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project["projectId"]

        frontend.call_sync("cacp/project/join", {
            "projectId": project_id,
            "repoName": "frontend-app",
            "agentEndpoint": "http://frontend:8081",
        })

        # Backend proposes
        contract = backend.call_sync("cacp/contract/propose", {
            "projectId": project_id,
            "type": "api_endpoint",
            "name": "User Endpoint",
            "content": {"method": "GET", "path": "/user"},
        })
        contract_id = contract["contractId"]

        # Frontend requests change
        response = frontend.call_sync("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "request_change",
            "comment": "Need POST for creating users",
        })
        assert response["contractStatus"] == "negotiating"

        # Backend updates
        update = backend.call_sync("cacp/contract/update", {
            "projectId": project_id,
            "contractId": contract_id,
            "content": {"method": "POST", "path": "/user"},
            "changeNotes": "Changed to POST per frontend request",
        })
        assert update["version"] == 2

        # Frontend agrees
        final = frontend.call_sync("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "agree",
        })
        assert final["contractStatus"] == "agreed"

        # Check history
        contract_detail = backend.call_sync("cacp/contract/get", {
            "projectId": project_id,
            "contractId": contract_id,
            "includeHistory": True,
        })
        assert len(contract_detail["history"]) == 1  # Original version
        assert contract_detail["version"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
