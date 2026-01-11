"""API Key generation and validation for CACP agents."""

import secrets
import hashlib
from typing import Tuple


def generate_api_key(agent_id: str, environment: str = "live") -> Tuple[str, str]:
    """
    Generate an API key and its hash for storage.

    Args:
        agent_id: Agent identifier (for reference, not included in key)
        environment: "live" or "test"

    Returns:
        Tuple of (api_key, key_hash)
        - api_key: The actual key to give to the agent (store securely)
        - key_hash: SHA-256 hash to store in database
    """
    random_part = secrets.token_urlsafe(24)
    key = f"cacp_sk_{environment}_{random_part}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key, key_hash


def validate_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Validate an API key against a stored hash.

    Args:
        provided_key: Key provided in request
        stored_hash: SHA-256 hash stored in database

    Returns:
        True if valid, False otherwise
    """
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return secrets.compare_digest(provided_hash, stored_hash)


def is_valid_key_format(key: str) -> bool:
    """Check if a key has the correct format."""
    if not key:
        return False
    parts = key.split("_")
    if len(parts) < 4:
        return False
    return parts[0] == "cacp" and parts[1] == "sk" and parts[2] in ("live", "test")
