"""Config flow for the Sieva integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SievaAuthError, SievaClient, SievaConnectionError, SievaError
from .const import CONF_DELIVERY_POINT, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
        vol.Required(CONF_DELIVERY_POINT): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class SievaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sieva."""

    VERSION = 1

    async def _async_validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Try to log in and fetch data, return form errors."""
        client = SievaClient(
            async_create_clientsession(self.hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_DELIVERY_POINT],
        )
        try:
            await client.async_get_data()
        except SievaAuthError:
            return {"base": "invalid_auth"}
        except SievaConnectionError:
            return {"base": "cannot_connect"}
        except SievaError:
            _LOGGER.exception("Unexpected answer from the Sieva portal")
            return {"base": "invalid_data"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_DELIVERY_POINT] = str(
                user_input[CONF_DELIVERY_POINT]
            ).strip()
            await self.async_set_unique_id(user_input[CONF_DELIVERY_POINT])
            self._abort_if_unique_id_configured()
            if not (errors := await self._async_validate(user_input)):
                return self.async_create_entry(
                    title=f"Sieva {user_input[CONF_DELIVERY_POINT]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start a reauthentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if not (errors := await self._async_validate(data)):
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
