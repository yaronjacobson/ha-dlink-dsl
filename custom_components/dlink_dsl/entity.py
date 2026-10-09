"""Base entity for the D-Link DSL integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .session import DslSession


class DslEntity(Entity):
    """Entity tied to the router device that follows the session state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str) -> None:
        """Set unique ID and device info."""
        self._session: DslSession = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Router",
            manufacturer="D-Link",
            model="DSL-225",
        )

    async def async_added_to_hass(self) -> None:
        """Follow armed/disarmed changes."""
        self.async_on_remove(
            self._session.async_add_listener(self.async_write_ha_state)
        )
