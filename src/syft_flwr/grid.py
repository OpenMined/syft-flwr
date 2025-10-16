import base64
import os
import random
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
from syft_rpc import SyftResponse, rpc, rpc_db
from typing_extensions import Dict, Iterable, List, Optional, Tuple, cast

from syft_flwr.consts import SYFT_FLWR_ENCRYPTION_ENABLED
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import check_reply_to_field, create_flwr_message, str_to_int

# this is what superlink super node do
AGGREGATOR_NODE_ID = 1

# env vars
SYFT_FLWR_MSG_TIMEOUT = "SYFT_FLWR_MSG_TIMEOUT"
SYFT_FLWR_POLL_INTERVAL = "SYFT_FLWR_POLL_INTERVAL"


class SyftGrid(Grid):
    def __init__(
        self,
        app_name: str,
        datasites: list[str] = [],
        client: Client = None,
    ) -> None:
        """
        SyftGrid is the server-side message orchestrator for federated learning in syft_flwr.
        It acts as a bridge between Flower's server logic and SyftBox's communication layer:

        Flower Server → SyftGrid → syft_rpc → SyftBox network → FL Clients
                            ↑                                          ↓
                            └──────────── responses ←─────────────────┘

        SyftGrid enables Flower's centralized server to communicate with distributed SyftBox
        clients without knowing the underlying transport details.

        Core functionalities:
        - push_messages(): Sends messages to clients via syft_rpc, returns future IDs
        - pull_messages(): Retrieves responses using futures
        - send_and_receive(): Combines push/pull with timeout handling
        """
        self._client = Client.load() if client is None else client
        self._run: Optional[Run] = None
        self.node = Node(node_id=AGGREGATOR_NODE_ID)
        self.datasites = datasites
        self.client_map = {str_to_int(ds): ds for ds in self.datasites}

        # Check if encryption is enabled (default: True for production)
        self._encryption_enabled = (
            os.environ.get(SYFT_FLWR_ENCRYPTION_ENABLED, "true").lower() != "false"
        )

        logger.debug(
            f"Initialize SyftGrid for '{self._client.email}' with datasites: {self.datasites}"
        )
        if self._encryption_enabled:
            logger.info("🔐 End-to-end encryption is ENABLED for FL messages")
        else:
            logger.warning(
                "⚠️ End-to-end encryption is DISABLED for FL messages (development mode / insecure)"
            )

        self.app_name = app_name

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
            dest_datasite, url, msg_bytes = self._prepare_message(msg)

            # Send message
            if self._encryption_enabled:
                future_id = self._send_encrypted_message(
                    url, msg_bytes, dest_datasite, msg
                )
            else:
                future_id = self._send_unencrypted_message(
                    url, msg_bytes, dest_datasite, msg
                )

            if future_id:
                message_ids.append(future_id)

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

        for msg_id in message_ids:
            try:
                # Get and resolve future
                future = rpc_db.get_future(future_id=msg_id, client=self._client)
                response = future.resolve()

                if response is None:
                    continue  # Message not ready yet

                response.raise_for_status()

                # Process the response
                message = self._process_response(response, msg_id)

                # Always delete the future once we get a response (success or error)
                # This prevents retrying failed messages indefinitely
                rpc_db.delete_future(future_id=msg_id, client=self._client)

                # Mark as completed regardless of success/failure
                completed_ids.add(msg_id)

                if message:
                    messages[msg_id] = message

            except Exception as e:
                logger.error(f"❌ Unexpected error pulling message {msg_id}: {e}")
                continue

        # Log summary
        self._log_pull_summary(messages, message_ids)

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

    def _prepare_message(self, msg: Message) -> Tuple[str, str, bytes]:
        """Prepare a message for sending.

        Returns:
            Tuple of (destination_datasite, url, message_bytes)
        """
        run_id = cast(Run, self._run).run_id
        msg.metadata.__dict__["_run_id"] = run_id
        msg.metadata.__dict__["_src_node_id"] = self.node.node_id

        dest_datasite = self.client_map[msg.metadata.dst_node_id]
        url = rpc.make_url(dest_datasite, app_name=self.app_name, endpoint="messages")

        self._check_message(msg)
        msg_bytes = flower_message_to_bytes(msg)

        return dest_datasite, url, msg_bytes

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 0.1,
        context: str = "",
        check_error=None,
    ):
        """Generic retry logic with exponential backoff and jitter.

        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            context: Context string for logging
            check_error: Optional function to check if error is retryable

        Returns:
            Result of func if successful

        Raises:
            Last exception if all retries fail
        """
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                is_retryable = check_error(e) if check_error else True
                if is_retryable and attempt < max_retries - 1:
                    jitter = random.uniform(0, 0.05)
                    delay = initial_delay * (2**attempt) + jitter
                    logger.debug(
                        f"{context} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.3f}s"
                    )
                    time.sleep(delay)
                else:
                    raise

    def _save_future_with_retry(self, future, dest_datasite: str) -> bool:
        """Save future to database with retry logic for database locks.

        Returns:
            True if saved successfully, False if failed after retries
        """
        try:
            self._retry_with_backoff(
                func=lambda: rpc_db.save_future(
                    future=future, namespace=self.app_name, client=self._client
                ),
                context=f"Database save for {dest_datasite}",
                check_error=lambda e: "database is locked" in str(e).lower(),
            )
            return True
        except Exception as e:
            logger.warning(
                f"⚠️ Failed to save future to database for {dest_datasite}: {e}. "
                f"Message sent but future not persisted."
            )
            return False

    def _send_encrypted_message(
        self, url: str, msg_bytes: bytes, dest_datasite: str, msg: Message
    ) -> Optional[str]:
        """Send an encrypted message and return future ID if successful."""
        try:
            # Send encrypted message
            future = rpc.send(
                url=url,
                body=base64.b64encode(msg_bytes).decode("utf-8"),
                client=self._client,
                encrypt=True,
            )

            logger.debug(
                f"🔐 Pushed ENCRYPTED message to {dest_datasite} at {url} "
                f"with metadata {msg.metadata}; size {len(msg_bytes) / 1024 / 1024:.2f} MB"
            )

            # Save future to database (non-critical - log warning if fails)
            self._save_future_with_retry(future, dest_datasite)
            return future.id

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
            return self._send_unencrypted_message(url, msg_bytes, dest_datasite, msg)

    def _send_unencrypted_message(
        self, url: str, msg_bytes: bytes, dest_datasite: str, msg: Message
    ) -> Optional[str]:
        """Send an unencrypted message and return future ID if successful."""
        try:
            future = rpc.send(url=url, body=msg_bytes, client=self._client)
            logger.debug(
                f"📤 Pushed PLAINTEXT message to {dest_datasite} at {url} "
                f"with metadata {msg.metadata}; size {len(msg_bytes) / 1024 / 1024:.2f} MB"
            )
            rpc_db.save_future(
                future=future, namespace=self.app_name, client=self._client
            )
            return future.id

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

    def _process_response(
        self, response: SyftResponse, msg_id: str
    ) -> Optional[Message]:
        """Process a single response and return the deserialized message."""
        if not response.body:
            logger.warning(f"⚠️ Empty response for message {msg_id}, skipping")
            return None

        response_body = response.body

        # Try to decrypt if encryption is enabled
        if self._encryption_enabled:
            response_body = self._try_decrypt_response(response.body, msg_id)

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
                f"{encryption_status} Pulled message from {response.url} "
                f"with metadata: {message.metadata}, "
                f"size: {len(response_body) / 1024 / 1024:.2f} MB"
            )

        # Always return the message (even with errors) so Flower's strategy can handle failures
        return message

    def _try_decrypt_response(self, body: bytes, msg_id: str) -> bytes:
        """Try to decrypt response body if it's encrypted."""
        try:
            # Try to parse as encrypted payload
            encrypted_payload = EncryptedPayload.model_validate_json(body.decode())
            # Decrypt the message
            decrypted_body = decrypt_message(encrypted_payload, client=self._client)
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
        self, messages: Dict[str, Message], message_ids: List[str]
    ) -> None:
        """Log summary of pulled messages."""
        if messages:
            if self._encryption_enabled:
                logger.info(
                    f"🔐 Successfully pulled {len(messages)} messages (encryption enabled)"
                )
            else:
                logger.info(f"📥 Successfully pulled {len(messages)} messages")
        elif message_ids:
            logger.debug(
                f"No messages pulled yet from {len(message_ids)} attempts "
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
