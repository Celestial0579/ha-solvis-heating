"""Constants for the Solvis Heating integration."""

from __future__ import annotations

DOMAIN = "solvis_heating"

MANUFACTURER = "Solvis"
MODEL = "SolvisControl 2 (SC2)"
DEFAULT_TITLE = "Solvis"

CONF_WARMWATER_STATION = "warmwater_station"
CONF_SOLAR = "solar"
CONF_SOLAR_EAST_WEST = "east_west"
CONF_OVEN = "oven"
CONF_BURNER_POWER = "burner_power"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_BURNER_POWER = 27
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

# Values used when an option is missing (for example after a manual edit of the config entry).
OPTION_DEFAULTS: dict[str, bool | int] = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
    CONF_BURNER_POWER: DEFAULT_BURNER_POWER,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}
