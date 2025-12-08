from __future__ import annotations

import base64
import os
import time

from flwr.common import ConfigRecord
from flwr.common.constant import MessageType
from flwr.common.message import Message
from flwr.common.record import RecordDict
from flwr.common.typing import Run
from flwr.proto.node_pb2 import Node  # pylint: disable=E0611
from flwr.server.grid import Grid
from loguru import logger
from syft_core import Client
from syft_crypto import EncryptedPayload, decrypt_message
from typing_extensions import Dict, Iterable, List, Optional, Tuple, Union, cast

from syft_flwr.client import (
    SyftCoreClient,
    SyftFlwrClient,
    SyftP2PClient,
    create_client,
)
from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED
from syft_flwr.rpc import SyftFlwrRpc, create_rpc
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import check_reply_to_field, create_flwr_message, str_to_int

# this is what superlink super node do
AGGREGATOR_NODE_ID = 1

# env vars
SYFT_FLWR_MSG_TIMEOUT = "SYFT_FLWR_MSG_TIMEOUT"
SYFT_FLWR_POLL_INTERVAL = "SYFT_FLWR_POLL_INTERVAL"


class SyftGrid(Grid):
    """SyftGrid is the server-side message orchestrator for federated learning.

    This class abstracts the RPC layer to support both syft_core and syft_client
    environments. The appropriate RPC adapter is auto-detected based on the client.

    Supported configurations:
    - syft_core: Full syft_rpc/syft_crypto stack with optional encryption
    - syft_client: P2P File-based RPC via Google Drive (no encryption)
    """

    def __init__(
        self,
        app_name: str,
        datasites: Optional[list[str]] = None,
        client: Optional[Union[Client, SyftFlwrClient]] = None,
        rpc: Optional[SyftFlwrRpc] = None,
    ) -> None:
        """Initialize SyftGrid.

        Args:
            app_name: Name of the FL application
            datasites: List of DO email addresses to communicate with
            client: SyftFlwrClient or syft_core.Client (for backward compatibility)
            rpc: RPC adapter for message transport (auto-created if None)

        Note:
            Encryption is only available when using syft_core (SyftCoreClient).
            When using syft_client (SyftP2PClient), encryption is automatically
            disabled and a warning is logged.
        """
        # Handle client setup
        if client is None:
            self._client = create_client()
        elif isinstance(client, SyftFlwrClient):
            self._client = client
        else:
            # Direct syft_core.Client passed - wrap it
            self._client = SyftCoreClient(client)

        # Create or use provided RPC adapter
        if rpc is None:
            self._rpc = create_rpc(
                client=self._client,
                app_name=app_name,
            )
        else:
            self._rpc = rpc

        # Determine encryption capability based on client type
        # Store syft_core.Client separately for encryption operations (only needed for syft_core)
        self._syft_core_client: Optional[Client] = None
        if isinstance(self._client, SyftP2PClient):
            # P2P mode (syft_client) - encryption not available
            self._encryption_enabled = False
            logger.warning(
                "⚠️ Running via syft_client (P2P mode) - no e2e encryption yet"
            )
        elif isinstance(self._client, SyftCoreClient):
            # Traditional SyftBox mode - encryption available
            self._encryption_enabled = (
                os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
            )
            if self._encryption_enabled:
                self._syft_core_client = self._client.get_client()
        else:
            # Unknown client type - disable encryption for safety
            self._encryption_enabled = False
            logger.warning(
                f"⚠️ Unknown client type {type(self._client)}, encryption disabled"
            )

        self._run: Optional[Run] = None
        self.node = Node(node_id=AGGREGATOR_NODE_ID)
        self.datasites = datasites or []
        self.client_map = {str_to_int(ds): ds for ds in self.datasites}
        self.app_name = app_name
        # Track pending messages: message_id -> client_email for debugging
        self._pending_messages: Dict[str, str] = {}

        logger.debug(
            f"Initialize SyftGrid for '{self._client.email}' with datasites: {self.datasites}"
        )
        if self._encryption_enabled:
            logger.info("🔐 End-to-end encryption is ENABLED for FL messages")
        else:
            logger.warning("⚠️ End-to-end encryption is DISABLED for FL messages")

    def get_client_email(self) -> str:
        """Get the email address of the server's SyftFlwrClient.

        Returns:
            Email address as a string
        """
        return self._client.email

    def set_run(self, run_id: int) -> None:
        """Set the run ID for this federated learning session.

        Args:
            run_id: Unique identifier for the FL run/session

        Note:
            In Grpc Grid case, the superlink sets up the run id.
            Here, the run id is set from an external context.
        """
        # Convert to Flower Run object
        self._run = Run.create_empty(run_id)

    @property
    def run(self) -> Run:
        """Get the current Flower Run object.

        Returns:
            A copy of the current Run object with run metadata
        """
        return Run(**vars(cast(Run, self._run)))

    def create_message(
        self,
        content: RecordDict,
        message_type: str,
        dst_node_id: int,
        group_id: str,
        ttl: Optional[float] = None,
    ) -> Message:
        """Create a new Flower message with proper metadata.

        Args:
            content: Message payload as RecordDict (e.g., model parameters, metrics)
            message_type: Type of FL message (e.g., MessageType.TRAIN, MessageType.EVALUATE)
            dst_node_id: Destination node ID (client identifier)
            group_id: Message group identifier for related messages
            ttl: Time-to-live in seconds (optional, for message expiration)

        Returns:
            A Flower Message object ready to be sent to a client

        Note:
            Automatically adds current run_id and server's node_id to metadata.
        """
        return create_flwr_message(
            content=content,
            message_type=message_type,
            dst_node_id=dst_node_id,
            group_id=group_id,
            ttl=ttl,
        )

    def get_node_ids(self) -> list[int]:
        """Get node IDs of all connected FL clients.

        Returns:
            List of integer node IDs representing connected datasites/clients

        Note:
            Node IDs are deterministically generated from datasite email addresses
            using str_to_int() for consistent client identification.
        """
        return list(self.client_map.keys())

    def push_messages(self, messages: Iterable[Message]) -> Iterable[str]:
        """Push FL messages to specified clients asynchronously.

        Args:
            messages: Iterable of Flower Messages to send to clients

        Returns:
            List of future IDs that can be used to retrieve responses
        """
        message_ids = []

        for msg in messages:
            # Prepare message
            dest_datasite, msg_bytes = self._prepare_message(msg)

            # Send message using RPC abstraction
            if self._encryption_enabled:
                future_id = self._send_encrypted_message(msg_bytes, dest_datasite, msg)
            else:
                future_id = self._send_unencrypted_message(
                    msg_bytes, dest_datasite, msg
                )

            if future_id:
                message_ids.append(future_id)
                # Track which client this message was sent to (for debugging)
                self._pending_messages[future_id] = dest_datasite

        return message_ids

    def pull_messages(self, message_ids: List[str]) -> Tuple[Dict[str, Message], set]:
        """Pull response messages from clients using future IDs.

        Args:
            message_ids: List of future IDs from push_messages()

        Returns:
            Tuple of:
            - Dict mapping message_id to Flower Message response (includes both successes and client errors)
            - Set of message_ids that are completed (got response, deserialized successfully, or permanently failed)
        """
        messages = {}
        completed_ids = set()
        responded_clients: set[str] = set()

        for msg_id in message_ids:
            try:
                # Get response using RPC abstraction
                response_body = self._rpc.get_response(msg_id)

                if response_body is None:
                    continue  # Message not ready yet

                # Process the response
                message = self._process_response_body(response_body, msg_id)

                # Always delete the future once we get a response (success or error)
                # This prevents retrying failed messages indefinitely
                self._rpc.delete_future(msg_id)

                # Mark as completed regardless of success/failure
                completed_ids.add(msg_id)

                # Get and remove from pending tracking dict
                client_email = self._pending_messages.pop(msg_id, None)

                if message:
                    messages[msg_id] = message
                    # Track which client this message came from
                    if client_email:
                        responded_clients.add(client_email)

            except Exception as e:
                logger.error(f"❌ Unexpected error pulling message {msg_id}: {e}")
                continue

        # Log summary
        self._log_pull_summary(messages, message_ids, responded_clients)

        return messages, completed_ids

    def send_and_receive(
        self,
        messages: Iterable[Message],
        *,
        timeout: Optional[float] = None,
    ) -> Iterable[Message]:
        """Push messages to specified node IDs and pull the reply messages.

        This method sends messages to their destination nodes and waits for replies.
        It continues polling until all replies are received or timeout is reached.

        Args:
            messages: Messages to send
            timeout: Maximum time to wait for replies (seconds).
                    Can be overridden by SYFT_FLWR_MSG_TIMEOUT env var.

        Returns:
            Collection of reply messages received
        """
        # Get timeout from environment or parameter
        timeout = self._get_timeout(timeout)

        # Push messages and get IDs
        msg_ids = set(self.push_messages(messages))
        if not msg_ids:
            return []

        # Poll for responses
        responses = self._poll_for_responses(msg_ids, timeout)

        return responses.values()

    def send_stop_signal(
        self, group_id: str, reason: str = "Training complete", ttl: float = 60.0
    ) -> List[Message]:
        """Send a stop signal to all connected FL clients.

        Args:
            group_id: Identifier for this group of stop messages
            reason: Human-readable reason for stopping (default: "Training complete")
            ttl: Time-to-live for stop messages in seconds (default: 60.0)

        Returns:
            List of stop Messages that were sent

        Note:
            Used to gracefully terminate FL clients when training completes or
            when the server encounters an error. Clients will shut down upon
            receiving this SYSTEM message with action="stop".
        """
        stop_messages: List[Message] = [
            self.create_message(
                content=RecordDict(
                    {"config": ConfigRecord({"action": "stop", "reason": reason})}
                ),
                message_type=MessageType.SYSTEM,
                dst_node_id=node_id,
                group_id=group_id,
                ttl=ttl,
            )
            for node_id in self.get_node_ids()
        ]
        self.push_messages(stop_messages)

        return stop_messages

    def _check_message(self, message: Message) -> None:
        """Validate a Flower message before sending.

        Args:
            message: The Flower Message to validate

        Raises:
            ValueError: If message metadata is invalid (wrong run_id, src_node_id,
                    missing ttl, or invalid reply_to field)

        Note:
            Ensures message belongs to current run and originates from this server node.
        """
        if not (
            message.metadata.run_id == cast(Run, self._run).run_id
            and message.metadata.src_node_id == self.node.node_id
            and message.metadata.message_id == ""
            and check_reply_to_field(message.metadata)
            and message.metadata.ttl > 0
        ):
            logger.debug(f"Invalid message with metadata: {message.metadata}")
            raise ValueError(f"Invalid message: {message}")

    def _prepare_message(self, msg: Message) -> Tuple[str, bytes]:
        """Prepare a message for sending.

        Returns:
            Tuple of (destination_datasite, message_bytes)

        Raises:
            ValueError: If destination node ID is not in the client map
        """
        run_id = cast(Run, self._run).run_id
        msg.metadata.__dict__["_run_id"] = run_id
        msg.metadata.__dict__["_src_node_id"] = self.node.node_id

        dst_node_id = msg.metadata.dst_node_id
        if dst_node_id not in self.client_map:
            raise ValueError(
                f"Unknown destination node ID {dst_node_id}. "
                f"Known nodes: {list(self.client_map.keys())}. "
                f"Datasites: {self.datasites}"
            )
        dest_datasite = self.client_map[dst_node_id]

        self._check_message(msg)
        msg_bytes = flower_message_to_bytes(msg)

        return dest_datasite, msg_bytes

    def _send_encrypted_message(
        self, msg_bytes: bytes, dest_datasite: str, msg: Message
    ) -> Optional[str]:
        """Send an encrypted message and return future ID if successful."""
        try:
            # Base64 encode for encrypted transmission
            encoded_body = base64.b64encode(msg_bytes).decode("utf-8")

            # Send encrypted message using RPC abstraction
            future_id = self._rpc.send(
                to_email=dest_datasite,
                app_name=self.app_name,
                endpoint="messages",
                body=encoded_body.encode("utf-8"),
                encrypt=True,
            )

            logger.debug(
                f"🔐 Pushed ENCRYPTED message to {dest_datasite} "
                f"with metadata {msg.metadata}; size {len(msg_bytes) / 1024 / 1024:.2f} MB"
            )

            return future_id

        except (KeyError, ValueError) as e:
            # Encryption setup errors - don't retry or fallback
            error_type = (
                "Encryption key" if isinstance(e, KeyError) else "Encryption parameter"
            )
            logger.error(
                f"❌ {error_type} error for {dest_datasite}: {e}. "
                f"Skipping message to node {msg.metadata.dst_node_id}"
            )
            return None

        except Exception as e:
            # Other errors - fallback to unencrypted
            logger.warning(
                f"⚠️ Encryption failed for {dest_datasite}: {e}. "
                f"Falling back to unencrypted transmission"
            )
            return self._send_unencrypted_message(msg_bytes, dest_datasite, msg)

    def _send_unencrypted_message(
        self, msg_bytes: bytes, dest_datasite: str, msg: Message
    ) -> Optional[str]:
        """Send an unencrypted message and return future ID if successful."""
        try:
            # Send unencrypted message using RPC abstraction
            future_id = self._rpc.send(
                to_email=dest_datasite,
                app_name=self.app_name,
                endpoint="messages",
                body=msg_bytes,
                encrypt=False,
            )
            logger.debug(
                f"📤 Pushed PLAINTEXT message to {dest_datasite} "
                f"with metadata {msg.metadata}; size {len(msg_bytes) / 1024 / 1024:.2f} MB"
            )
            return future_id

        except Exception as e:
            logger.error(f"❌ Failed to send message to {dest_datasite}: {e}")
            return None

    def _poll_for_responses(
        self, msg_ids: set, timeout: Optional[float]
    ) -> Dict[str, Message]:
        """Poll for responses until all received or timeout."""
        end_time = time.time() + (timeout if timeout is not None else float("inf"))
        responses = {}
        pending_ids = msg_ids.copy()

        # Get polling interval from environment or use default
        poll_interval = float(os.environ.get(SYFT_FLWR_POLL_INTERVAL, "3"))

        while pending_ids and (timeout is None or time.time() < end_time):
            # Pull available messages
            batch, completed = self.pull_messages(list(pending_ids))
            responses.update(batch)
            # Remove all completed IDs (both successes and failures)
            pending_ids.difference_update(completed)

            if pending_ids:
                time.sleep(poll_interval)  # Configurable polling interval

        # Log any missing responses
        if pending_ids:
            logger.warning(
                f"Timeout reached. {len(pending_ids)} message(s) not received."
            )

        return responses

    def _process_response_body(self, body: bytes, msg_id: str) -> Optional[Message]:
        """Process a single response body and return the deserialized message."""
        if not body:
            logger.warning(f"⚠️ Empty response for message {msg_id}, skipping")
            return None

        response_body = body

        # Try to decrypt if encryption is enabled
        if self._encryption_enabled:
            response_body = self._try_decrypt_response(body, msg_id)

        # Deserialize message
        try:
            message = bytes_to_flower_message(response_body)
        except Exception as e:
            logger.error(
                f"❌ Failed to deserialize message {msg_id}: {e}. "
                f"Message may be corrupted or in incompatible format."
            )
            return None

        # Check for errors in message (but still return it so Flower can handle the failure)
        if message.has_error():
            error = message.error
            logger.error(
                f"❌ Message {msg_id} returned error with code={error.code}, "
                f"reason={error.reason}. Returning error message to Flower for proper failure handling."
            )
        else:
            # Log successful pull only if no error
            encryption_status = (
                "🔐 ENCRYPTED" if self._encryption_enabled else "📥 PLAINTEXT"
            )
            logger.debug(
                f"{encryption_status} Pulled message for {msg_id}, "
                f"metadata: {message.metadata}, "
                f"size: {len(response_body) / 1024 / 1024:.2f} MB"
            )

        # Always return the message (even with errors) so Flower's strategy can handle failures
        return message

    def _try_decrypt_response(self, body: bytes, msg_id: str) -> bytes:
        """Try to decrypt response body if it's encrypted."""
        if self._syft_core_client is None:
            # No syft_core client available for decryption
            return body

        try:
            # Try to parse as encrypted payload
            encrypted_payload = EncryptedPayload.model_validate_json(body.decode())
            # Decrypt the message
            decrypted_body = decrypt_message(
                encrypted_payload, client=self._syft_core_client
            )
            # The decrypted body should be a base64-encoded string
            response_body = base64.b64decode(decrypted_body)
            logger.debug(f"🔓 Successfully decrypted response for message {msg_id}")
            return response_body
        except Exception as e:
            # If decryption fails, assume plaintext
            logger.debug(
                f"📥 Response appears to be plaintext or decryption not needed "
                f"for message {msg_id}: {e}"
            )
            return body

    def _log_pull_summary(
        self,
        messages: Dict[str, Message],
        message_ids: List[str],
        responded_clients: set[str],
    ) -> None:
        """Log summary of pulled messages."""
        if messages:
            clients_str = (
                ", ".join(sorted(responded_clients)) if responded_clients else "unknown"
            )
            if self._encryption_enabled:
                logger.info(
                    f"🔐 Successfully pulled {len(messages)} message(s) from [{clients_str}] (encryption enabled)"
                )
            else:
                logger.info(
                    f"📥 Successfully pulled {len(messages)} message(s) from [{clients_str}]"
                )
        elif message_ids:
            # Get the client emails for pending messages
            pending_clients = [
                self._pending_messages.get(msg_id, "unknown")
                for msg_id in message_ids
                if msg_id in self._pending_messages
            ]
            clients_str = ", ".join(pending_clients) if pending_clients else "unknown"
            logger.debug(
                f"No messages pulled yet from {len(message_ids)} client(s): [{clients_str}] "
                f"(clients may still be processing)"
            )

    def _get_timeout(self, timeout: Optional[float]) -> Optional[float]:
        """Get timeout value from environment or parameter.

        Priority:
        1. Explicit timeout parameter
        2. SYFT_FLWR_MSG_TIMEOUT environment variable
        3. Default: 120 seconds (to prevent indefinite waiting)
        """
        # First check explicit parameter
        if timeout is not None:
            logger.debug(f"Message timeout: {timeout}s (from parameter)")
            return timeout

        # Then check environment variable
        env_timeout = os.environ.get(SYFT_FLWR_MSG_TIMEOUT)
        if env_timeout is not None:
            timeout = float(env_timeout)
            logger.debug(f"Message timeout: {timeout}s (from env var)")
            return timeout

        # Default to 120 seconds to prevent indefinite waiting
        default_timeout = 120.0
        logger.debug(f"Message timeout: {default_timeout}s (default)")
        return default_timeout
