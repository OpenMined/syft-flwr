from __future__ import annotations

from loguru import logger
from syft_event import SyftEvents
from syft_event.types import Request

box = SyftEvents("flwr")


@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    logger.info(f"Received request: {request.body}")


if __name__ == "__main__":
    box.run_forever()
