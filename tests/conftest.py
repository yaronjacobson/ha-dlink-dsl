"""Shared fixtures: a fake telnet router that speaks like the DSL-225 CLI."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest

USERNAME = "admin"
PASSWORD = "secret"

# IAC DO ECHO, IAC WILL SUPPRESS-GO-AHEAD: what many routers send on connect.
NEGOTIATION = bytes((255, 253, 1, 255, 251, 3))


@dataclass
class FakeRouter:
    """Records what the client sent and how the session went."""

    host: str = "127.0.0.1"
    port: int = 0
    lines: list[str] = field(default_factory=list)
    negotiation_replies: bytes = b""
    connections: int = 0
    rebooted: bool = False
    drop_after_login: bool = False
    writers: list[asyncio.StreamWriter] = field(default_factory=list)

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        self.writers.append(writer)
        try:
            writer.write(NEGOTIATION + b"\r\nDSL-225\r\nLogin: ")
            await writer.drain()
            # Client must refuse both options before sending the username.
            self.negotiation_replies = await reader.readexactly(6)
            user = await self._line(reader)
            writer.write(b"Password: ")
            await writer.drain()
            password = await self._line(reader)
            if (user, password) != (USERNAME, PASSWORD):
                writer.write(b"\r\nLogin incorrect\r\nLogin: ")
                await writer.drain()
                await reader.read()
                return
            writer.write(b"\r\nWelcome\r\n> ")
            await writer.drain()
            if self.drop_after_login:
                return
            while line := await self._line(reader):
                if line == "reboot":
                    self.rebooted = True
                    writer.write(b"\r\nThe system is going down NOW!\r\n")
                    await writer.drain()
                    return
                if line == "exit":
                    return
                writer.write(b"\r\n> ")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async def _line(self, reader: asyncio.StreamReader) -> str:
        raw = await reader.readuntil(b"\r\n")
        line = raw.decode().strip()
        self.lines.append(line)
        return line


@pytest.fixture
async def router() -> AsyncIterator[FakeRouter]:
    """Start a fake router on a random local port."""
    fake = FakeRouter()
    server = await asyncio.start_server(fake.handle, fake.host, 0)
    fake.port = server.sockets[0].getsockname()[1]
    yield fake
    server.close()
    for writer in fake.writers:
        writer.close()
    await server.wait_closed()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/dlink_dsl."""
    return


@pytest.fixture(autouse=True)
def allow_local_sockets(socket_enabled):
    """The fake router is a real local TCP server."""
    return
