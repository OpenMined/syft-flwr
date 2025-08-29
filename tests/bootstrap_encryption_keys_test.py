"""Test encryption key bootstrapping for FL server and clients."""

from unittest.mock import MagicMock, patch

from syft_core import Client
from syft_crypto import get_did_document, load_private_keys

from syft_flwr.flower_client import syftbox_flwr_client
from syft_flwr.flower_server import syftbox_flwr_server


def test_syft_flwr_server_bootstrap_key(ds_client: Client) -> None:
    """Test syft_flwr server bootstraps encryption keys."""

    with (
        patch("syft_flwr.utils.Client.load", return_value=ds_client),
        patch("syft_flwr.flower_server.run_server") as mock_run_server,
        patch("syft_flwr.flower_server.SyftGrid") as MockSyftGrid,
    ):
        mock_run_server.return_value = MagicMock()
        mock_grid = MagicMock()
        MockSyftGrid.return_value = mock_grid

        syftbox_flwr_server(
            server_app=MagicMock(),
            context=MagicMock(),
            datasites=["do1@test.org", "do2@test.org"],
            app_name="test_app",
        )

        # Verify SyftGrid was created with bootstrapped client
        MockSyftGrid.assert_called_once()
        grid_call_kwargs = MockSyftGrid.call_args.kwargs
        assert grid_call_kwargs["app_name"] == "flwr/test_app"
        assert grid_call_kwargs["datasites"] == ["do1@test.org", "do2@test.org"]

        # The client passed to SyftGrid should be bootstrapped
        grid_client = grid_call_kwargs["client"]
        did_doc = get_did_document(grid_client, grid_client.email)
        assert did_doc is not None

        # Verify that we can load the private keys
        identity_priv_key, signed_prekey_priv_key = load_private_keys(ds_client)
        assert identity_priv_key is not None
        assert signed_prekey_priv_key is not None


def test_syft_flwr_client_bootstrap_key(do1_client: Client) -> None:
    """Test syft_flwr client bootstraps encryption keys."""

    with (
        patch("syft_flwr.utils.Client.load", return_value=do1_client),
        patch("syft_flwr.flower_client.SyftEvents") as MockSyftEvents,
    ):
        mock_events = MagicMock()
        mock_events.client = do1_client
        mock_events.run_forever = MagicMock()  # Don't actually run forever
        MockSyftEvents.return_value = mock_events

        # Call client - this should bootstrap the client
        syftbox_flwr_client(
            client_app=MagicMock(), context=MagicMock(), app_name="test_app"
        )

        # Check that SyftEvents was called with the bootstrapped client
        MockSyftEvents.assert_called_once()
        call_kwargs = MockSyftEvents.call_args.kwargs

        # Verify that we can load the private keys
        identity_priv_key, signed_prekey_priv_key = load_private_keys(do1_client)
        assert identity_priv_key is not None
        assert signed_prekey_priv_key is not None

        # Verify that the client was bootstrapped
        did_doc = get_did_document(call_kwargs["client"], call_kwargs["client"].email)
        assert did_doc is not None
