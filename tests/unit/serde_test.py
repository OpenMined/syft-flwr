"""
Unit tests for Flower message serialization/deserialization.

These tests verify syft-flwr's serde functions work correctly with flwr 1.25.0 API.
"""

import time

from flwr.common import ConfigRecord, Metadata, RecordDict
from flwr.common.message import Message
from loguru import logger

from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes


def test_flower_message_serialization():
    """Test Flower message serialization/deserialization roundtrip."""
    # Create a test message (flwr 1.25.0 API)
    metadata = Metadata(
        run_id=12345,
        message_id="test-msg-001",
        src_node_id=1,
        dst_node_id=2,
        reply_to_message_id="",
        group_id="test-group",
        created_at=time.time(),
        ttl=300.0,
        message_type="train",
    )

    content = RecordDict()
    message = Message(metadata=metadata, content=content)

    # Serialize
    serialized = flower_message_to_bytes(message)
    assert isinstance(serialized, bytes), "Serialized message should be bytes"
    assert len(serialized) > 0, "Serialized message should not be empty"

    # Deserialize
    deserialized = bytes_to_flower_message(serialized)
    assert isinstance(deserialized, Message), "Deserialized should be a Message"

    # Verify roundtrip
    assert deserialized.metadata.run_id == message.metadata.run_id
    assert deserialized.metadata.message_id == message.metadata.message_id
    assert deserialized.metadata.src_node_id == message.metadata.src_node_id
    assert deserialized.metadata.dst_node_id == message.metadata.dst_node_id
    assert deserialized.metadata.message_type == message.metadata.message_type

    logger.success("FL message serialization roundtrip successful")


def test_flower_message_serialization_with_content():
    """Test Flower message serialization with actual content."""
    # Create a message with content (flwr 1.25.0 API)
    metadata = Metadata(
        run_id=99999,
        message_id="content-msg-001",
        src_node_id=1,
        dst_node_id=2,
        reply_to_message_id="",
        group_id="",
        created_at=time.time(),
        ttl=60.0,
        message_type="evaluate",
    )

    # Add some config content
    content = RecordDict()
    content["config"] = ConfigRecord({"batch_size": 32, "learning_rate": 0.01})

    message = Message(metadata=metadata, content=content)

    # Roundtrip
    serialized = flower_message_to_bytes(message)
    deserialized = bytes_to_flower_message(serialized)

    # Verify content preserved
    assert "config" in deserialized.content
    config = deserialized.content["config"]
    assert config["batch_size"] == 32
    assert config["learning_rate"] == 0.01

    logger.success("FL message with content serialization successful")
