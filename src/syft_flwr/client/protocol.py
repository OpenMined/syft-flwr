from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class SyftFlwrClient(ABC):
    """Protocol for syft-flwr client implementations.

    This abstraction allows syft-flwr to work with different
    SyftBox client implementations (syft_core, syft_client, etc.)
    """

    @property
    @abstractmethod
    def email(self) -> str:
        """Email of the current user."""
        ...

    @property
    @abstractmethod
    def config_path(self) -> Path:
        """Path to the config file."""
        ...

    @property
    @abstractmethod
    def my_datasite(self) -> Path:
        """Path to the user's datasite directory."""
        ...

    @property
    @abstractmethod
    def datasites(self) -> Path:
        """Path to the datasites root directory."""
        ...

    @abstractmethod
    def app_data(
        self,
        app_name: Optional[str] = None,
        datasite: Optional[str] = None,
    ) -> Path:
        """Get the app data directory path."""
        ...

    @abstractmethod
    def get_client(self) -> Any:
        """Get the underlying client of the underlying communication transport layer.

        Returns:
            - syft_core.Client instance for SyftCoreClient (full RPC/crypto stack)
            - SyftP2PClient instance itself for P2P sync mode (file-based messaging)

        Note:
            Use isinstance() checks in calling code to determine which
            path to take for RPC/encryption operations.
        """
        ...
