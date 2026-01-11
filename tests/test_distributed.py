"""
Distributed Test - Two Agents with Separate Stores

This test validates the TRUE peer-to-peer architecture:
- Each agent has its OWN MemoryStore
- State is synchronized via JSON-RPC messages
- No shared state between agents

This is the correct architecture for CACP.
"""

import pytest
import asyncio
import httpx
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, ".")

from src.store import MemoryStore
from src.transport import create_app, PeerRegistry


class DistributedTestClient:
    """
    Test client that simulates HTTP calls between agents.

    Each agent has its own store. When agent A broadcasts to agent B,
    this client routes the call to agent B's TestClient.
    """

    def __init__(self, test_client: TestClient, agent_id: str):
        self.client = test_client
        self.agent_id = agent_id

    def call(self, method: str, params: dict) -> dict:
        """Make a JSON-RPC call."""
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


class MockPeerRegistry(PeerRegistry):
    """
    Peer registry that routes calls to TestClients instead of HTTP.

    This allows testing peer-to-peer communication without actual network calls.
    """

    def __init__(self, self_agent_id: str, self_endpoint: str):
        super().__init__(self_agent_id, self_endpoint)
        self.peer_clients: dict[str, TestClient] = {}

    def set_peer_client(self, agent_id: str, client: TestClient):
        """Set the TestClient for a peer (for routing calls)."""
        self.peer_clients[agent_id] = client

    async def call_peer(self, peer, method: str, params: dict):
        """Route call to peer's TestClient."""
        if peer is None:
            return None

        client = self.peer_clients.get(peer.agent_id)
        if not client:
            return None

        response = client.post("/", json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": f"{self.self_agent_id}-test",
        }, headers={
            "X-Agent-ID": self.self_agent_id,
            "X-Source-Endpoint": self.self_endpoint,
        })

        data = response.json()
        if "error" in data:
            return None

        return data.get("result")


@pytest.fixture
def distributed_agents():
    """
    Create two agents with SEPARATE stores and peer registries.

    This is the correct architecture - each agent is independent.
    """
    # Backend agent - own store, own peer registry
    backend_store = MemoryStore()
    backend_peers = MockPeerRegistry("agent-backend", "http://backend:8080")
    backend_app = create_app(
        agent_id="agent-backend",
        repo_name="backend-api",
        repo_role="backend",
        language="python",
        store=backend_store,
        peer_registry=backend_peers,
        self_endpoint="http://backend:8080",
    )
    backend_client = TestClient(backend_app)

    # Frontend agent - own store, own peer registry
    frontend_store = MemoryStore()
    frontend_peers = MockPeerRegistry("agent-frontend", "http://frontend:8081")
    frontend_app = create_app(
        agent_id="agent-frontend",
        repo_name="frontend-app",
        repo_role="frontend",
        language="typescript",
        store=frontend_store,
        peer_registry=frontend_peers,
        self_endpoint="http://frontend:8081",
    )
    frontend_client = TestClient(frontend_app)

    # Register peers with each other
    backend_peers.register_peer("agent-frontend", "http://frontend:8081", "frontend-app")
    frontend_peers.register_peer("agent-backend", "http://backend:8080", "backend-api")

    # Set up routing for mock calls
    backend_peers.set_peer_client("agent-frontend", frontend_client)
    frontend_peers.set_peer_client("agent-backend", backend_client)

    return {
        "backend": {
            "client": DistributedTestClient(backend_client, "agent-backend"),
            "store": backend_store,
            "peers": backend_peers,
        },
        "frontend": {
            "client": DistributedTestClient(frontend_client, "agent-frontend"),
            "store": frontend_store,
            "peers": frontend_peers,
        },
    }


