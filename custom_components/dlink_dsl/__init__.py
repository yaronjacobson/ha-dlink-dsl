"""The D-Link DSL integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import CONF_ARM_WINDOW, DEFAULT_ARM_WINDOW
from .session import DslSession
from .telnet import DslTelnetClient

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON]

type DslConfigEntry = ConfigEntry[DslSession]


async def async_setup_entry(hass: HomeAssistant, entry: DslConfigEntry) -> bool:
    """Set up the router from a config entry."""
    data = entry.data

    def client_factory(on_disconnect: Callable[[], None]) -> DslTelnetClient:
        return DslTelnetClient(
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            on_disconnect,
        )

    entry.runtime_data = DslSession(
        hass, client_factory, entry.options.get(CONF_ARM_WINDOW, DEFAULT_ARM_WINDOW)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DslConfigEntry) -> bool:
    """Unload a config entry and close any open connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: DslConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
