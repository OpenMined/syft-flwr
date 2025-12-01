from pathlib import Path
from typing import Optional

from syft_core import Client

from syft_flwr.client.protocol import SyftFlwrClient


class SyftCoreClient(SyftFlwrClient):
    """Adapter for syft_core.Client - the traditional SyftBox client.

    This adapter wraps syft_core.Client and provides full syft-rpc/syft-crypto/syft-event
    functionality through get_client().
    """

    def __init__(self, client: Client):
        self._client = client

    def __repr__(self) -> str:
        return f"SyftCoreClient(email={self._client.email!r})"

    @classmethod
    def load(cls, filepath: Optional[str] = None) -> "SyftCoreClient":
        """Load client from config file."""
        return cls(Client.load(filepath))

    @property
    def email(self) -> str:
        return self._client.email

    @property
    def config_path(self) -> Path:
        return self._client.config_path

    @property
    def my_datasite(self) -> Path:
        return self._client.my_datasite

    @property
    def datasites(self) -> Path:
        return self._client.datasites

    def app_data(
        self,
        app_name: Optional[str] = None,
        datasite: Optional[str] = None,
    ) -> Path:
        return self._client.app_data(app_name, datasite)

    def get_client(self) -> Client:
        """Return the underlying syft_core.Client for syft-rpc/syft-crypto/syft-event/syftbox stack."""
        return self._client
