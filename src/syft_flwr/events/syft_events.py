from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from loguru import logger
from syft_event import SyftEvents as SyftEventsWatcher
from syft_event.types import Request

from syft_flwr.events.protocol import MessageHandler, SyftFlwrEvents

if TYPE_CHECKING:
    from syft_core import Client


class SyftEvents(SyftFlwrEvents):
    """Adapter wrapping syft_event.SyftEvents for traditional SyftBox.

    This adapter provides the syft-extras stack (syft_rpc/syft_crypto/syft_event)
    for FL message handling when running with syft_core.Client.
    """

    def __init__(
        self,
        app_name: str,
        client: Client,
        cleanup_expiry: str = "1d",
        cleanup_interval: str = "1d",
    ) -> None:
        self._client = client
        self._app_name = app_name
        self._events_watcher = SyftEventsWatcher(
            app_name=app_name,
            client=client,
            cleanup_expiry=cleanup_expiry,
            cleanup_interval=cleanup_interval,
        )
        self._handlers: dict[str, MessageHandler] = {}
        logger.debug(f"Initialized SyftEvents for {client.email}")

    @property
    def client_email(self) -> str:
        return self._client.email

    @property
    def app_dir(self) -> Path:
        return self._events_watcher.app_dir

    def on_request(
        self,
        endpoint: str,
        handler: MessageHandler,
        auto_decrypt: bool = True,
        encrypt_reply: bool = False,
    ) -> None:
        """Register handler using SyftEvents' decorator pattern."""
        self._handlers[endpoint] = handler

        @self._events_watcher.on_request(
            endpoint,
            auto_decrypt=auto_decrypt,
            encrypt_reply=encrypt_reply,
        )
        def wrapped_handler(request: Request) -> Optional[Union[str, bytes]]:
            return handler(request.body)

        logger.info(f"Registered handler for endpoint: {endpoint}")

    def run_forever(self) -> None:
        logger.info(f"Starting SyftEvents for {self._client.email}")
        self._events_watcher.run_forever()

    def stop(self) -> None:
        logger.info("Stopping SyftEvents")
        self._events_watcher._stop_event.set()

    @property
    def is_running(self) -> bool:
        return not self._events_watcher._stop_event.is_set()

    @property
    def native_events(self) -> SyftEventsWatcher:
        """Get the underlying SyftEvents instance for advanced operations."""
        return self._events_watcher

    def is_cleanup_running(self) -> bool:
        """Check if the cleanup service is running."""
        return self._events_watcher.is_cleanup_running()
