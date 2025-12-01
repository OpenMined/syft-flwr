from abc import ABC, abstractmethod
from typing import Optional


class SyftFlwrRpc(ABC):
    """Protocol for syft-flwr RPC implementations.

    This abstraction allows syft-flwr to work with different
    transport mechanisms for sending FL messages:
    - syft_core: syft_rpc (using SyftBox Go Client) with futures database
    - syft_client: P2P File-based RPC via Google Drive sync
    """

    @abstractmethod
    def send(
        self,
        to_email: str,
        app_name: str,
        endpoint: str,
        body: bytes,
        encrypt: bool = False,
    ) -> str:
        """Send a message to a recipient.

        Args:
            to_email: Recipient's email address
            app_name: Name of the FL application
            endpoint: RPC endpoint (e.g., "messages")
            body: Message body as bytes
            encrypt: Whether to encrypt the message (syft_core only)

        Returns:
            Future ID for tracking the response
        """
        ...

    @abstractmethod
    def get_response(self, future_id: str) -> Optional[bytes]:
        """Get response for a future ID.

        Args:
            future_id: The ID returned by send()

        Returns:
            Response body as bytes, or None if not ready yet
        """
        ...

    @abstractmethod
    def delete_future(self, future_id: str) -> None:
        """Delete a future after processing its response.

        Args:
            future_id: The ID to delete
        """
        ...
