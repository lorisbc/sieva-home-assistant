"""Sensors for the Sieva integration."""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import SievaData
from .const import DOMAIN
from .coordinator import SievaConfigEntry, SievaCoordinator

_LOGGER = logging.getLogger(__name__)

# Data is fetched by the coordinator, entities never poll.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SievaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up two sensors per installation point of the account."""
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for point in coordinator.data
        for entity in (
            SievaTotalSensor(coordinator, point),
            SievaCurrentYearSensor(coordinator, point),
        )
    )


class SievaEntity(CoordinatorEntity[SievaCoordinator]):
    """Base entity for one installation point."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by Sieva"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: SievaCoordinator, point: str, key: str) -> None:
        super().__init__(coordinator)
        self._point = point
        self._attr_translation_key = key
        self._attr_unique_id = f"{point}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, point)},
            name=f"Sieva {point}",
            manufacturer="Sieva",
            model="Water meter",
            serial_number=coordinator.data[point].meter or None,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://ael.sieva.fr/Portail/fr-FR/Connexion/Login",
        )

    @property
    def point_data(self) -> SievaData | None:
        """Data of this installation point, if still returned by the portal."""
        return (self.coordinator.data or {}).get(self._point)

    @property
    def available(self) -> bool:
        return super().available and self.point_data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (data := self.point_data) is None:
            return {}
        return {
            "address": data.address,
            "installation_point": data.installation_point,
            "meter": data.meter,
        }


class SievaTotalSensor(SievaEntity, RestoreSensor):
    """Cumulated consumption since the start of the contract (m³).

    This is the sensor to use in the Energy dashboard.
    """

    def __init__(self, coordinator: SievaCoordinator, point: str) -> None:
        super().__init__(coordinator, point, "total")

    async def async_added_to_hass(self) -> None:
        """Restore the last known total, then apply the fresh data."""
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, (int, float, Decimal)):
            self._attr_native_value = float(last.native_value)
        self._update_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    @callback
    def _update_from_coordinator(self) -> None:
        if (data := self.point_data) is None:
            return
        previous = self._attr_native_value
        # A lower value would be seen as a meter reset by the statistics and
        # would count the whole total again: keep the previous value instead.
        if isinstance(previous, (int, float)) and data.total < previous:
            _LOGGER.warning(
                "Sieva total for %s decreased (%s -> %s m³), keeping the previous value",
                self._point,
                previous,
                data.total,
            )
            return
        self._attr_native_value = data.total


class SievaCurrentYearSensor(SievaEntity, SensorEntity):
    """Consumption of the current calendar year (m³)."""

    def __init__(self, coordinator: SievaCoordinator, point: str) -> None:
        super().__init__(coordinator, point, "current_year")

    @property
    def native_value(self) -> float | None:
        if (data := self.point_data) is None:
            return None
        return round(data.yearly.get(str(dt_util.now().year), 0.0), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (data := self.point_data) is None:
            return {}
        return {
            **super().extra_state_attributes,
            "yearly": {
                year: round(value, 3) for year, value in sorted(data.yearly.items())
            },
        }
