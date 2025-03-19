from flwr.client import ClientApp
from flwr.common import Context
from flwr.common.message import Message
from flwr.server import ServerApp
from flwr.server.run_serverapp import run as run_server
from loguru import logger
from syft_core import Client
from syft_event import SyftEvents
from syft_event.types import Request

from syft_flwr.constant import RUN_ID
from syft_flwr.driver import SyftDriver
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes
from syft_flwr.utils import create_context


def syftbox_flwr_server(
    server_app: ServerApp, datasites: list[str], sb_client: Client
) -> Context:
    """Run the Flower ServerApp with SyftBox."""
    syft_driver = SyftDriver(datasites=datasites, client=sb_client)
    syft_driver.set_run(RUN_ID)
    logger.info(f"Started SyftBox Flower Server on: {syft_driver._client.email}")
    context = create_context(run_id=RUN_ID, node_id=0)
    updated_context = run_server(
        driver=syft_driver,
        context=context,
        loaded_server_app=server_app,
        server_app_dir="",
    )
    logger.info(f"Server completed with context: {updated_context}")
    return updated_context


def syftbox_flwr_client(client_app: ClientApp, sb_client: Client) -> None:
    """Run the Flower ClientApp with SyftBox."""

    box = SyftEvents("flwr", client=sb_client)
    logger.info(f"Started SyftBox Flower Client on: {box.client.email}")
    context = create_context(run_id=RUN_ID, node_id=0)

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body)} bytes"
        )
        message: Message = bytes_to_flower_message(request.body)
        reply_message: Message = client_app(message=message, context=context)
        res_bytes: bytes = flower_message_to_bytes(reply_message)
        logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
        return res_bytes

    box.run_forever()
