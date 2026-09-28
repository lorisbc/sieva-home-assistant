"""Data update coordinator for Sieva."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SievaAuthError, SievaClient, SievaData, SievaError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SievaConfigEntry = ConfigEntry[SievaCoordinator]


class SievaCoordinator(DataUpdateCoordinator[SievaData]):
    """Fetch the yearly consumption from the Sieva portal."""

    config_entry: SievaConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SievaConfigEntry, client: SievaClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> SievaData:
        try:
            return await self.client.async_get_data()
        except SievaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SievaError as err:
            raise UpdateFailed(str(err)) from err