class TestDistributedArchitecture:
    """Test that agents have truly separate state."""

    def test_stores_are_separate(self, distributed_agents):
        """Verify each agent has its own store."""
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # They should be different objects
        assert backend_store is not frontend_store

        # Initially both empty
        assert len(backend_store.list_projects()) == 0
        assert len(frontend_store.list_projects()) == 0

    def test_peer_registries_are_separate(self, distributed_agents):
        """Verify each agent has its own peer registry."""
        backend_peers = distributed_agents["backend"]["peers"]
        frontend_peers = distributed_agents["frontend"]["peers"]

        # They should be different objects
        assert backend_peers is not frontend_peers

        # Each knows about the other
        assert "agent-frontend" in [p.agent_id for p in backend_peers.list_peers()]
        assert "agent-backend" in [p.agent_id for p in frontend_peers.list_peers()]


class TestPeerToPeerSync:
    """Test state synchronization between peers."""

    def test_project_syncs_to_peer(self, distributed_agents):
        """When backend creates project, it should sync to frontend."""
        backend = distributed_agents["backend"]["client"]
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # Backend creates project
        result = backend.call("cacp/project/create", {
            "name": "Sync Test Project",
            "objective": "Test peer sync",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = result["projectId"]

        # Backend should have it
        assert backend_store.get_project(project_id) is not None

        # Frontend should also have it (via sync)
        frontend_project = frontend_store.get_project(project_id)
        assert frontend_project is not None
        assert frontend_project.name == "Sync Test Project"

    def test_contract_syncs_to_peer(self, distributed_agents):
        """When backend proposes contract, it should sync to frontend."""
        backend = distributed_agents["backend"]["client"]
        frontend = distributed_agents["frontend"]["client"]
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # Create project first
        project = backend.call("cacp/project/create", {
            "name": "Contract Sync Test",
            "objective": "Test contract sync",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project["projectId"]

        # Backend proposes contract
        contract = backend.call("cacp/contract/propose", {
            "projectId": project_id,
            "type": "api_endpoint",
            "name": "Test API",
            "content": {"method": "GET", "path": "/test"},
        })
        contract_id = contract["contractId"]

        # Backend should have it
        backend_contract = backend_store.get_contract(project_id, contract_id)
        assert backend_contract is not None

        # Frontend should also have it (via sync)
        frontend_contract = frontend_store.get_contract(project_id, contract_id)
        assert frontend_contract is not None
        assert frontend_contract.name == "Test API"
        assert frontend_contract.status.value == "proposed"

    def test_contract_response_syncs_back(self, distributed_agents):
        """When frontend responds to contract, it should sync back to backend."""
        backend = distributed_agents["backend"]["client"]
        frontend = distributed_agents["frontend"]["client"]
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # Setup: create project and contract
        project = backend.call("cacp/project/create", {
            "name": "Response Sync Test",
            "objective": "Test response sync",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project["projectId"]

        # Frontend joins
        frontend.call("cacp/project/join", {
            "projectId": project_id,
            "repoName": "frontend-app",
            "agentEndpoint": "http://frontend:8081",
        })

        contract = backend.call("cacp/contract/propose", {
            "projectId": project_id,
            "type": "api_endpoint",
            "name": "Response Test API",
            "content": {"method": "POST", "path": "/users"},
        })
        contract_id = contract["contractId"]

        # Frontend responds with agree
        frontend.call("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "agree",
        })

        # Frontend's local store should show agreed
        frontend_contract = frontend_store.get_contract(project_id, contract_id)
        assert frontend_contract.status.value == "agreed"

        # Backend should also see agreed (via sync)
        backend_contract = backend_store.get_contract(project_id, contract_id)
        assert backend_contract.status.value == "agreed"

    def test_context_syncs_between_peers(self, distributed_agents):
        """Context packets should sync between peers."""
        backend = distributed_agents["backend"]["client"]
        frontend = distributed_agents["frontend"]["client"]
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # Setup
        project = backend.call("cacp/project/create", {
            "name": "Context Sync Test",
            "objective": "Test context sync",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project["projectId"]

        frontend.call("cacp/project/join", {
            "projectId": project_id,
            "repoName": "frontend-app",
            "agentEndpoint": "http://frontend:8081",
        })

        # Frontend shares context
        context = frontend.call("cacp/context/share", {
            "projectId": project_id,
            "type": "question",
            "content": {"question": "What auth method?", "urgent": False},
        })
        packet_id = context["packetId"]

        # Frontend should have it
        frontend_packet = frontend_store.get_context(project_id, packet_id)
        assert frontend_packet is not None

        # Backend should also have it (via sync)
        backend_packet = backend_store.get_context(project_id, packet_id)
        assert backend_packet is not None
        assert backend_packet.content["question"] == "What auth method?"


class TestFullDistributedWorkflow:
    """Test complete workflow with distributed agents."""

    def test_full_coordination_separate_stores(self, distributed_agents):
        """
        Full coordination flow with truly separate stores.

        This proves the protocol works without shared state.
        """
        backend = distributed_agents["backend"]["client"]
        frontend = distributed_agents["frontend"]["client"]
        backend_store = distributed_agents["backend"]["store"]
        frontend_store = distributed_agents["frontend"]["store"]

        # Step 1: Backend creates project
        project = backend.call("cacp/project/create", {
            "name": "Full Distributed Test",
            "objective": "Prove distributed architecture works",
            "repos": [
                {"name": "backend-api", "role": "backend", "language": "python"},
                {"name": "frontend-app", "role": "frontend", "language": "typescript"},
            ],
        })
        project_id = project["projectId"]

        # Verify both stores have project
        assert backend_store.get_project(project_id) is not None
        assert frontend_store.get_project(project_id) is not None

        # Step 2: Frontend joins
        frontend.call("cacp/project/join", {
            "projectId": project_id,
            "repoName": "frontend-app",
            "agentEndpoint": "http://frontend:8081",
        })

        # Step 3: Backend proposes contract
        contract = backend.call("cacp/contract/propose", {
            "projectId": project_id,
            "type": "api_endpoint",
            "name": "User API",
            "content": {"method": "GET", "path": "/api/user"},
        })
        contract_id = contract["contractId"]

        # Verify both stores have contract
        assert backend_store.get_contract(project_id, contract_id) is not None
        assert frontend_store.get_contract(project_id, contract_id) is not None

        # Step 4: Frontend agrees
        frontend.call("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "agree",
        })

        # Verify both see agreed status
        assert backend_store.get_contract(project_id, contract_id).status.value == "agreed"
        assert frontend_store.get_contract(project_id, contract_id).status.value == "agreed"

        # Step 5: Both implement
        backend.call("cacp/implementation/start", {
            "projectId": project_id,
            "contractId": contract_id,
            "plan": "Implement backend",
        })
        backend.call("cacp/implementation/complete", {
            "projectId": project_id,
            "contractId": contract_id,
            "files": ["api.py"],
        })

        frontend.call("cacp/implementation/start", {
            "projectId": project_id,
            "contractId": contract_id,
            "plan": "Implement frontend",
        })
        frontend.call("cacp/implementation/complete", {
            "projectId": project_id,
            "contractId": contract_id,
            "files": ["api.ts"],
        })

        # Verify both see implemented
        assert backend_store.get_contract(project_id, contract_id).status.value == "implemented"
        assert frontend_store.get_contract(project_id, contract_id).status.value == "implemented"

        # Step 6: Verify
        backend.call("cacp/implementation/verify", {
            "projectId": project_id,
            "contractId": contract_id,
            "result": "success",
        })

        # Verify both see verified
        assert backend_store.get_contract(project_id, contract_id).status.value == "verified"
        assert frontend_store.get_contract(project_id, contract_id).status.value == "verified"

        # Final check: stores are still separate objects
        assert backend_store is not frontend_store

        print("\n" + "="*60)
        print("SUCCESS: Full workflow completed with SEPARATE stores!")
        print("Each agent maintained its own state, synchronized via protocol.")
        print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
