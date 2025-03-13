import time
from typing import Iterable, cast

from flwr.common import DEFAULT_TTL, Message, Metadata, RecordSet
from flwr.common.constant import SUPERLINK_NODE_ID
from flwr.common.serde import ProtoMessage, message_from_proto, message_to_proto
from flwr.common.typing import Run
from flwr.proto.node_pb2 import Node  # pylint: disable=E0611
from flwr.server.driver import Driver
from loguru import logger
from syft_core import Client
from syft_rpc import rpc, rpc_db
from typing_extensions import Optional


class SyftDriver(Driver):
    """`SyftDriver` class provides an interface to the ServerAppIo API.

    Parameters
    ----------
    state_factory : StateFactory
        A StateFactory embedding a state that this driver can interface with.
    pull_interval : float (default=0.1)
        Sleep duration between calls to `pull_messages`.
    """

    def __init__(self, pull_interval: float = 0.1, client: Client = None) -> None:
        logger.info("Initializing SyftDriver")
        self._client = Client.load() if client is None else client
        self._run: Optional[Run] = None
        self.node = Node(node_id=SUPERLINK_NODE_ID)

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
        return [7, 8, 9]

        # TODO: modify the method to retrive node IDs from all the clients
        # maybe using rpc.broadcast?
        # url = rpc.make_url(self._client.email, app_name="flwr", endpoint="get_nodes")
        # future = rpc.send(
        #     url=url,
        #     body={"run_id": cast(Run, self._run).run_id},
        #     client=self._client,
        # )

        # nodes = future.wait()
        # return [node.node_id for node in nodes]

    def push_messages(self, messages: Iterable[Message]) -> Iterable[str]:
        """Push messages to specified node IDs."""

        # todo - replace with dest node id
        url = rpc.make_url(self._client.email, app_name="flwr", endpoint="messages")

        # Construct Messages
        message_ids = []
        for msg in messages:
            # Check message
            self._check_message(msg)

            # Convert to proto
            msg_proto = message_to_proto(msg)
            future = rpc.send(
                url=url, body=msg_proto.SerializeToString(), client=self._client
            )
            rpc_db.save_future(future=future, namespace="flwr", client=self._client)
            message_ids.append(future.id)

        return message_ids

    def pull_messages(self, message_ids):
        """Pull messages based on message IDs."""

        messages = []
        for msg_id in message_ids:
            future = rpc_db.get_future(future_id=msg_id, client=self._client)
            response = future.resolve()
            if response is None:
                continue

            if not response.body:
                raise ValueError(f"Empty response: {response}")

            msg_proto = ProtoMessage.ParseFromString(response.body)
            message = message_from_proto(msg_proto)
            messages.append(message)
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
        ret: list[Message] = []
        while timeout is None or time.time() < end_time:
            res_msgs = self.pull_messages(msg_ids)
            ret.extend(res_msgs)
            msg_ids.difference_update(
                {msg.metadata.reply_to_message for msg in res_msgs}
            )
            if len(msg_ids) == 0:
                break
            # Sleep
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


if __name__ == "__main__":
    client = Client.load()
    logger.info(
        f"Running SyftBox client: {client.email}. SyftBox Folder: {client.workspace.data_dir}"
    )

    driver = SyftDriver(client=client)
    run_id = 2
    driver.set_run(run_id)

    create_message = driver.create_message(
        content=RecordSet(), message_type="test", dst_node_id=0, group_id="test"
    )

    message_ids = driver.push_messages([create_message])
    driver.pull_messages(message_ids)
