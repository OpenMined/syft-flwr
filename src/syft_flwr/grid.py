import os
import time
from typing import Iterable, cast

from flwr.common import ConfigRecord
from flwr.common.constant import MessageType
from flwr.common.message import Message
from flwr.common.typing import Run
from flwr.proto.node_pb2 import Node  # pylint: disable=E0611
from loguru import logger
from syft_core import Client
from syft_rpc import rpc, rpc_db
from typing_extensions import Optional

from syft_flwr.flwr_compatibility import (
    Grid,
    RecordDict,
    check_reply_to_field,
    create_flwr_message,
)
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import str_to_int

# this is what superlink super node do
AGGREGATOR_NODE_ID = 1


# env vars
SYFT_FLWR_MSG_TIMEOUT = "SYFT_FLWR_MSG_TIMEOUT"


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
        logger.debug(
            f"Initialize SyftGrid for '{self._client.email}' with datasites: {self.datasites}"
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
            run_id=cast(Run, self._run).run_id,
            src_node_id=self.node.node_id,
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

        Process:
            1. Validates each message metadata
            2. Serializes Flower Message to bytes
            3. Sends via syft_rpc to appropriate datasite
            4. Stores futures for later retrieval

        Note:
            Messages are sent asynchronously; use returned IDs with pull_messages()
            to retrieve responses.
        """
        # Construct Messages
        run_id = cast(Run, self._run).run_id
        message_ids = []
        for msg in messages:
            # Set metadata
            msg.metadata.__dict__["_run_id"] = run_id
            msg.metadata.__dict__["_src_node_id"] = self.node.node_id
            # RPC URL
            dest_datasite = self.client_map[msg.metadata.dst_node_id]
            url = rpc.make_url(
                dest_datasite, app_name=self.app_name, endpoint="messages"
            )
            # Check message
            self._check_message(msg)
            # Serialize message
            msg_bytes = flower_message_to_bytes(msg)
            # Send message
            future = rpc.send(url=url, body=msg_bytes, client=self._client)
            logger.debug(
                f"Pushed message to {url} with metadata {msg.metadata}; size {len(msg_bytes) / 1024 / 1024} (Mb)"
            )
            # Save future
            rpc_db.save_future(
                future=future, namespace=self.app_name, client=self._client
            )
            message_ids.append(future.id)

        return message_ids

    def pull_messages(self, message_ids):
        """Pull response messages from clients using future IDs.

        Args:
            message_ids: List of future IDs from push_messages()

        Returns:
            Dict mapping message_id to Flower Message response

        Process:
            1. Resolves each future to get RPC response
            2. Deserializes response bytes to Flower Message
            3. Handles errors and missing responses gracefully
            4. Cleans up completed futures from storage

        Note:
            - Skips messages that haven't arrived yet (returns None)
            - Logs but skips messages with errors
            - Responses are automatically decrypted if encryption is enabled
        """
        messages = {}

        for msg_id in message_ids:
            future = rpc_db.get_future(future_id=msg_id, client=self._client)
            response = future.resolve()
            if response is None:
                continue

            response.raise_for_status()

            if not response.body:
                raise ValueError(f"Empty response: {response}")

            message: Message = bytes_to_flower_message(response.body)
            if message.has_error():
                error = message.error
                logger.error(
                    f"Message {msg_id} error with code={error.code}, reason={error.reason}"
                )
                continue

            logger.debug(
                f"Pulled message from {response.url} with metadata: {message.metadata}, size: {len(response.body) / 1024 / 1024} (Mb)"
            )
            messages[msg_id] = message
            rpc_db.delete_future(future_id=msg_id, client=self._client)

        return messages

    def send_and_receive(
        self,
        messages: Iterable[Message],
        *,
        timeout: Optional[float] = None,
    ) -> Iterable[Message]:
        """Push messages to specified node IDs and pull the reply messages.

        This method sends a list of messages to their destination node IDs and then
        waits for the replies. It continues to pull replies until either all replies are
        received or the specified timeout duration (in seconds) is exceeded.
        """
        if os.environ.get(SYFT_FLWR_MSG_TIMEOUT) is not None:
            timeout = float(os.environ.get(SYFT_FLWR_MSG_TIMEOUT))
        if timeout is not None:
            logger.debug(
                f"syft_flwr messages timeout = {timeout}: Will move on after {timeout} (s) if no reply is received"
            )
        else:
            logger.debug(
                "syft_flwr messages timeout = None: Will wait indefinitely for replies"
            )

        # Push messages
        msg_ids = set(self.push_messages(messages))

        # Pull messages
        end_time = time.time() + (timeout if timeout is not None else 0.0)
        ret = {}
        while timeout is None or time.time() < end_time:
            res_msgs = self.pull_messages(msg_ids)
            ret.update(res_msgs)
            msg_ids.difference_update(res_msgs.keys())
            if len(msg_ids) == 0:  # All messages received
                break
            time.sleep(3)  # polling interval

        if msg_ids:
            logger.warning(
                f"Timeout reached. {len(msg_ids)} message(s) sent out but not replied."
            )

        return ret.values()

    def send_stop_signal(
        self, group_id: str, reason: str = "Training complete", ttl: float = 60.0
    ) -> list[Message]:
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
        stop_messages: list[Message] = [
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
