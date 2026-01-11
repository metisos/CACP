#!/usr/bin/env python3
"""
CACP v2 Agent Entry Point

Usage:
    # With config file (recommended for ADP integration)
    python -m src.main --config config/agent-config.yaml

    # With CLI args (for development/testing)
    python -m src.main --port 8080 --repo backend-api --role backend --language python

    # With ADP registration
    python -m src.main --config config/agent-config.yaml --register-adp
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import uvicorn
from dotenv import load_dotenv

from src.store import MemoryStore
from src.transport import create_app, PeerRegistry
from src.adp import ADPClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        import yaml
    except ImportError:
        logger.error("PyYAML required for config files. Install with: pip install pyyaml")
        sys.exit(1)

    with open(config_path) as f:
        return yaml.safe_load(f)


async def register_with_adp(config: Dict[str, Any], endpoint: str) -> bool:
    """Register this agent with Metis Agentic Exchange (ADP)."""
    adp_config = config.get("adp", {})
    agent_config = config.get("agent", {})
    cacp_config = config.get("cacp", {})

    exchange_url = adp_config.get("exchange_url", "https://agentic-exchange.metisos.co")
    adp = ADPClient(exchange_url)

    try:
        manifest = adp.build_manifest(
            aid=agent_config.get("aid"),
            name=agent_config.get("name", "CACP Agent"),
            description=agent_config.get("description", ""),
            endpoint=endpoint,
            role=cacp_config.get("role", "backend"),
            languages=cacp_config.get("languages", ["python"]),
            owner=agent_config.get("owner"),
            supported_contract_types=cacp_config.get("supported_contract_types"),
        )

        result = await adp.register(manifest)
        success = result.get("success", False)

        if success:
            logger.info(f"Registered with ADP: {agent_config.get('aid')}")
        else:
            logger.warning(f"ADP registration failed: {result.get('error', 'Unknown error')}")

        return success

    except Exception as e:
        logger.error(f"ADP registration error: {e}")
        return False
    finally:
        await adp.close()


def main():
    parser = argparse.ArgumentParser(
        description="CACP v2 Agent Server with ADP Integration",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Config file option
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file",
    )

    # CLI options (used if no config file)
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the server on",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Repository name this agent manages",
    )
    parser.add_argument(
        "--role",
        type=str,
        default="backend",
        choices=["frontend", "backend", "mobile", "shared", "infra", "devops"],
        help="Role of the repository",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="python",
        help="Primary language of the repository",
    )
    parser.add_argument(
        "--persist",
        type=str,
        default=None,
        help="Path to persist state (JSON file)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="./workspace",
        help="Path to store received files",
    )
    parser.add_argument(
        "--agent-id",
        type=str,
        default=None,
        help="Agent ID (AID format for ADP, e.g., aid://example.com/agent@1.0.0)",
    )

    # ADP options
    parser.add_argument(
        "--adp-url",
        type=str,
        default="https://agentic-exchange.metisos.co",
        help="Metis Agentic Exchange URL",
    )
    parser.add_argument(
        "--register-adp",
        action="store_true",
        help="Register with ADP on startup",
    )
    parser.add_argument(
        "--require-adp",
        action="store_true",
        help="Require successful ADP registration (exit if fails)",
    )

    args = parser.parse_args()

    # Load config from file if provided
    config: Dict[str, Any] = {}
    if args.config:
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config}")

    # Merge CLI args with config (CLI takes precedence)
    agent_config = config.get("agent", {})
    server_config = config.get("server", {})
    adp_config = config.get("adp", {})
    cacp_config = config.get("cacp", {})

    host = args.host if args.host != "0.0.0.0" else server_config.get("host", "0.0.0.0")
    port = args.port if args.port != 8080 else server_config.get("port", 8080)
    repo = args.repo or cacp_config.get("repo")
    role = args.role if args.role != "backend" else cacp_config.get("role", "backend")
    language = args.language if args.language != "python" else (cacp_config.get("languages", ["python"])[0] if cacp_config.get("languages") else "python")
    agent_id = args.agent_id or agent_config.get("aid") or (f"agent-{repo}" if repo else "agent-default")
    persist_path = args.persist or config.get("persist_path")
    adp_url = args.adp_url if args.adp_url != "https://agentic-exchange.metisos.co" else adp_config.get("exchange_url", "https://agentic-exchange.metisos.co")
    auto_register = args.register_adp or adp_config.get("auto_register", False)
    require_adp = args.require_adp or config.get("mode") == "production"

    # Validate required args
    if not repo:
        parser.error("--repo is required (or set cacp.repo in config)")

    # Build endpoint URL
    endpoint = f"http://{host}:{port}"
    if host == "0.0.0.0":
        # Try to get a better hostname for registration
        import socket
        try:
            hostname = socket.gethostname()
            endpoint = f"http://{hostname}:{port}"
        except Exception:
            pass

    # Initialize store
    if persist_path:
        persist_path = str(Path(persist_path).resolve())
    store = MemoryStore(persist_path=persist_path)

    # Initialize ADP client and peer registry
    adp_client = ADPClient(adp_url)
    peer_registry = PeerRegistry(
        self_agent_id=agent_id,
        self_endpoint=endpoint,
        adp_client=adp_client,
    )

    # Register with ADP if requested
    if auto_register:
        logger.info(f"Registering with ADP at {adp_url}...")
        success = asyncio.run(register_with_adp(config or {
            "agent": {"aid": agent_id, "name": f"CACP Agent ({repo})"},
            "cacp": {"repo": repo, "role": role, "languages": [language]},
            "adp": {"exchange_url": adp_url},
        }, endpoint))

        if not success and require_adp:
            logger.error("ADP registration required but failed. Exiting.")
            sys.exit(1)

    # Create app
    app = create_app(
        agent_id=agent_id,
        repo_name=repo,
        repo_role=role,
        language=language,
        store=store,
        workspace_path=args.workspace,
        peer_registry=peer_registry,
        self_endpoint=endpoint,
    )

    # Start server
    logger.info(f"Starting CACP agent")
    logger.info(f"  Agent ID: {agent_id}")
    logger.info(f"  Repository: {repo}")
    logger.info(f"  Role: {role}")
    logger.info(f"  Language: {language}")
    logger.info(f"  Endpoint: {endpoint}")
    logger.info(f"  ADP Exchange: {adp_url}")
    if persist_path:
        logger.info(f"  Persistence: {persist_path}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
