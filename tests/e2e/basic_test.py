import os
import sys
import threading
import time

import pytest
from loguru import logger

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server

from examples.basic.client_syft_event import box
from examples.basic.server import server_fn
from syft_flwr.driver import SyftDriver

NUM_CLIENTS = 3


def run_server_in_thread(driver, context, app):
    """Run the server in a separate thread."""
    updated_context = run_server(
        driver=driver,
        context=context,
        loaded_server_app=app,
        server_app_dir="./examples/basic",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context


def test_syft_flwr_basic_integration():
    """Test the basic integration between Syft and Flower."""
    # Start the client (this will run the box event handler but not block)
    for i in range(NUM_CLIENTS):
        client_thread = threading.Thread(target=box.run_forever)
        client_thread.daemon = (
            True  # Allow the test to exit even if the thread is running
        )
        client_thread.start()

    # Set up server
    run_id = 12345
    server_app = ServerApp(server_fn=server_fn)

    syft_driver = SyftDriver()
    syft_driver.set_run(run_id)

    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig({"num-server-rounds": 1}),  # Just 1 round for testing
    )

    # Start server in a separate thread
    server_thread = threading.Thread(
        target=run_server_in_thread, args=(syft_driver, context, server_app)
    )
    server_thread.start()

    # Give server time to start
    time.sleep(2)

    # Import and run the client in this thread
    try:
        # Wait for server to complete (maximum 30 seconds)
        server_thread.join(timeout=30)

        # Check if server completed successfully
        assert (
            not server_thread.is_alive()
        ), "Server did not complete in the expected time"

        # Successful if we get here without exceptions
        assert True

    except Exception as e:
        # If any exception occurs, fail the test
        pytest.fail(f"Test failed with exception: {e}")
