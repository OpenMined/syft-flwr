import os
from pathlib import Path
from typing import Optional

from syft_flwr.client.protocol import SyftFlwrClient


class SyftP2PClient(SyftFlwrClient):
    """Client for P2P (Google Drive) sync mode using Google Drive API.

    This client is used when FL jobs are submitted via syft_client's
    Google Drive-based sync system.

    Key differences from syft_core:
    - Uses Google Drive API directly (via GDriveFileIO) instead of filesystem paths
    - No RPC/crypto/event - Google Drive handles transport and access control
    - Email comes from environment variable or explicit parameter

    Note: Path properties (my_datasite, datasites, etc.) are kept for compatibility
    but represent logical paths in Google Drive, not local filesystem paths.
    """

    def __init__(self, email: str):
        """Initialize SyftP2PClient.

        Args:
            email: The user's email address for Google Drive access
        """
        self._email = email

    def __repr__(self) -> str:
        return f"SyftP2PClient(email={self._email!r})"

    @classmethod
    def from_env(cls) -> "SyftP2PClient":
        """Create client from environment variables set by job runner.

        Environment variables:
        - SYFTBOX_EMAIL: The DO's email (set by job_runner.py)
        """
        email = os.environ.get("SYFTBOX_EMAIL")

        if not email:
            raise ValueError("SYFTBOX_EMAIL environment variable not set")

        return cls(email=email)

    @property
    def email(self) -> str:
        return self._email

    @property
    def syftbox_folder(self) -> Path:
        # Returns logical path in Google Drive
        return Path("SyftBox")

    @property
    def config_path(self) -> Path:
        # No config file in P2P context
        return Path("SyftBox") / ".config"

    @property
    def my_datasite(self) -> Path:
        # Logical path: SyftBox/{email}/
        return Path("SyftBox") / self._email

    @property
    def datasites(self) -> Path:
        # In Google Drive, datasites root is SyftBox folder
        return Path("SyftBox")

    def app_data(
        self,
        app_name: Optional[str] = None,
        datasite: Optional[str] = None,
    ) -> Path:
        # Logical path: SyftBox/{datasite}/app_data/{app_name}/
        datasite = datasite or self._email
        if app_name:
            return Path("SyftBox") / datasite / "app_data" / app_name
        return Path("SyftBox") / datasite / "app_data"

    def get_client(self) -> "SyftP2PClient":
        """Return self - this IS the client."""
        return self
