from datetime import timedelta
import logging
import traceback

from custom_components.sieva.sieva import Sieva
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity, STATE_CLASS_TOTAL_INCREASING
from homeassistant.const import (
    CONF_PASSWORD, CONF_LOGIN, CONF_DELIVERY_POINT,
    VOLUME_CUBIC_METERS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval, call_later

_LOGGER = logging.getLogger(__name__)

# CONST
DEFAULT_SCAN_INTERVAL = timedelta(hours=12)

HA_INDEX_ENERGY_M3 = 'Sieva m3'

# Config
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOGIN): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_DELIVERY_POINT): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configure the platform and add the Sieva sensor."""

    _LOGGER.debug('Initializing Sieva platform...')

    try:
        login = config[CONF_LOGIN]
        password = config[CONF_PASSWORD]
        delivery_point = config[CONF_DELIVERY_POINT]

        account = SievaAccount(hass, login, password, delivery_point)
        add_entities(account.sensors, True)

        _LOGGER.debug('Sieva platform initialization has completed successfully')
    except BaseException:
        _LOGGER.error('Sieva platform initialization has failed with exception : {0}'.format(traceback.format_exc()))


class SievaAccount:
    """Representation of a Sieva account."""

    def __init__(self, hass, login, password, delivery_point):
        """Initialise the Sieva account."""
        self._login = login
        self._password = password
        self._delivery_point = delivery_point
        self.sensors = []

        call_later(hass, 5, self.update_sieva_data)

        # Add sensors
        self.sensors.append(SievaSensor(HA_INDEX_ENERGY_M3, VOLUME_CUBIC_METERS))

        track_time_interval(hass, self.update_sieva_data, DEFAULT_SCAN_INTERVAL)

    def update_sieva_data(self, event_time):
        """Fetch new state data for the sensor."""
        _LOGGER.debug('Querying Sieva library for new data...')

        try:
            # Get full month data
            sieva = Sieva(self._login, self._password, self._delivery_point)
            index_m3 = sieva.get_consumption()

            # Update sensors
            for sensor in self.sensors:
                if sensor.name == HA_INDEX_ENERGY_M3:
                    sensor.set_data(index_m3)

                sensor.async_schedule_update_ha_state(True)
                _LOGGER.debug('Sieva data updated')
        except BaseException:
            _LOGGER.error('Failed to query Sieva library with exception : {0}'.format(traceback.format_exc()))

    @property
    def login(self):
        """Return the login."""
        return self._login


class SievaSensor(SensorEntity):
    """Representation of a sensor entity for Sieva."""

    def __init__(self, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._unit = unit
        self._measure = None
        self._attr_state_class = STATE_CLASS_TOTAL_INCREASING

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._measure

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return 'mdi:water'

    def set_data(self, measure):
        """Update sensor data"""
        self._measure = measure
