"""Project invite system for CACP agent onboarding."""

import secrets
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class Invite:
    """Represents a project invitation."""
    code: str
    project_id: str
    repo_name: str
    permissions: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    redeemed: bool = False
    redeemed_by: Optional[str] = None
    redeemed_at: Optional[datetime] = None


class InviteManager:
    """Manages project invitations."""

    def __init__(self):
        self.invites: Dict[str, Invite] = {}

    def create_invite(
        self,
        project_id: str,
        repo_name: str,
        permissions: List[str],
        expires_in_hours: int = 24,
    ) -> str:
        """
        Create a new project invite.

        Args:
            project_id: Project to invite to
            repo_name: Repo the invited agent will claim
            permissions: Permissions to grant
            expires_in_hours: How long the invite is valid

        Returns:
            Invite code string
        """
        # Generate invite code: INV-<project_short>-<random>-<checksum>
        project_short = project_id[:5]
        random_part = secrets.token_urlsafe(6)
        checksum = hashlib.sha256(f"{project_id}{random_part}".encode()).hexdigest()[:2]
        code = f"INV-{project_short}-{random_part}-{checksum}"

        invite = Invite(
            code=code,
            project_id=project_id,
            repo_name=repo_name,
            permissions=permissions,
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
        )

        self.invites[code] = invite
        return code

    def get_invite(self, code: str) -> Optional[Invite]:
        """Get an invite by code."""
        return self.invites.get(code)

    def redeem_invite(self, code: str, agent_id: str) -> Invite:
        """
        Redeem an invite code.

        Args:
            code: Invite code to redeem
            agent_id: Agent redeeming the invite

        Returns:
            The redeemed Invite object

        Raises:
            ValueError: If invite is invalid, expired, or already redeemed
        """
        invite = self.invites.get(code)

        if not invite:
            raise ValueError(f"Invite code not found: {code}")

        if invite.redeemed:
            raise ValueError("Invite has already been redeemed")

        if datetime.utcnow() > invite.expires_at:
            raise ValueError("Invite has expired")

        # Mark as redeemed
        invite.redeemed = True
        invite.redeemed_by = agent_id
        invite.redeemed_at = datetime.utcnow()

        return invite

    def list_invites(self, project_id: Optional[str] = None) -> List[Invite]:
        """List all invites, optionally filtered by project."""
        invites = list(self.invites.values())
        if project_id:
            invites = [i for i in invites if i.project_id == project_id]
        return invites

    def cleanup_expired(self) -> int:
        """Remove expired invites. Returns count of removed invites."""
        now = datetime.utcnow()
        expired = [code for code, inv in self.invites.items() if inv.expires_at < now]
        for code in expired:
            del self.invites[code]
        return len(expired)

    def revoke_invite(self, code: str) -> bool:
        """Revoke an invite. Returns True if found and removed."""
        if code in self.invites:
            del self.invites[code]
            return True
        return False
