"""Project-scoped JWT tokens for CACP authorization."""

import jwt
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


# In production, load from environment or secrets manager
SECRET_KEY = os.getenv("CACP_JWT_SECRET", "cacp-dev-secret-change-in-production")
ALGORITHM = "HS256"


def generate_project_token(
    project_id: str,
    agent_id: str,
    repo_id: str,
    permissions: List[str],
    expires_in_hours: int = 24,
) -> str:
    """
    Generate a project-scoped JWT token.

    Args:
        project_id: Project the token is scoped to
        agent_id: Agent the token is issued to
        repo_id: Repo the agent is assigned to
        permissions: List of permissions granted
        expires_in_hours: Token validity period

    Returns:
        Encoded JWT string
    """
    payload = {
        "sub": agent_id,
        "project_id": project_id,
        "repo_id": repo_id,
        "permissions": permissions,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def validate_project_token(token: str, project_id: str) -> Dict[str, Any]:
    """
    Validate a project token and return its claims.

    Args:
        token: JWT token string
        project_id: Expected project ID

    Returns:
        Token payload/claims

    Raises:
        ValueError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("project_id") != project_id:
            raise ValueError("Token not valid for this project")

        return payload

    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def get_permissions_from_token(token: str) -> List[str]:
    """Extract permissions from a token without full validation."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("permissions", [])
    except jwt.InvalidTokenError:
        return []


# Standard permission sets
PERMISSIONS_READ_ONLY = ["project:read"]
PERMISSIONS_CONTRIBUTOR = [
    "project:read",
    "contract:propose",
    "contract:respond",
    "context:share",
    "implementation:update",
]
PERMISSIONS_FULL = [
    "project:read",
    "project:write",
    "contract:propose",
    "contract:respond",
    "context:share",
    "implementation:update",
    "file:share",
]
