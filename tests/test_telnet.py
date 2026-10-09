"""Tests for the telnet client."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.dlink_dsl.telnet import (
    AuthError,
    CannotConnect,
    DslTelnetClient,
    NotLoggedIn,
)

from .conftest import PASSWORD, USERNAME, FakeRouter

# IAC WONT ECHO, IAC DONT SUPPRESS-GO-AHEAD
REFUSALS = bytes((255, 252, 1, 255, 254, 3))


def client_for(router: FakeRouter, password: str = PASSWORD) -> DslTelnetClient:
    return DslTelnetClient(router.host, router.port, USERNAME, password)


async def test_login_refuses_options_and_reaches_prompt(router: FakeRouter) -> None:
    client = client_for(router)
    await client.login()
    assert client.logged_in
    assert router.negotiation_replies == REFUSALS
    assert router.lines == [USERNAME, PASSWORD]
    await client.close()
    assert not client.logged_in


async def test_bad_password(router: FakeRouter) -> None:
    client = client_for(router, password="wrong")
    with pytest.raises(AuthError):
        await client.login()
    assert not client.logged_in


async def test_unreachable() -> None:
    client = DslTelnetClient("127.0.0.1", 1, USERNAME, PASSWORD)
    with pytest.raises(CannotConnect):
        await client.login()


async def test_silent_server_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("custom_components.dlink_dsl.telnet.PROMPT_TIMEOUT", 0.2)

    async def silent(reader, writer):
        await reader.read()

    server = await asyncio.start_server(silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = DslTelnetClient("127.0.0.1", port, USERNAME, PASSWORD)
    with pytest.raises(CannotConnect):
        await asyncio.wait_for(client.login(), 15)
    server.close()


async def test_reboot_requires_login(router: FakeRouter) -> None:
    client = client_for(router)
    with pytest.raises(NotLoggedIn):
        await client.reboot()
    assert router.connections == 0


async def test_reboot_sends_only_fixed_command(router: FakeRouter) -> None:
    client = client_for(router)
    await client.login()
    await client.reboot()
    assert router.rebooted
    assert router.lines == [USERNAME, PASSWORD, "reboot"]
    assert not client.logged_in


async def test_dropped_connection_reports_disconnect(router: FakeRouter) -> None:
    router.drop_after_login = True
    dropped = asyncio.Event()
    client = DslTelnetClient(router.host, router.port, USERNAME, PASSWORD, dropped.set)
    await client.login()
    await asyncio.wait_for(dropped.wait(), 2)
    assert not client.logged_in
    with pytest.raises(NotLoggedIn):
        await client.reboot()
    await client.close()


async def test_own_close_does_not_report_disconnect(router: FakeRouter) -> None:
    calls: list[None] = []
    client = DslTelnetClient(
        router.host, router.port, USERNAME, PASSWORD, lambda: calls.append(None)
    )
    await client.login()
    await client.close()
    await asyncio.sleep(0.1)
    assert calls == []
    assert router.lines[-1] == "exit"
