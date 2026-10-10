"""Tests for the two-step Login → Reboot flow."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.dlink_dsl.const import CONF_ARM_WINDOW, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import PASSWORD, USERNAME, FakeRouter

LOGIN = "button.router_login"
REBOOT = "button.router_reboot"
ARMED = "binary_sensor.router_reboot_armed"


async def setup_entry(
    hass: HomeAssistant, router: FakeRouter, password: str = PASSWORD
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=router.host,
        data={
            CONF_HOST: router.host,
            CONF_PORT: router.port,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: password,
        },
        options={CONF_ARM_WINDOW: 30},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )


async def wait_for_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    for _ in range(50):
        await hass.async_block_till_done()
        if hass.states.get(entity_id).state == state:
            return
        await asyncio.sleep(0.05)
    assert hass.states.get(entity_id).state == state


async def test_reboot_refused_until_login(
    hass: HomeAssistant, router: FakeRouter
) -> None:
    await setup_entry(hass, router)
    assert hass.states.get(REBOOT).state != STATE_UNAVAILABLE
    assert hass.states.get(ARMED).state == STATE_OFF

    with pytest.raises(HomeAssistantError):
        await press(hass, REBOOT)
    # Refused without touching the router.
    assert router.connections == 0
    assert not router.rebooted

    await press(hass, LOGIN)
    armed = hass.states.get(ARMED)
    assert armed.state == STATE_ON
    assert armed.attributes["expires_at"] is not None


async def test_login_then_reboot(hass: HomeAssistant, router: FakeRouter) -> None:
    await setup_entry(hass, router)
    await press(hass, LOGIN)
    await press(hass, REBOOT)
    assert router.rebooted
    assert router.lines == [USERNAME, PASSWORD, "reboot"]
    assert hass.states.get(ARMED).state == STATE_OFF
    # The button itself never goes unavailable.
    assert hass.states.get(REBOOT).state != STATE_UNAVAILABLE


async def test_failed_login_stays_disarmed(
    hass: HomeAssistant, router: FakeRouter
) -> None:
    await setup_entry(hass, router, password="wrong")
    with pytest.raises(HomeAssistantError):
        await press(hass, LOGIN)
    assert hass.states.get(ARMED).state == STATE_OFF
    with pytest.raises(HomeAssistantError):
        await press(hass, REBOOT)
    assert not router.rebooted


async def test_window_expiry_disarms(hass: HomeAssistant, router: FakeRouter) -> None:
    await setup_entry(hass, router)
    await press(hass, LOGIN)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await wait_for_state(hass, ARMED, STATE_OFF)
    assert router.lines[-1] == "exit"
    with pytest.raises(HomeAssistantError):
        await press(hass, REBOOT)
    assert not router.rebooted
    assert "reboot" not in router.lines


async def test_second_login_reuses_connection(
    hass: HomeAssistant, router: FakeRouter
) -> None:
    await setup_entry(hass, router)
    await press(hass, LOGIN)
    await press(hass, LOGIN)
    assert router.connections == 1


async def test_router_drop_disarms(hass: HomeAssistant, router: FakeRouter) -> None:
    router.drop_after_login = True
    await setup_entry(hass, router)
    await press(hass, LOGIN)
    await wait_for_state(hass, ARMED, STATE_OFF)
    with pytest.raises(HomeAssistantError):
        await press(hass, REBOOT)


async def test_unload_closes_connection(
    hass: HomeAssistant, router: FakeRouter
) -> None:
    entry = await setup_entry(hass, router)
    await press(hass, LOGIN)
    session = entry.runtime_data
    assert session.armed
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not session.armed
    assert router.lines[-1] == "exit"
