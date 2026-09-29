"""Diagnostics support for Sieva."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SievaConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SievaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (includes the raw portal answers)."""
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "delivery_points": {
                point: {**asdict(data), "total": data.total}
                for point, data in (entry.runtime_data.data or {}).items()
            },
        },
        TO_REDACT,
    )
