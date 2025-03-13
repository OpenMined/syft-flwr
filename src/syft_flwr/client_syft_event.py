from __future__ import annotations

from datetime import datetime, timezone
import argparse as arg_parser

from loguru import logger
from pydantic import BaseModel, Field
from syft_event import SyftEvents
from syft_event.types import Request
from syft_core import Client

box = SyftEvents("flwr")

@box.on_request("/messages")
def handle_messages(request: Request) -> None:
    print("Received a request to /messages")
    print(request.body)
    print("\n\n\n")



if __name__ == "__main__":
    box.run_forever()