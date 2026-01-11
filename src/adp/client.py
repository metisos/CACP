"""
ADP Client - Agent Discovery Protocol client for Metis Agentic Exchange.

CACP agents use ADP for:
1. Registration - Register agent with the exchange
2. Discovery - Find other CACP-compatible agents
3. Verification - Verify agent identities
4. Endpoints - Get authoritative agent endpoints
"""

import aiohttp
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import quote
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default Agentic Exchange URL
DEFAULT_EXCHANGE_URL = "https://agentic-exchange.metisos.co"


@dataclass
class AgentInfo:
    """Parsed agent information from ADP."""
    aid: str
    name: str
    description: str
    endpoint: Optional[str]
    verified: bool
    role: Optional[str] = None
    languages: Optional[List[str]] = None

    @classmethod
    def from_response(cls, data: dict) -> "AgentInfo":
        """Create AgentInfo from ADP response."""
        manifest = data.get("manifest", {})
        metadata = manifest.get("metadata", {})
        cacp_meta = metadata.get("cacp", {})

        # Extract CACP endpoint
        endpoint = None
        invocation = manifest.get("invocation", {})
        for protocol in invocation.get("protocols", []):
            if protocol.get("type") == "cacp":
                endpoint = protocol.get("endpoint")
                break

        return cls(
            aid=data.get("aid", ""),
            name=data.get("name", manifest.get("name", "")),
            description=data.get("description", manifest.get("description", "")),
            endpoint=endpoint,
            verified=data.get("verified", False),
            role=cacp_meta.get("role"),
            languages=cacp_meta.get("languages"),
        )


