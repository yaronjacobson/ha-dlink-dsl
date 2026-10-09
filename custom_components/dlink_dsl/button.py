"""Login and Reboot buttons for the D-Link DSL integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DslConfigEntry
from .const import DOMAIN
from .entity import DslEntity
from .telnet import AuthError, CannotConnect, NotLoggedIn


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DslConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the two buttons."""
    async_add_entities(
        [DslLoginButton(entry, "login"), DslRebootButton(entry, "reboot")]
    )


class DslLoginButton(DslEntity, ButtonEntity):
    """Logs in to the router and arms the Reboot button."""

    _attr_icon = "mdi:login"

    async def async_press(self) -> None:
        """Log in."""
        try:
            await self._session.async_login()
        except AuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except CannotConnect as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err


class DslRebootButton(DslEntity, ButtonEntity):
    """Reboots the router; only available right after a successful login."""

    _attr_device_class = ButtonDeviceClass.RESTART

    @property
    def available(self) -> bool:
        """Only pressable while armed."""
        return self._session.armed

    async def async_press(self) -> None:
        """Send the reboot."""
        try:
            await self._session.async_reboot()
        except NotLoggedIn as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_logged_in"
            ) from err
        except CannotConnect as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
