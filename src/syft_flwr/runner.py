from pathlib import Path

from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.driver import SyftDriver
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes

PROJECT_ROOT = Path(__file__).parent.parent.parent


def syftbox_flwr_server(server_app, datasites):
    """Run the Flower ServerApp with SyftBox."""
    run_id = 12345
    syft_driver = SyftDriver(datasites=datasites)
    syft_driver.set_run(run_id)

    context = Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )

    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir=PROJECT_ROOT / "examples" / "quickstart",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context


def syftbox_flwr_client(client_app, aggregator_datasite):
    """Run the Flower ClientApp with SyftBox."""
    box = SyftEvents("flwr")

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body)} bytes"
        )
        message = bytes_to_flower_message(request.body)

        run_id = 12345  # same as server
        context = Context(
            run_id=run_id,
            node_id=0,
            node_config=UserConfig(),
            state=RecordSet(),
            run_config=UserConfig(),
        )

        reply_message = client_app(message=message, context=context)
        logger.info(f"Reply message type: {type(reply_message)}")
        res_bytes = flower_message_to_bytes(reply_message)
        logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
        return res_bytes

    box.run_forever()
