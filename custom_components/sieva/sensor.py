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

from .const import CONF_DELIVERY_POINT, DOMAIN
from .coordinator import SievaConfigEntry, SievaCoordinator

_LOGGER = logging.getLogger(__name__)

# The portal only exposes one refresh every few hours: no need for parallel updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SievaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sieva sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [SievaIndexSensor(coordinator), SievaCurrentYearSensor(coordinator)]
    )


class SievaEntity(CoordinatorEntity[SievaCoordinator]):
    """Base entity for Sieva."""

    _attr_has_entity_name = True
    _attr_attribution = "Données fournies par Sieva"

    def __init__(self, coordinator: SievaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        delivery_point = coordinator.config_entry.data[CONF_DELIVERY_POINT]
        self._attr_translation_key = key
        self._attr_unique_id = f"{delivery_point}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, delivery_point)},
            name=f"Compteur d'eau Sieva {delivery_point}",
            manufacturer="Sieva",
            model="Compteur d'eau",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://ael.sieva.fr/Portail/fr-FR/Connexion/Login",
        )


class SievaIndexSensor(SievaEntity, RestoreSensor):
    """Cumulated consumption since the start of the contract (m³).

    This is the sensor to use in the Energy dashboard.
    """

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: SievaCoordinator) -> None:
        super().__init__(coordinator, "index")

    async def async_added_to_hass(self) -> None:
        """Restore the last known index, then apply the fresh data."""
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
        if self.coordinator.data is None:
            return
        new_value = self.coordinator.data.total
        previous = self._attr_native_value
        # A lower value would be seen as a meter reset by the statistics and
        # would count the whole index again: keep the previous value instead.
        if isinstance(previous, (int, float)) and new_value < previous:
            _LOGGER.warning(
                "Index Sieva en baisse (%s -> %s m³), valeur précédente conservée",
                previous,
                new_value,
            )
            return
        self._attr_native_value = new_value


class SievaCurrentYearSensor(SievaEntity, SensorEntity):
    """Consumption of the current calendar year (m³)."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: SievaCoordinator) -> None:
        super().__init__(coordinator, "current_year")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        year = str(dt_util.now().year)
        return round(self.coordinator.data.yearly.get(year, 0.0), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}
        return {
            "par_annee": {
                year: round(value, 3)
                for year, value in sorted(self.coordinator.data.yearly.items())
            }
        }
