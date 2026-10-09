"""Two-step reboot session: Login arms Reboot for a short window."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .telnet import DslTelnetClient, NotLoggedIn

_LOGGER = logging.getLogger(__name__)


class DslSession:
    """Holds the logged-in connection and disarms it when the window ends."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_factory: Callable[[Callable[[], None]], DslTelnetClient],
        arm_window: int,
    ) -> None:
        """Create a disarmed session."""
        self._hass = hass
        self._client_factory = client_factory
        self._arm_window = arm_window
        self._client: DslTelnetClient | None = None
        self._lock = asyncio.Lock()
        self._cancel_expiry: CALLBACK_TYPE | None = None
        self._listeners: list[Callable[[], None]] = []
        self.expires_at: datetime | None = None

    @property
    def armed(self) -> bool:
        """Return True while a logged-in connection is open."""
        return self._client is not None and self._client.logged_in

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        """Call update whenever the armed state changes."""
        self._listeners.append(update)

        @callback
        def remove() -> None:
            self._listeners.remove(update)

        return remove

    async def async_login(self) -> None:
        """Log in (or restart the window if already logged in)."""
        async with self._lock:
            if not self.armed:
                await self._async_disarm()
                client = self._client_factory(self._handle_disconnect)
                await client.login()  # raises AuthError / CannotConnect
                self._client = client
            self._schedule_expiry()
        self._notify()

    async def async_reboot(self) -> None:
        """Send the reboot on the open connection, then disarm."""
        async with self._lock:
            if not self.armed:
                await self._async_disarm()
                self._notify()
                raise NotLoggedIn("Press Login first")
            assert self._client is not None
            try:
                await self._client.reboot()
            finally:
                await self._async_disarm()
        self._notify()

    async def async_close(self) -> None:
        """Disarm and close the connection (entry unload)."""
        async with self._lock:
            await self._async_disarm()
        self._notify()

    def _schedule_expiry(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
        self.expires_at = dt_util.utcnow() + timedelta(seconds=self._arm_window)
        self._cancel_expiry = async_call_later(
            self._hass, self._arm_window, self._handle_expiry
        )

    async def _handle_expiry(self, _now: datetime) -> None:
        self._cancel_expiry = None
        _LOGGER.debug("Reboot window ended; logging out")
        await self.async_close()

    @callback
    def _handle_disconnect(self) -> None:
        """The router hung up while armed."""
        _LOGGER.debug("Router closed the connection; disarming")
        self._hass.async_create_task(self.async_close(), eager_start=False)

    async def _async_disarm(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        self.expires_at = None
        client, self._client = self._client, None
        if client is not None:
            await client.close()

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
