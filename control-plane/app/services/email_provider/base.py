from abc import ABC, abstractmethod

from app.models.mailbox_connection import MailboxConnection


class EmailProvider(ABC):
    """Common interface implemented per provider (gmail.py, outlook.py — Phase 2).

    The control plane is the only thing that ever calls `send_draft` — the
    agent-side MCP servers only ever create/update drafts, never send.
    """

    @abstractmethod
    def refresh_access_token(self, connection: MailboxConnection) -> str:
        """Return a fresh access token, refreshing via the stored (decrypted)
        refresh token if the cached access token is expired."""

    @abstractmethod
    def send_draft(self, connection: MailboxConnection, provider_draft_id: str) -> str:
        """Send an existing provider-side draft. Returns the sent message id."""
