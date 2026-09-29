"""Constants for the Sieva integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "sieva"

PORTAL_URL: Final = "https://ael.sieva.fr"

DEFAULT_SCAN_INTERVAL: Final = timedelta(hours=6)