class ADPClient:
    """
    Client for Metis Agentic Exchange (ADP).

    Used by CACP agents to:
    - Register themselves with the exchange
    - Discover other CACP-compatible agents
    - Verify agent identities before coordination
    """

    def __init__(self, exchange_url: str = DEFAULT_EXCHANGE_URL):
        self.exchange_url = exchange_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search for agents matching query and filters.

        Args:
            query: Natural language search query
            filters: Optional filters (protocols, authentication, etc.)
            limit: Max results to return
            offset: Pagination offset

        Returns:
            Search results with 'results' and 'total' keys
        """
        session = await self._get_session()

        payload = {
            "query": query,
            "filters": filters or {},
            "limit": limit,
            "offset": offset
        }

        logger.info(f"ADP search: {query}")

        try:
            async with session.post(
                f"{self.exchange_url}/v1/search/",
                json=payload
            ) as resp:
                if resp.status != 200:
                    logger.error(f"ADP search failed: {resp.status}")
                    return {"results": [], "total": 0}
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"ADP search error: {e}")
            return {"results": [], "total": 0}

    async def get_agent(self, aid: str) -> Dict[str, Any]:
        """
        Get agent details by AID.

        Args:
            aid: Agent ID (format: aid://domain.com/name@version)

        Returns:
            Full agent data including manifest

        Raises:
            ValueError: If agent not found
        """
        session = await self._get_session()

        # URL encode the AID (contains special chars like :// and @)
        encoded_aid = quote(aid, safe="")

        logger.info(f"ADP get agent: {aid}")

        try:
            async with session.get(
                f"{self.exchange_url}/v1/agents/{encoded_aid}"
            ) as resp:
                if resp.status == 404:
                    raise ValueError(f"Agent not found: {aid}")
                if resp.status != 200:
                    raise ValueError(f"ADP error: {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as e:
            raise ValueError(f"ADP connection error: {e}")

    async def register(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register this agent with ADP.

        Args:
            manifest: Full agent manifest (ADP v2.0 format)

        Returns:
            Registration result with 'success' and 'aid' keys
        """
        session = await self._get_session()

        logger.info(f"ADP register: {manifest.get('aid')}")

        try:
            async with session.post(
                f"{self.exchange_url}/v1/register/",
                json={"manifest": manifest}
            ) as resp:
                result = await resp.json()
                if result.get("success"):
                    logger.info(f"ADP registration successful: {manifest.get('aid')}")
                else:
                    logger.error(f"ADP registration failed: {result}")
                return result
        except aiohttp.ClientError as e:
            logger.error(f"ADP registration error: {e}")
            return {"success": False, "error": str(e)}

    async def browse(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Browse all registered agents.

        Args:
            limit: Max results per page
            offset: Pagination offset

        Returns:
            Paginated list of agents
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.exchange_url}/v1/agents/",
                params={"limit": limit, "offset": offset}
            ) as resp:
                if resp.status != 200:
                    return {"results": [], "total": 0}
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"ADP browse error: {e}")
            return {"results": [], "total": 0}

    async def search_cacp_agents(
        self,
        role: Optional[str] = None,
        languages: Optional[List[str]] = None
    ) -> List[AgentInfo]:
        """
        Convenience method to find CACP-compatible agents.

        Args:
            role: Filter by role (backend, frontend, mobile, etc.)
            languages: Filter by programming languages

        Returns:
            List of AgentInfo for matching agents
        """
        query_parts = ["cacp protocol coding"]
        if role:
            query_parts.append(role)
        if languages:
            query_parts.extend(languages)

        results = await self.search(
            query=" ".join(query_parts),
            filters={"protocols": ["cacp"]}
        )

        agents = []
        for agent_data in results.get("results", []):
            try:
                agent = AgentInfo.from_response(agent_data)
                if agent.endpoint:  # Only include agents with CACP endpoints
                    agents.append(agent)
            except Exception as e:
                logger.warning(f"Failed to parse agent: {e}")

        return agents

    def get_cacp_endpoint(self, agent: Dict[str, Any]) -> Optional[str]:
        """
        Extract CACP endpoint from agent manifest.

        Args:
            agent: Agent data from ADP

        Returns:
            CACP endpoint URL or None
        """
        manifest = agent.get("manifest", {})
        invocation = manifest.get("invocation", {})
        protocols = invocation.get("protocols", [])

        for protocol in protocols:
            if protocol.get("type") == "cacp":
                return protocol.get("endpoint")

        return None

    def build_manifest(
        self,
        aid: str,
        name: str,
        description: str,
        endpoint: str,
        role: str,
        languages: List[str],
        owner: Optional[Dict[str, str]] = None,
        supported_contract_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build an ADP manifest for a CACP agent.

        Args:
            aid: Agent ID (format: aid://domain.com/name@version)
            name: Human-readable agent name
            description: Agent description
            endpoint: CACP endpoint URL
            role: Agent role (backend, frontend, etc.)
            languages: Supported programming languages
            owner: Optional owner info
            supported_contract_types: Optional list of contract types

        Returns:
            Complete ADP manifest
        """
        from datetime import datetime

        return {
            "aid": aid,
            "name": name,
            "description": description,
            "owner": owner or {},
            "capabilities": [
                {
                    "id": "cacp.coordinate",
                    "description": "Cross-repository coordination via CACP v2 protocol",
                    "inputs": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string"},
                            "role": {"type": "string", "enum": ["backend", "frontend", "mobile", "devops"]}
                        }
                    },
                    "outputs": {
                        "type": "object",
                        "properties": {
                            "contracts": {"type": "array"},
                            "implementations": {"type": "array"}
                        }
                    }
                }
            ],
            "invocation": {
                "protocols": [
                    {
                        "type": "cacp",
                        "version": "2.0",
                        "endpoint": endpoint,
                        "transportType": "http"
                    }
                ],
                "authentication": ["api_key"]
            },
            "privacy": {
                "dataRetentionDays": 30,
                "dataRegions": ["US"],
                "dataSharing": "none",
                "gdprCompliant": True,
                "ccpaCompliant": True
            },
            "security": {
                "certifications": [],
            },
            "sla": {
                "availability": 99.5,
                "responseTimeMs": 500
            },
            "pricing": [
                {
                    "plan": "Free",
                    "price": 0,
                    "currency": "USD"
                }
            ],
            "metadata": {
                "cacp": {
                    "role": role,
                    "languages": languages,
                    "supported_contract_types": supported_contract_types or [
                        "api_endpoint",
                        "event_schema",
                        "data_model",
                        "config_spec",
                        "rpc_interface",
                        "custom"
                    ],
                    "max_concurrent_projects": 5
                }
            },
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        }
