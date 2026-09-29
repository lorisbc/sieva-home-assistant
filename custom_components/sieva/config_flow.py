"""Config flow for the Sieva integration (one entry per portal account)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
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
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR})


class SievaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sieva."""

    VERSION = 1

    async def _async_validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Log in and check the account has at least one installation point."""
        client = SievaClient(
            async_create_clientsession(self.hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        try:
            points = await client.async_get_data()
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
        if not points:
            return {"base": "no_delivery_point"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the portal credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_USERNAME] = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            if not (errors := await self._async_validate(user_input)):
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
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
