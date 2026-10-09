"""Reboot-armed sensor for the D-Link DSL integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DslConfigEntry
from .entity import DslEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DslConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the armed sensor."""
    async_add_entities([DslRebootArmedSensor(entry, "reboot_armed")])


class DslRebootArmedSensor(DslEntity, BinarySensorEntity):
    """On while logged in and the Reboot button can be pressed."""

    _attr_icon = "mdi:shield-alert"

    @property
    def is_on(self) -> bool:
        """Return True while armed."""
        return self._session.armed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose when the window ends."""
        expires = self._session.expires_at if self._session.armed else None
        return {"expires_at": expires.isoformat() if expires else None}
