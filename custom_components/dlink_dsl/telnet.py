"""Minimal asyncio telnet client for D-Link DSL routers.

It can only log in, send the fixed reboot command, and close. There is no
general "run a command" method on purpose.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import re

from .const import (
    CONNECT_TIMEOUT,
    LOGIN_PROMPT,
    PASSWORD_PROMPT,
    PROMPT_TIMEOUT,
    REBOOT_COMMAND,
    REBOOT_TIMEOUT,
    SHELL_PROMPT,
)

_LOGGER = logging.getLogger(__name__)

# Telnet protocol bytes (RFC 854).
IAC = 255  # "Interpret As Command": starts every control sequence
DONT = 254
DO = 253
WONT = 252
WILL = 251
SB = 250  # subnegotiation begin
SE = 240  # subnegotiation end


class DslError(Exception):
    """Base error for the router client."""


class CannotConnect(DslError):
    """The router could not be reached or stopped answering."""


class AuthError(DslError):
    """The router rejected the username or password."""


class NotLoggedIn(DslError):
    """A reboot was requested without a logged-in connection."""


class DslTelnetClient:
    """One telnet connection to the router."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        on_disconnect: Callable[[], None] | None = None,
    ) -> None:
        """Store connection settings; nothing is opened yet."""
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._on_disconnect = on_disconnect
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._buffer = b""
        self._logged_in = False
        self._monitor: asyncio.Task[None] | None = None

    @property
    def logged_in(self) -> bool:
        """Return True while the connection is open and authenticated."""
        return (
            self._logged_in
            and self._writer is not None
            and not self._writer.is_closing()
        )

    async def login(self) -> None:
        """Open the connection and log in, leaving it at the shell prompt."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), CONNECT_TIMEOUT
            )
        except (OSError, TimeoutError) as err:
            raise CannotConnect(f"Cannot connect to {self._host}:{self._port}") from err

        try:
            await self._read_until(LOGIN_PROMPT)
            await self._send(self._username)
            await self._read_until(PASSWORD_PROMPT)
            await self._send(self._password)
            text = await self._read_until(SHELL_PROMPT, LOGIN_PROMPT)
            if LOGIN_PROMPT.search(text):
                raise AuthError("Router rejected the username or password")
        except BaseException:
            await self.close()
            raise
        self._logged_in = True
        # From here on only the monitor reads, so a dropped connection is seen at once.
        self._monitor = asyncio.get_running_loop().create_task(self._watch())
        _LOGGER.debug("Logged in to %s", self._host)

    async def reboot(self) -> None:
        """Send the fixed reboot command on the logged-in connection."""
        if not self.logged_in:
            raise NotLoggedIn("Log in before rebooting")
        self._logged_in = False  # no disconnect callback for the expected drop
        try:
            await self._send(REBOOT_COMMAND)
            # Give the router a moment to act on it; it usually drops the
            # connection. Silence or a drop both mean it is going down.
            if self._monitor is not None:
                await asyncio.wait({self._monitor}, timeout=REBOOT_TIMEOUT)
        finally:
            await self._close_transport()
        _LOGGER.info("Reboot command sent to %s", self._host)

    async def close(self) -> None:
        """Log out if possible and close the connection."""
        if self.logged_in:
            self._logged_in = False
            try:
                await self._send("exit")
            except CannotConnect:
                pass
        self._logged_in = False
        await self._close_transport()

    async def _watch(self) -> None:
        """Discard output while idle and report when the router hangs up."""
        assert self._reader is not None
        try:
            while await self._reader.read(1024):
                pass
        except OSError:
            pass
        if self._logged_in:
            self._logged_in = False
            _LOGGER.debug("Router %s closed the connection", self._host)
            if self._on_disconnect is not None:
                self._on_disconnect()

    async def _close_transport(self) -> None:
        monitor, self._monitor = self._monitor, None
        if monitor is not None and not monitor.done():
            monitor.cancel()
        writer, self._writer, self._reader = self._writer, None, None
        self._buffer = b""
        if writer is None:
            return
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 2)
        except (OSError, TimeoutError):
            pass

    async def _send(self, line: str) -> None:
        if self._writer is None or self._writer.is_closing():
            raise CannotConnect("Connection is closed")
        try:
            self._writer.write(line.encode() + b"\r\n")
            await self._writer.drain()
        except OSError as err:
            raise CannotConnect("Connection lost while sending") from err

    async def _read_until(self, *patterns: re.Pattern[bytes]) -> bytes:
        """Read text until one of the patterns matches the end of the buffer."""
        assert self._reader is not None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + PROMPT_TIMEOUT
        while not any(p.search(self._buffer) for p in patterns):
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise CannotConnect("Timed out waiting for the router")
            try:
                chunk = await asyncio.wait_for(self._reader.read(1024), remaining)
            except TimeoutError as err:
                raise CannotConnect("Timed out waiting for the router") from err
            except OSError as err:
                raise CannotConnect("Connection lost") from err
            if not chunk:
                raise CannotConnect("Router closed the connection")
            self._buffer += await self._negotiate(chunk)
        text, self._buffer = self._buffer, b""
        return text

    async def _negotiate(self, data: bytes) -> bytes:
        """Refuse every telnet option and return the data without IAC sequences."""
        assert self._writer is not None
        text = bytearray()
        replies = bytearray()
        i = 0
        while i < len(data):
            byte = data[i]
            if byte != IAC:
                text.append(byte)
                i += 1
                continue
            if i + 1 >= len(data):
                break
            cmd = data[i + 1]
            if cmd == IAC:  # escaped 0xFF data byte
                text.append(IAC)
                i += 2
            elif cmd in (DO, DONT, WILL, WONT):
                if i + 2 >= len(data):
                    break
                option = data[i + 2]
                if cmd == DO:
                    replies += bytes((IAC, WONT, option))
                elif cmd == WILL:
                    replies += bytes((IAC, DONT, option))
                i += 3
            elif cmd == SB:
                end = data.find(bytes((IAC, SE)), i + 2)
                i = len(data) if end == -1 else end + 2
            else:
                i += 2
        if replies:
            self._writer.write(bytes(replies))
        return bytes(text)
