"""
Peer Registry for CACP Agent-to-Agent Communication

Each agent maintains a registry of known peers. When state changes,
the agent broadcasts updates to all registered peers.

Peers can be discovered via:
1. ADP (Agent Discovery Protocol) - Recommended, uses Metis Agentic Exchange
2. Manual registration - For testing or private networks
3. Direct discovery - Probe endpoint for agent card
"""

import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from src.adp import ADPClient

logger = logging.getLogger(__name__)


@dataclass
class Peer:
    """Represents a known peer agent."""
    agent_id: str  # AID format: aid://domain.com/name@version
    endpoint: str
    repo_name: Optional[str] = None
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_healthy: bool = True
    failed_attempts: int = 0
    verified: bool = False  # True if verified via ADP
    role: Optional[str] = None
    languages: Optional[List[str]] = None


class PeerRegistry:
    """
    Manages peer agents and handles broadcasting state changes.

    Each CACP agent has its own PeerRegistry. When local state changes,
    the agent uses the registry to propagate changes to all peers.

    Supports ADP (Agent Discovery Protocol) for peer discovery.
    """

    def __init__(
        self,
        self_agent_id: str,
        self_endpoint: str,
        timeout: float = 10.0,
        adp_client: Optional["ADPClient"] = None,
    ):
        self.self_agent_id = self_agent_id
        self.self_endpoint = self_endpoint
        self.timeout = timeout
        self.adp = adp_client
        self.peers: Dict[str, Peer] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self):
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # === Peer Registration ===

    def register_peer(
        self,
        agent_id: str,
        endpoint: str,
        repo_name: Optional[str] = None,
        verified: bool = False,
        role: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ):
        """
        Register a peer agent manually.

        Args:
            agent_id: Unique identifier of the peer (AID format recommended)
            endpoint: HTTP endpoint (e.g., "http://server-b:8080")
            repo_name: Name of the repo the peer manages
            verified: Whether this peer is ADP-verified
            role: Agent role (backend, frontend, etc.)
            languages: Supported languages
        """
        if agent_id == self.self_agent_id:
            return  # Don't register self

        self.peers[agent_id] = Peer(
            agent_id=agent_id,
            endpoint=endpoint.rstrip("/"),
            repo_name=repo_name,
            verified=verified,
            role=role,
            languages=languages,
        )
        logger.info(f"Registered peer: {agent_id} at {endpoint} (verified={verified})")

    def unregister_peer(self, agent_id: str):
        """Remove a peer from the registry."""
        if agent_id in self.peers:
            del self.peers[agent_id]
            logger.info(f"Unregistered peer: {agent_id}")

    def get_peer(self, agent_id: str) -> Optional[Peer]:
        """Get a peer by ID."""
        return self.peers.get(agent_id)

    def list_peers(self) -> List[Peer]:
        """List all registered peers."""
        return list(self.peers.values())

    def get_verified_peers(self) -> List[Peer]:
        """List only ADP-verified peers."""
        return [p for p in self.peers.values() if p.verified]

    # === ADP Discovery ===

    async def discover_via_adp(
        self,
        role: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> List[Peer]:
        """
        Discover CACP-compatible peers via ADP (Agentic Exchange).

        Args:
            role: Filter by role (backend, frontend, etc.)
            languages: Filter by programming languages

        Returns:
            List of discovered and registered peers
        """
        if not self.adp:
            logger.warning("No ADP client configured - cannot discover via ADP")
            return []

        logger.info(f"Discovering CACP agents via ADP (role={role}, languages={languages})")

        agents = await self.adp.search_cacp_agents(role=role, languages=languages)

        discovered = []
        for agent in agents:
            if agent.aid == self.self_agent_id:
                continue  # Skip self

            if agent.endpoint:
                self.register_peer(
                    agent_id=agent.aid,
                    endpoint=agent.endpoint,
                    verified=agent.verified,
                    role=agent.role,
                    languages=agent.languages,
                )
                peer = self.peers.get(agent.aid)
                if peer:
                    discovered.append(peer)

        logger.info(f"Discovered {len(discovered)} peers via ADP")
        return discovered

    async def add_peer_by_aid(self, aid: str) -> Optional[Peer]:
        """
        Add a specific peer by AID, fetching details from ADP.

        Args:
            aid: Agent ID (format: aid://domain.com/name@version)

        Returns:
            Peer if found and registered, None otherwise
        """
        if not self.adp:
            logger.warning("No ADP client configured - cannot fetch by AID")
            return None

        try:
            agent_data = await self.adp.get_agent(aid)
            endpoint = self.adp.get_cacp_endpoint(agent_data)

            if not endpoint:
                logger.warning(f"Agent {aid} has no CACP endpoint")
                return None

            # Extract metadata
            manifest = agent_data.get("manifest", {})
            metadata = manifest.get("metadata", {})
            cacp_meta = metadata.get("cacp", {})

            self.register_peer(
                agent_id=aid,
                endpoint=endpoint,
                verified=agent_data.get("verified", False),
                role=cacp_meta.get("role"),
                languages=cacp_meta.get("languages"),
            )

            return self.peers.get(aid)

        except ValueError as e:
            logger.warning(f"Failed to add peer by AID: {e}")
            return None

    # === Direct Discovery (without ADP) ===

    async def discover_peer(self, endpoint: str) -> Optional[Peer]:
        """
        Discover a peer by fetching its agent card directly.

        This is a fallback when ADP is not available.

        Args:
            endpoint: The endpoint to probe

        Returns:
            Peer if discovery successful, None otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{endpoint.rstrip('/')}/.well-known/agent.json")
            response.raise_for_status()
            card = response.json()

            agent_id = card.get("extensions", {}).get("cacp", {}).get("agentId")
            repo_name = card.get("extensions", {}).get("cacp", {}).get("repo")
            role = card.get("extensions", {}).get("cacp", {}).get("role")
            language = card.get("extensions", {}).get("cacp", {}).get("language")

            if agent_id:
                self.register_peer(
                    agent_id=agent_id,
                    endpoint=endpoint,
                    repo_name=repo_name,
                    verified=False,  # Not ADP-verified
                    role=role,
                    languages=[language] if language else None,
                )
                return self.peers.get(agent_id)

        except Exception as e:
            logger.warning(f"Failed to discover peer at {endpoint}: {e}")

        return None

    # === Communication ===

    async def call_peer(self, peer: Peer, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make a JSON-RPC call to a specific peer.

        Args:
            peer: The peer to call
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            Result dict if successful, None if failed
        """
        try:
            client = await self._get_client()
            response = await client.post(
                peer.endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": f"{self.self_agent_id}-{datetime.utcnow().timestamp()}",
                },
                headers={
                    "X-Agent-ID": self.self_agent_id,
                    "X-Source-Endpoint": self.self_endpoint,
                }
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning(f"Peer {peer.agent_id} returned error: {data['error']}")
                return None

            peer.last_seen = datetime.utcnow()
            peer.is_healthy = True
            peer.failed_attempts = 0

            return data.get("result")

        except Exception as e:
            logger.warning(f"Failed to call peer {peer.agent_id}: {e}")
            peer.failed_attempts += 1
            if peer.failed_attempts >= 3:
                peer.is_healthy = False
            return None

    async def broadcast(self, method: str, params: Dict[str, Any], exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Broadcast a message to all healthy peers.

        Args:
            method: JSON-RPC method name
            params: Method parameters
            exclude: List of agent_ids to exclude from broadcast

        Returns:
            Dict mapping agent_id to result (or error message)
        """
        exclude = exclude or []
        results = {}

        # Get healthy peers
        peers_to_call = [
            p for p in self.peers.values()
            if p.is_healthy and p.agent_id not in exclude
        ]

        if not peers_to_call:
            return results

        # Call all peers concurrently
        tasks = [
            self.call_peer(peer, method, params)
            for peer in peers_to_call
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for peer, response in zip(peers_to_call, responses):
            if isinstance(response, Exception):
                results[peer.agent_id] = {"error": str(response)}
            elif response is None:
                results[peer.agent_id] = {"error": "No response"}
            else:
                results[peer.agent_id] = response

        return results

    # === Health Checks ===

    async def health_check_peers(self) -> Dict[str, bool]:
        """
        Check health of all registered peers.

        Returns:
            Dict mapping agent_id to health status
        """
        results = {}

        for peer in self.peers.values():
            try:
                client = await self._get_client()
                response = await client.get(f"{peer.endpoint}/health")
                response.raise_for_status()
                peer.is_healthy = True
                peer.last_seen = datetime.utcnow()
                results[peer.agent_id] = True
            except Exception:
                peer.is_healthy = False
                results[peer.agent_id] = False

        return results
