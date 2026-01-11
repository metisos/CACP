from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Callable, Optional, Union
import logging
import asyncio

from src.store import MemoryStore
from src.handlers import (
    ProjectHandlers,
    ContractHandlers,
    ContextHandlers,
    ImplementationHandlers,
    FileHandlers,
)
from src.handlers.sync_handlers import SyncHandlers
from src.transport.peer_registry import PeerRegistry

logger = logging.getLogger(__name__)


class BroadcastingHandlers:
    """
    Wrapper that adds peer broadcasting to handlers.

    When a handler modifies state, this wrapper broadcasts the change
    to all registered peers after the local operation completes.
    """

    def __init__(
        self,
        store: MemoryStore,
        agent_id: str,
        repo_name: str,
        peer_registry: PeerRegistry,
    ):
        self.store = store
        self.agent_id = agent_id
        self.repo_name = repo_name
        self.peers = peer_registry

        # Original handlers
        self._project = ProjectHandlers(store, agent_id, repo_name)
        self._contract = ContractHandlers(store, agent_id, repo_name)
        self._context = ContextHandlers(store, agent_id, repo_name)
        self._impl = ImplementationHandlers(store, agent_id, repo_name)

    # === Project methods with broadcasting ===

    async def create_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create project locally, then broadcast to peers."""
        result = self._project.create(params)
        project_id = result["projectId"]

        # Broadcast to peers
        project = self.store.get_project(project_id)
        if project and self.peers.peers:
            await self.peers.broadcast("cacp/project/sync", {
                "project": project.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    async def join_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Join project locally, then broadcast repo assignment to peers."""
        result = self._project.join(params)
        project_id = params["projectId"]

        # Broadcast repo update to peers
        project = self.store.get_project(project_id)
        if project:
            repo = project.get_repo_by_name(params["repoName"])
            if repo and self.peers.peers:
                await self.peers.broadcast("cacp/repo/sync", {
                    "projectId": project_id,
                    "repo": repo.model_dump(mode="json"),
                    "source_agent": self.agent_id,
                })

        return result

    # === Contract methods with broadcasting ===

    async def propose_contract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Propose contract locally, then broadcast to peers."""
        result = self._contract.propose(params)
        project_id = params["projectId"]
        contract_id = result["contractId"]

        # Broadcast to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    async def respond_contract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Respond to contract locally, then broadcast to peers."""
        result = self._contract.respond(params)
        project_id = params["projectId"]
        contract_id = params["contractId"]

        # Broadcast updated contract to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    async def update_contract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update contract locally, then broadcast to peers."""
        result = self._contract.update(params)
        project_id = params["projectId"]
        contract_id = params["contractId"]

        # Broadcast updated contract to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    # === Context methods with broadcasting ===

    async def share_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Share context locally, then broadcast to peers."""
        result = self._context.share(params)
        project_id = params["projectId"]
        packet_id = result["packetId"]

        # Broadcast to peers
        packet = self.store.get_context(project_id, packet_id)
        if packet and self.peers.peers:
            await self.peers.broadcast("cacp/context/sync", {
                "projectId": project_id,
                "packet": packet.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    # === Implementation methods with broadcasting ===

    async def start_implementation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start implementation locally, then broadcast to peers."""
        result = self._impl.start(params)
        project_id = params["projectId"]
        contract_id = params["contractId"]

        # Broadcast updated contract to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    async def complete_implementation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Complete implementation locally, then broadcast to peers."""
        result = self._impl.complete(params)
        project_id = params["projectId"]
        contract_id = params["contractId"]

        # Broadcast updated contract to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result

    async def verify_implementation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Verify implementation locally, then broadcast to peers."""
        result = self._impl.verify(params)
        project_id = params["projectId"]
        contract_id = params["contractId"]

        # Broadcast updated contract to peers
        contract = self.store.get_contract(project_id, contract_id)
        if contract and self.peers.peers:
            await self.peers.broadcast("cacp/contract/sync", {
                "projectId": project_id,
                "contract": contract.model_dump(mode="json"),
                "source_agent": self.agent_id,
            })

        return result


def create_app(
    agent_id: str,
    repo_name: str,
    repo_role: str,
    language: str,
    store: MemoryStore,
    workspace_path: Optional[str] = None,
    peer_registry: Optional[PeerRegistry] = None,
    self_endpoint: Optional[str] = None,
) -> FastAPI:
    """
    Create a FastAPI application for a CACP agent.

    Args:
        agent_id: Unique identifier for this agent
        repo_name: Name of the repository this agent manages
        repo_role: Role of the repo (frontend, backend, mobile, etc.)
        language: Primary language of the repo
        store: Memory store for LOCAL state management
        workspace_path: Path to save received files
        peer_registry: Registry for peer-to-peer communication
        self_endpoint: This agent's endpoint URL for peer communication
    """
    app = FastAPI(
        title=f"CACP Agent - {repo_name}",
        description=f"Coding Agent Coordination Protocol server for {repo_name}",
        version="2.0.0",
    )

    # CORS middleware for cross-agent communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create peer registry if not provided
    if peer_registry is None:
        peer_registry = PeerRegistry(
            self_agent_id=agent_id,
            self_endpoint=self_endpoint or f"http://localhost:8080",
        )

    # Store peer registry on app for access
    app.state.peer_registry = peer_registry
    app.state.store = store

    # Initialize handlers
    project_handlers = ProjectHandlers(store, agent_id, repo_name)
    contract_handlers = ContractHandlers(store, agent_id, repo_name)
    context_handlers = ContextHandlers(store, agent_id, repo_name)
    impl_handlers = ImplementationHandlers(store, agent_id, repo_name)
    file_handlers = FileHandlers(store, agent_id, repo_name, workspace_path)
    sync_handlers = SyncHandlers(store, agent_id, repo_name)

    # Broadcasting handlers (for methods that modify state)
    broadcasting = BroadcastingHandlers(store, agent_id, repo_name, peer_registry)

    # Method routing table - sync handlers for local-only, async for broadcasting
    sync_methods: Dict[str, Callable] = {
        # Read-only methods (no broadcasting needed)
        "cacp/project/get": project_handlers.get,
        "cacp/project/list": project_handlers.list,
        "cacp/contract/get": contract_handlers.get,
        "cacp/contract/list": contract_handlers.list,
        "cacp/context/list": context_handlers.list,
        "cacp/context/getThread": context_handlers.get_thread,
        "cacp/implementation/getStatus": impl_handlers.get_status,
        # File methods (local only for now)
        "cacp/file/share": file_handlers.share,
        "cacp/file/request": file_handlers.request,
        "cacp/file/listRequests": file_handlers.list_requests,
        "cacp/file/fulfillRequest": file_handlers.fulfill_request,
        # Sync methods (receive broadcasts from peers)
        "cacp/project/sync": sync_handlers.project_sync,
        "cacp/contract/sync": sync_handlers.contract_sync,
        "cacp/context/sync": sync_handlers.context_sync,
        "cacp/repo/sync": sync_handlers.repo_sync,
        "cacp/peer/announce": sync_handlers.peer_announce,
    }

    # Async wrapper functions for convenience methods
    async def ask_question(p):
        return await broadcasting.share_context({
            **p,
            "type": "question",
            "content": {"question": p["question"], "options": p.get("options"), "urgent": p.get("urgent", False)}
        })

    async def record_decision(p):
        return await broadcasting.share_context({
            **p,
            "type": "decision",
            "content": {"decision": p["decision"], "chosen": p["chosen"], "rationale": p["rationale"], "implications": p.get("implications", [])}
        })

    async_methods: Dict[str, Callable] = {
        # Write methods (broadcast to peers)
        "cacp/project/create": broadcasting.create_project,
        "cacp/project/join": broadcasting.join_project,
        "cacp/contract/propose": broadcasting.propose_contract,
        "cacp/contract/respond": broadcasting.respond_contract,
        "cacp/contract/update": broadcasting.update_contract,
        "cacp/context/share": broadcasting.share_context,
        "cacp/context/askQuestion": ask_question,
        "cacp/context/recordDecision": record_decision,
        "cacp/implementation/start": broadcasting.start_implementation,
        "cacp/implementation/complete": broadcasting.complete_implementation,
        "cacp/implementation/verify": broadcasting.verify_implementation,
    }

    @app.post("/")
    async def handle_rpc(request: Request) -> JSONResponse:
        """Main JSON-RPC 2.0 endpoint."""
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            })

        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        # Validate JSON-RPC structure
        if body.get("jsonrpc") != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: jsonrpc must be '2.0'"},
                "id": request_id,
            })

        if not method:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: method is required"},
                "id": request_id,
            })

        # Find handler (check async first, then sync)
        handler = async_methods.get(method) or sync_methods.get(method)
        is_async = method in async_methods

        if not handler:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id,
            })

        # Execute handler
        try:
            if is_async:
                result = await handler(params)
            else:
                result = handler(params)
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id,
            })
        except ValueError as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": f"Invalid params: {e}"},
                "id": request_id,
            })
        except Exception as e:
            logger.exception(f"Error handling {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": f"Server error: {e}"},
                "id": request_id,
            })

    @app.post("/peers/register")
    async def register_peer(request: Request) -> Dict[str, Any]:
        """Register a new peer agent."""
        body = await request.json()
        peer_registry.register_peer(
            agent_id=body["agentId"],
            endpoint=body["endpoint"],
            repo_name=body.get("repoName"),
        )

        # Announce ourselves back
        try:
            await peer_registry.call_peer(
                peer_registry.get_peer(body["agentId"]),
                "cacp/peer/announce",
                {
                    "agentId": agent_id,
                    "endpoint": self_endpoint or f"http://localhost:8080",
                    "repoName": repo_name,
                }
            )
        except Exception:
            pass

        return {
            "status": "registered",
            "peerCount": len(peer_registry.peers),
        }

    @app.get("/peers")
    async def list_peers() -> Dict[str, Any]:
        """List registered peers."""
        return {
            "peers": [
                {
                    "agentId": p.agent_id,
                    "endpoint": p.endpoint,
                    "repoName": p.repo_name,
                    "isHealthy": p.is_healthy,
                    "lastSeen": p.last_seen.isoformat(),
                }
                for p in peer_registry.list_peers()
            ]
        }

    @app.get("/.well-known/agent.json")
    async def agent_card() -> Dict[str, Any]:
        """Return A2A-compatible agent card with CACP extensions."""
        return {
            "name": f"CACP Agent ({repo_name})",
            "description": f"Coding agent for {repo_name} repository",
            "version": "2.0.0",
            "url": self_endpoint or "http://localhost:8080",
            "protocols": {
                "a2a": "0.3",
                "cacp": "2.0",
            },
            "capabilities": [language, repo_role],
            "extensions": {
                "cacp": {
                    "repo": repo_name,
                    "role": repo_role,
                    "language": language,
                    "agentId": agent_id,
                    "supportedContractTypes": [
                        "api_endpoint",
                        "event_schema",
                        "data_model",
                        "config_spec",
                        "rpc_interface",
                        "custom",
                    ],
                    "supportedContextTypes": [
                        "code_snippet",
                        "type_definition",
                        "api_spec",
                        "error_catalog",
                        "env_config",
                        "test_case",
                        "dependency_info",
                        "implementation_status",
                        "question",
                        "decision",
                    ],
                }
            },
        }

    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "agentId": agent_id,
            "repo": repo_name,
            "peerCount": len(peer_registry.peers),
        }

    @app.get("/methods")
    async def list_methods() -> Dict[str, Any]:
        """List available JSON-RPC methods."""
        return {
            "methods": list(sync_methods.keys()) + list(async_methods.keys())
        }

    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on shutdown."""
        await peer_registry.close()

    return app
