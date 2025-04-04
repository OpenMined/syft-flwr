import flwr
from flwr.common import Metadata
from flwr.common.message import Message
from packaging.version import Version
from typing_extensions import Optional


def flwr_later_than_1_17():
    return Version(flwr.__version__) >= Version("1.17.0")


# Version-dependent imports
if flwr_later_than_1_17():
    from flwr.common.record import RecordDict
    from flwr.server.grid import Driver
else:
    from flwr.common.record import RecordSet as RecordDict
    from flwr.server.driver import Driver


__all__ = ["Driver", "RecordDict"]


def check_reply_to_field(metadata: Metadata):
    if flwr_later_than_1_17():
        return metadata.reply_to_message_id == ""
    else:
        return metadata.reply_to_message == ""


def create_flwr_message(
    content: RecordDict,
    message_type: str,
    dst_node_id: int,
    group_id: str,
    run_id: int,
    src_node_id: int,
    ttl: Optional[float] = None,
) -> Message:
    if flwr_later_than_1_17():
        return Message(content, dst_node_id, message_type, ttl=ttl, group_id=group_id)
    else:
        from flwr.common import DEFAULT_TTL

        ttl_ = DEFAULT_TTL if ttl is None else ttl
        metadata = Metadata(
            run_id=run_id,
            message_id="",  # Will be set when saving to file
            src_node_id=src_node_id,
            dst_node_id=dst_node_id,
            reply_to_message="",
            group_id=group_id,
            ttl=ttl_,
            message_type=message_type,
        )
        return Message(metadata=metadata, content=content)
