import flwr
from flwr.common import Metadata
from flwr.common.message import Error, Message
from packaging.version import Version
from typing_extensions import Optional


def flwr_later_than_1_17():
    return Version(flwr.__version__) >= Version("1.17.0")


# Version-dependent imports
if flwr_later_than_1_17():
    from flwr.common.record import RecordDict
    from flwr.server.grid import Grid
else:
    from flwr.common.record import RecordSet as RecordDict
    from flwr.server.driver import Driver as Grid


__all__ = ["Grid", "RecordDict"]


def check_reply_to_field(metadata: Metadata) -> bool:
    """Check if reply_to field is empty based on Flower version."""
    if flwr_later_than_1_17():
        return metadata.reply_to_message_id == ""
    else:
        return metadata.reply_to_message == ""


def create_flwr_message(
    content: RecordDict,
    message_type: str,
    src_node_id: int,
    dst_node_id: int,
    group_id: str,
    run_id: int,
    ttl: Optional[float] = None,
    error: Optional[Error] = None,
    reply_to: Optional[Message] = None,
) -> Message:
    """Create a Flower message with version-compatible parameters."""
    if flwr_later_than_1_17():
        return _create_message_v1_17_plus(
            content,
            message_type,
            dst_node_id,
            group_id,
            ttl,
            error,
            reply_to,
        )
    else:
        return _create_message_pre_v1_17(
            content,
            message_type,
            src_node_id,
            dst_node_id,
            group_id,
            run_id,
            ttl,
            error,
        )


def _create_message_v1_17_plus(
    content: RecordDict,
    message_type: str,
    dst_node_id: int,
    group_id: str,
    ttl: Optional[float],
    error: Optional[Error],
    reply_to: Optional[Message],
) -> Message:
    """Create message for Flower version 1.17+."""
    if reply_to is not None:
        if error is not None:
            return Message(reply_to=reply_to, error=error)
        return Message(content=content, reply_to=reply_to)
    else:
        if error is not None:
            raise ValueError("Error and reply_to cannot both be None")
        return Message(
            content=content,
            dst_node_id=dst_node_id,
            message_type=message_type,
            ttl=ttl,
            group_id=group_id,
        )


def _create_message_pre_v1_17(
    content: RecordDict,
    message_type: str,
    src_node_id: int,
    dst_node_id: int,
    group_id: str,
    run_id: int,
    ttl: Optional[float],
    error: Optional[Error],
) -> Message:
    """Create message for Flower versions before 1.17."""
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

    if error is not None:
        return Message(metadata=metadata, error=error)
    else:
        return Message(metadata=metadata, content=content)
