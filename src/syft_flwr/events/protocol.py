from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Union

# Type alias for message handler function
MessageHandler = Callable[[bytes], Optional[Union[str, bytes]]]


class SyftFlwrEvents(ABC):
    """Protocol for syft-flwr event handling implementations.

    This abstraction allows syft-flwr to work with different
    transport/event mechanisms:
    - syft_core: SyftEvents with watchdog file watching + syft_rpc
    - syft_client: P2P File-based polling via Google Drive sync
    """

    @property
    @abstractmethod
    def client_email(self) -> str:
        """Email of the current user."""
        ...

    @property
    @abstractmethod
    def app_dir(self) -> Path:
        """Path to the app data directory."""
        ...

    @abstractmethod
    def on_request(
        self,
        endpoint: str,
        handler: MessageHandler,
        auto_decrypt: bool = True,
        encrypt_reply: bool = False,
    ) -> None:
        """Register a handler for incoming messages at an endpoint.

        Args:
            endpoint: The endpoint path (e.g., "/messages")
            handler: Function that receives message bytes and returns response
            auto_decrypt: Whether to auto-decrypt (only for syft_core)
            encrypt_reply: Whether to encrypt replies (only for syft_core)
        """
        ...

    @abstractmethod
    def run_forever(self) -> None:
        """Start the main event loop and block until stopped."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Signal the event loop to stop."""
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Check if the event loop is currently running."""
        ...
