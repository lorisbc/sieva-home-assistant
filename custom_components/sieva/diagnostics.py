"""Diagnostics support for Sieva."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SievaConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SievaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (includes the raw portal answer)."""
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "yearly": data.yearly if data else None,
        "total": data.total if data else None,
        "raw": data.raw if data else None,
    }
