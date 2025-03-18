from flwr.common.message import Message
from flwr.common.serde import message_from_proto, message_to_proto
from flwr.proto.message_pb2 import Message as ProtoMessage


def bytes_to_flower_message(data: bytes) -> Message:
    message_pb = ProtoMessage()
    message_pb.ParseFromString(data)
    message = message_from_proto(message_pb)
    return message


def flower_message_to_bytes(message: Message) -> bytes:
    msg_proto = message_to_proto(message)
    return msg_proto.SerializeToString()
