"""Test encryption key bootstrapping for FL server and clients."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from syft_crypto.x3dh_bootstrap import ensure_bootstrap

from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server
from syft_flwr.grid import SyftGrid


def test_server_bootstraps_keys(
    full_fl_network, mock_flwr_server_app, mock_flwr_context
):
    """Test that FL server bootstraps encryption keys correctly."""
    network = full_fl_network
    ds_client = network["ds"]["client"]
    do_emails = [network["do1"]["email"], network["do2"]["email"]]

    # Set environment variable for client config
    os.environ["SYFTBOX_CLIENT_CONFIG_PATH"] = str(ds_client.config_path)

    with patch("syft_flwr.flower_server.run_server") as mock_run_server:
        mock_run_server.return_value = mock_flwr_context

        # Call the server function
        syftbox_flwr_server(
            server_app=mock_flwr_server_app,
            context=mock_flwr_context,
            datasites=do_emails,
            app_name="test_fl_app",
        )

        # Verify server was called with bootstrapped client
        assert mock_run_server.called
        call_args = mock_run_server.call_args[0]

        # Extract the SyftGrid from the call
        syft_grid = call_args[0]
        assert isinstance(syft_grid, SyftGrid)

        # Verify the client has been bootstrapped (has keys)
        # Check that DID document exists
        did_path = ds_client.datasite_path / "public" / "did.json"
        assert did_path.exists(), "DID document should be created after bootstrap"

        # Verify DID document structure
        with open(did_path) as f:
            did_doc = json.load(f)

        assert "id" in did_doc
        assert network["ds"]["email"] in did_doc["id"]
        assert "authentication" in did_doc
        assert len(did_doc["authentication"]) > 0


def test_client_bootstraps_keys(
    full_fl_network, mock_flwr_client_app, mock_flwr_context
):
    """Test that FL clients bootstrap encryption keys correctly."""
    network = full_fl_network
    do1_client = network["do1"]["client"]

    # Set environment variable for client config
    os.environ["SYFTBOX_CLIENT_CONFIG_PATH"] = str(do1_client.config_path)

    with patch("syft_flwr.flower_client.SyftEvents") as MockSyftEvents:
        # Create a mock SyftEvents instance
        mock_box = MagicMock()
        mock_box.client = do1_client
        mock_box._stop_event = MagicMock()
        mock_box.on_request = MagicMock(return_value=lambda x: x)
        mock_box.run_forever = MagicMock(side_effect=lambda: mock_box._stop_event.set())

        MockSyftEvents.return_value = mock_box

        # Call the client function (it will return immediately due to mock)
        syftbox_flwr_client(
            client_app=mock_flwr_client_app,
            context=mock_flwr_context,
            app_name="test_fl_app",
        )

        # Verify SyftEvents was created with correct parameters
        assert MockSyftEvents.called
        call_kwargs = MockSyftEvents.call_args.kwargs

        # Verify client was passed and is bootstrapped
        assert "client" in call_kwargs
        client = call_kwargs["client"]

        # Check that DID document exists for the client
        did_path = client.datasite_path / "public" / "did.json"
        assert did_path.exists(), "Client DID document should exist after bootstrap"

        # Verify DID document structure
        with open(did_path) as f:
            did_doc = json.load(f)

        assert "id" in did_doc
        assert network["do1"]["email"] in did_doc["id"]


def test_ensure_bootstrap_creates_keys_and_did(rds_stack_ds):
    """Test that ensure_bootstrap creates keys and DID document."""
    client = rds_stack_ds.client

    # Bootstrap the client
    bootstrapped_client = ensure_bootstrap(client)

    # Verify DID document exists
    did_path = bootstrapped_client.datasite_path / "public" / "did.json"
    assert did_path.exists(), "DID document should be created"

    # Verify DID document has correct structure
    with open(did_path) as f:
        did_doc = json.load(f)

    assert "id" in did_doc
    assert "did:key:" in did_doc["id"]
    assert "authentication" in did_doc
    assert len(did_doc["authentication"]) > 0
    assert "publicKeyJwk" in did_doc["authentication"][0]

    # Verify private keys exist
    pvt_key_dir = Path.home() / ".syftbox"
    pvt_key_files = list(pvt_key_dir.glob("*/pvt.jwks.json"))
    assert len(pvt_key_files) > 0, "Private key file should exist"


def test_multiple_clients_bootstrap_independently(full_fl_network):
    """Test that multiple clients can bootstrap independently with unique keys."""
    network = full_fl_network

    # Bootstrap all three clients
    clients_info = [
        (network["ds"]["email"], network["ds"]["client"]),
        (network["do1"]["email"], network["do1"]["client"]),
        (network["do2"]["email"], network["do2"]["client"]),
    ]

    bootstrapped_clients = []
    dids = []

    for email, client in clients_info:
        # Bootstrap each client
        bootstrapped = ensure_bootstrap(client)
        bootstrapped_clients.append((email, bootstrapped))

        # Verify DID document exists
        did_path = bootstrapped.datasite_path / "public" / "did.json"
        assert did_path.exists(), f"DID document should exist for {email}"

        # Read and verify DID structure
        with open(did_path) as f:
            did_doc = json.load(f)

        assert "id" in did_doc
        assert "authentication" in did_doc
        dids.append(did_doc["id"])

    # Verify all clients have unique DIDs
    assert len(set(dids)) == 3, "All clients should have unique DIDs"

    # Verify each DID is properly formatted
    for did in dids:
        assert did.startswith(
            "did:key:"
        ), f"DID should start with 'did:key:' but got {did}"


def test_bootstrap_idempotent(rds_stack_ds):
    """Test that bootstrapping is idempotent (safe to call multiple times)."""
    client = rds_stack_ds.client

    # Bootstrap once
    bootstrapped1 = ensure_bootstrap(client)
    did_path = bootstrapped1.datasite_path / "public" / "did.json"

    with open(did_path) as f:
        did_doc1 = json.load(f)

    # Bootstrap again
    _ = ensure_bootstrap(bootstrapped1)

    with open(did_path) as f:
        did_doc2 = json.load(f)

    # Verify DID hasn't changed
    assert (
        did_doc1["id"] == did_doc2["id"]
    ), "DID should remain the same after re-bootstrap"
    assert (
        did_doc1["authentication"][0]["publicKeyJwk"]
        == did_doc2["authentication"][0]["publicKeyJwk"]
    ), "Public key should remain the same"
