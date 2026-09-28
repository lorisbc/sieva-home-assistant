"""Config flow for the Sieva integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SievaAuthError, SievaClient, SievaConnectionError, SievaError
from .const import CONF_DELIVERY_POINT, DOMAIN

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


async def _async_call[T](
    call: Callable[[], Awaitable[T]],
) -> tuple[T | None, dict[str, str]]:
    """Run a portal call and map failures to form errors."""
    try:
        return await call(), {}
    except SievaAuthError:
        return None, {"base": "invalid_auth"}
    except SievaConnectionError:
        return None, {"base": "cannot_connect"}
    except SievaError:
        _LOGGER.exception("Unexpected answer from the Sieva portal")
        return None, {"base": "invalid_data"}
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return None, {"base": "unknown"}


class SievaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sieva."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}
        self._delivery_points: dict[str, str] = {}

    def _client(self, data: Mapping[str, Any]) -> SievaClient:
        return SievaClient(
            async_create_clientsession(self.hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_DELIVERY_POINT),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the portal credentials, then discover the installation points."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = self._client(user_input)
            points, errors = await _async_call(client.async_get_delivery_points)
            if not errors:
                self._credentials = user_input
                self._delivery_points = points or {}
                if len(self._delivery_points) != 1:
                    return await self.async_step_delivery_point()
                result = await self._async_create(next(iter(self._delivery_points)))
                if result is not None:
                    return result
                errors = {"base": "invalid_data"}

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_delivery_point(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the installation point (or type it if discovery found none)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._async_create(user_input[CONF_DELIVERY_POINT])
            if result is not None:
                return result
            errors = {"base": "invalid_data"}

        if self._delivery_points:
            field: Any = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=point, label=f"{point} – {address}")
                        for point, address in self._delivery_points.items()
                    ]
                )
            )
        else:
            field = str
        return self.async_show_form(
            step_id="delivery_point",
            data_schema=vol.Schema({vol.Required(CONF_DELIVERY_POINT): field}),
            errors=errors,
        )

    async def _async_create(self, delivery_point: str) -> ConfigFlowResult | None:
        """Check the data can be read, then create the entry."""
        delivery_point = str(delivery_point).strip()
        await self.async_set_unique_id(delivery_point)
        self._abort_if_unique_id_configured()
        data = {**self._credentials, CONF_DELIVERY_POINT: delivery_point}
        _, errors = await _async_call(self._client(data).async_get_data)
        if errors:
            return None
        address = self._delivery_points.get(delivery_point)
        return self.async_create_entry(
            title=f"Sieva {address or delivery_point}", data=data
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
            _, errors = await _async_call(self._client(data).async_get_data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
