"""Config flow for the D-Link DSL integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ARM_WINDOW,
    DEFAULT_ARM_WINDOW,
    DEFAULT_PORT,
    DOMAIN,
    MAX_ARM_WINDOW,
    MIN_ARM_WINDOW,
)
from .telnet import AuthError, CannotConnect, DslTelnetClient

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def validate_login(data: dict[str, Any]) -> None:
    """Log in and straight back out. Never reboots."""
    client = DslTelnetClient(
        data[CONF_HOST], data[CONF_PORT], data[CONF_USERNAME], data[CONF_PASSWORD]
    )
    await client.login()
    await client.close()


class DslConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for D-Link DSL."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the router address and credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            try:
                await validate_login(user_input)
            except AuthError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while logging in")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"D-Link DSL ({user_input[CONF_HOST]})", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DslOptionsFlow:
        """Return the options flow."""
        return DslOptionsFlow()


class DslOptionsFlow(OptionsFlow):
    """Only the arm window is configurable."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set how long Reboot stays available after Login."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_ARM_WINDOW, DEFAULT_ARM_WINDOW)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ARM_WINDOW, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_ARM_WINDOW, max=MAX_ARM_WINDOW),
                    )
                }
            ),
        )
