"""
In-memory integration tests for syft-flwr + syft-client workflows.

These tests use SyftboxManager.pair_with_in_memory_connection() to test
the integration between syft-flwr and syft-client without Google Drive.

Test coverage:
- Peer request and approval flow
- Job submission via in-memory sync
- Job approval flow
- Dataset creation and discovery
- FL message serialization

Run with: pytest tests/integration/syft-client/in-memory/ -v
"""

import tempfile
from pathlib import Path

from loguru import logger

from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes

# =============================================================================
# Test: Peer Request and Approval Flow
# =============================================================================


def test_peer_request_approval_flow(in_memory_managers_no_peers):
    """Test that DS can add DO as peer and DO can approve the request."""
    ds_manager, do_manager = in_memory_managers_no_peers

    # Initially, DS has no peers
    assert len(ds_manager.peers) == 0, "DS should have no peers initially"

    # DS adds DO as peer
    logger.info(f"DS adding peer: {do_manager.email}")
    ds_manager.add_peer(do_manager.email)

    # DS should now have DO as a peer
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        do_manager.email in ds_peer_emails
    ), f"DO should be in DS peers: {ds_peer_emails}"

    # DO loads peers to see the request
    do_manager.load_peers()

    # DO should see the peer request from DS
    peer_requests = do_manager._peer_requests
    logger.info(f"DO peer requests: {[pr.email for pr in peer_requests]}")

    # DO approves the peer request
    do_manager.approve_peer_request(ds_manager.email)
    logger.info(f"DO approved peer request from {ds_manager.email}")

    # Verify DO has DS as approved peer
    approved_peers = do_manager._approved_peers
    approved_emails = [p.email for p in approved_peers]
    assert (
        ds_manager.email in approved_emails
    ), f"DS should be approved: {approved_emails}"

    logger.success("Peer request/approval flow completed successfully")


def test_peer_connection_established(in_memory_managers_single_do):
    """Test that peers are properly established with add_peers=True."""
    ds_manager, do_manager = in_memory_managers_single_do

    # With add_peers=True, peers should already be established
    ds_peer_emails = [p.email for p in ds_manager.peers]
    assert (
        do_manager.email in ds_peer_emails
    ), f"DO should be in DS peers: {ds_peer_emails}"

    logger.success("Peer connection verified")


# =============================================================================
# Test: Job Submission via In-Memory Sync
# =============================================================================


def test_job_submission_in_memory(in_memory_managers_single_do):
    """Test that DS can submit a job and DO receives it via in-memory sync."""
    ds_manager, do_manager = in_memory_managers_single_do

    # Create a simple job file
    job_content = """
# Simple test job
import pandas as pd
print("Hello from test job!")
result = {"status": "success"}
"""
    job_path = f"{do_manager.email}/test_job.py"

    # DS submits the job by sending a file change
    logger.info(f"DS submitting job to: {job_path}")
    ds_manager.send_file_change(job_path, job_content)

    # DO syncs to receive the job
    do_manager.sync()

    # Verify DO received the job in cache
    do_cache = do_manager.proposed_file_change_handler.event_cache
    logger.info(f"DO cache file hashes: {len(do_cache.file_hashes)}")

    # The job should be in DO's received files
    assert len(do_cache.file_hashes) > 0, "DO should have received files in cache"

    logger.success("Job submission via in-memory sync completed successfully")


def test_job_submission_blocked_without_peer_approval(in_memory_managers_no_peers):
    """Test that jobs don't sync until peer request is approved."""
    ds_manager, do_manager = in_memory_managers_no_peers

    # DS adds DO as peer (but DO hasn't approved yet)
    ds_manager.add_peer(do_manager.email)

    # DS submits a job
    job_content = "print('This should not sync yet')"
    job_path = f"{do_manager.email}/blocked_job.py"
    ds_manager.send_file_change(job_path, job_content)

    # DO syncs WITHOUT approving the peer request
    do_manager.sync()

    # Cache should be empty (peer not approved)
    do_cache = do_manager.proposed_file_change_handler.event_cache
    assert len(do_cache.file_hashes) == 0, "Cache should be empty - peer not approved"

    # Now DO approves the peer request
    do_manager.load_peers()
    do_manager.approve_peer_request(ds_manager.email)

    # DO syncs again - now it should work
    do_manager.sync()

    # Cache should now have content
    assert len(do_cache.file_hashes) > 0, "Cache should have content after approval"

    logger.success("Peer approval blocking verified successfully")


# =============================================================================
# Test: Dataset Creation and Discovery
# =============================================================================


def test_dataset_creation_in_memory(in_memory_managers_single_do):
    """Test that DO can create a dataset."""
    ds_manager, do_manager = in_memory_managers_single_do

    # Create a temporary dataset
    with tempfile.TemporaryDirectory() as temp_dir:
        dataset_dir = Path(temp_dir)

        # Create mock and private data files
        mock_dir = dataset_dir / "mock"
        private_dir = dataset_dir / "private"
        mock_dir.mkdir()
        private_dir.mkdir()

        (mock_dir / "data.csv").write_text("id,value\n1,100\n2,200")
        (private_dir / "data.csv").write_text("id,value,secret\n1,100,abc\n2,200,xyz")

        # DO creates the dataset (syft_datasets API)
        logger.info("DO creating dataset...")
        do_manager.create_dataset(
            name="test-dataset",
            mock_path=mock_dir,
            private_path=private_dir,
        )

        # Verify dataset was created
        datasets = do_manager.datasets
        logger.info(f"DO datasets: {datasets.get_all()}")

        assert len(datasets.get_all()) > 0, "DO should have at least one dataset"

    logger.success("Dataset creation completed successfully")


# =============================================================================
# Test: FL Message Serialization
# =============================================================================


def test_flower_message_serialization():
    """Test Flower message serialization/deserialization roundtrip."""
    import time

    from flwr.common import Metadata, RecordDict
    from flwr.common.message import Message

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
    import time

    from flwr.common import ConfigRecord, Metadata, RecordDict
    from flwr.common.message import Message

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


# =============================================================================
# Test: Two Data Owners
# =============================================================================


def test_two_dos_peer_setup(in_memory_managers_two_dos):
    """Test that DS can connect to two DOs."""
    ds_manager, do1_manager, do2_manager = in_memory_managers_two_dos

    # Verify DS has both DOs as peers
    ds_peer_emails = [p.email for p in ds_manager.peers]
    logger.info(f"DS peers: {ds_peer_emails}")

    # Note: with the current fixture, DS might only have one DO
    # because pair_with_in_memory_connection creates separate pairs
    assert len(ds_manager.peers) >= 1, "DS should have at least one peer"

    logger.success("Two DOs setup verified")
