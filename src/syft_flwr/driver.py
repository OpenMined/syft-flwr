import time
from typing import Iterable, cast

from flwr.common import DEFAULT_TTL, Metadata, RecordSet
from flwr.common.message import Message
from flwr.common.typing import Run
from flwr.proto.node_pb2 import Node  # pylint: disable=E0611
from flwr.server.driver import Driver
from loguru import logger
from syft_core import Client
from syft_rpc import rpc, rpc_db
from typing_extensions import Optional

from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from .utils import string_to_hash_int
from .constant import AGGREGATOR_NODE_ID


class SyftDriver(Driver):
    def __init__(
        self,
        datasites: list[str] = [],
        client: Client = None,
    ) -> None:
        # logger.info("Initializing SyftDriver")
        self._client = Client.load() if client is None else client
        self._run: Optional[Run] = None
        self.node = Node(node_id=AGGREGATOR_NODE_ID)
        self.datasites = datasites
        self.client_map = self._construct_client_map(self.datasites)

    def _construct_client_map(self, datasites: list[str]) -> dict:
        """Construct a map from node ID to client."""
        return {string_to_hash_int(datasite): datasite for datasite in datasites}

    def set_run(self, run_id: int) -> None:
        # Convert to Flower Run object
        self._run = Run.create_empty(run_id)

        # todo rpc this
        # url = rpc.make_url(
        #     datasite=self._client.email,
        #     app_name="flwr",
        #     endpoint="get_run",
        # )
        # path = url.to_local_path(self._client.datasites)
        # run_file = path / f"run_{run_id}.json"

        # if not run_file.exists():
        #     # Create a new run file
        #     run_file.parent.mkdir(parents=True, exist_ok=True)
        #     run_obj = Run.create_empty(run_id=run_id)
        #     run_data = asdict(run_obj)
        #     run_file.write_text(json.dumps(run_data))

        # # Load run data
        # run_data = Run(**json.loads(run_file.read_text()))

        # if run_data["run_id"] != run_id:
        #     raise RuntimeError(f"Cannot find the run with ID: {run_id}")

    @property
    def run(self) -> Run:
        """Run ID."""
        return Run(**vars(cast(Run, self._run)))

    def create_message(
        self,
        content: RecordSet,
        message_type: str,
        dst_node_id: int,
        group_id: str,
        ttl: Optional[float] = None,
    ) -> Message:
        """Create a new message with specified parameters."""
        ttl_ = DEFAULT_TTL if ttl is None else ttl

        metadata = Metadata(
            run_id=cast(Run, self._run).run_id,
            message_id="",  # Will be set when saving to file
            src_node_id=self.node.node_id,
            dst_node_id=dst_node_id,
            reply_to_message="",
            group_id=group_id,
            ttl=ttl_,
            message_type=message_type,
        )

        return Message(metadata=metadata, content=content)

    def get_node_ids(self) -> list[int]:
        """Get node IDs of all connected nodes."""
        # it is map from datasites to node id
        return list(self.client_map.keys())

    def push_messages(self, messages: Iterable[Message]) -> Iterable[str]:
        """Push messages to specified node IDs."""
        # Construct Messages
        message_ids = []
        for msg in messages:
            # RPC URl
            dest_datasite = self.client_map[msg.metadata.dst_node_id]
            url = rpc.make_url(dest_datasite, app_name="flwr", endpoint="messages")

            # Check message
            self._check_message(msg)
            msg_bytes = flower_message_to_bytes(msg)
            future = rpc.send(url=url, body=msg_bytes, client=self._client)
            rpc_db.save_future(future=future, namespace="flwr", client=self._client)
            message_ids.append(future.id)

        return message_ids

    def pull_messages(self, message_ids):
        """Pull messages based on message IDs."""
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
        received or the specified timeout duration is exceeded.
        """
        # Push messages
        msg_ids = set(self.push_messages(messages))

        # Pull messages
        end_time = time.time() + (timeout if timeout is not None else 0.0)
        ret = {}
        while timeout is None or time.time() < end_time:
            res_msgs = self.pull_messages(msg_ids)
            print("send_and_receive", len(res_msgs), len(msg_ids))
            ret.update(res_msgs)
            msg_ids.difference_update(res_msgs.keys())
            if len(msg_ids) == 0:
                break
            time.sleep(3)
        return ret

    def _check_message(self, message: Message) -> None:
        # Check if the message is valid
        if not (
            # Assume self._run being initialized
            message.metadata.run_id == cast(Run, self._run).run_id
            and message.metadata.src_node_id == self.node.node_id
            and message.metadata.message_id == ""
            and message.metadata.reply_to_message == ""
            and message.metadata.ttl > 0
        ):
            raise ValueError(f"Invalid message: {message}")

