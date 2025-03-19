from __future__ import annotations

import argparse

from flwr.common import Context
from flwr.common.message import Message
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig
from loguru import logger
from syft_core import Client
from syft_event import SyftEvents
from syft_event.types import Request

from examples.basic.client_app import app as client_app
from syft_flwr.serde import bytes_to_flower_message, flower_message_to_bytes

if __name__ == "__main__":
    # Get the config from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sb_conf_path",
        type=str,
        help="Path to the SyftBox configuration file",
        default=None,
    )
    sb_conf_path = parser.parse_args().sb_conf_path

    sb_client = Client.load(sb_conf_path)
    logger.info(f"Started SyftBox Flower Client on: {sb_client.email}")

    box = SyftEvents("flwr", client=sb_client)

    @box.on_request("/messages")
    def handle_messages(request: Request) -> None:
        logger.info(
            f"Received request id: {request.id}, size: {len(request.body)} bytes"
        )
        message: Message = bytes_to_flower_message(request.body)
        run_id = 12345  # same as server
        context = Context(
            run_id=run_id,
            node_id=0,
            node_config=UserConfig(),
            state=RecordSet(),
            run_config=UserConfig(),
        )

        reply_message: Message = client_app(message=message, context=context)
        logger.info(f"Reply message type: {type(reply_message)}")
        res_bytes: bytes = flower_message_to_bytes(reply_message)
        logger.info(f"Reply message size: {len(res_bytes)/2**20} MB")
        return res_bytes

    box.run_forever()
