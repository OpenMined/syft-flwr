import os
from pathlib import Path
from typing import Optional

from syft_flwr.client.protocol import SyftFlwrClient


class SyftP2PClient(SyftFlwrClient):
    """Client for P2P (Google Drive/OneDrive) sync mode - flat path structure.

    This client is used when FL jobs are submitted via syft_client's
    Google Drive-based sync system.
    syft_client does NOT use the syft_rpc / syft_crypto / syft_event / syftbox stack.

    Key differences from syft_core:
    - Flat path structure: {syftbox_folder}/{email}/ (no 'datasites/' subdirectory)
    - No RPC/crypto/event - Google Drive handles transport and access control
    - Email and folder path come from environment variables set by job runner
    """

    def __init__(self, email: str, syftbox_folder: Path):
        self._email = email
        self._syftbox_folder = syftbox_folder

    def __repr__(self) -> str:
        return f"SyftP2PClient(email={self._email!r}, syftbox_folder={self._syftbox_folder!r})"

    @classmethod
    def from_env(cls) -> "SyftP2PClient":
        """Create client from environment variables set by job runner.

        Environment variables:
        - SYFTBOX_EMAIL: The DO's email (set by job_runner.py)
        - SYFTBOX_FOLDER: Path to SyftBox folder (set by job_runner.py)
        """
        email = os.environ.get("SYFTBOX_EMAIL")
        syftbox_folder = os.environ.get("SYFTBOX_FOLDER")

        if not email:
            raise ValueError("SYFTBOX_EMAIL environment variable not set")
        if not syftbox_folder:
            raise ValueError("SYFTBOX_FOLDER environment variable not set")

        return cls(email=email, syftbox_folder=Path(syftbox_folder))

    @property
    def email(self) -> str:
        return self._email

    @property
    def syftbox_folder(self) -> Path:
        return self._syftbox_folder

    @property
    def config_path(self) -> Path:
        # No config file in syft_client context - return placeholder
        return self._syftbox_folder / ".config"

    @property
    def my_datasite(self) -> Path:
        # Flat structure: {syftbox_folder}/{email}/
        return self._syftbox_folder / self._email

    @property
    def datasites(self) -> Path:
        # In flat structure, datasites root IS the syftbox_folder
        return self._syftbox_folder

    def app_data(
        self,
        app_name: Optional[str] = None,
        datasite: Optional[str] = None,
    ) -> Path:
        # Flat structure: {syftbox_folder}/{datasite}/app_data/{app_name}/
        datasite = datasite or self._email
        if app_name:
            return self._syftbox_folder / datasite / "app_data" / app_name
        return self._syftbox_folder / datasite / "app_data"

    def get_client(self) -> "SyftP2PClient":
        """Return self - this IS the client."""
        return self
