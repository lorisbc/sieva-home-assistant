"""Constants for the Sieva integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "sieva"

CONF_DELIVERY_POINT: Final = "delivery_point"

DEFAULT_SCAN_INTERVAL: Final = timedelta(hours=6)
