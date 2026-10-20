"""Constants for the Solvis Heating integration."""

from __future__ import annotations

from datetime import timedelta

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

# The SolvisRemote now and then rejects a login for a short time. An entry that has worked before
# keeps polling (slower after a few rejections) and only asks for the password again when the
# rejections last this long.
AUTH_GRACE_PERIOD = timedelta(hours=1)
AUTH_BACKOFF_AFTER = 3  # rejected polls in a row
AUTH_BACKOFF_INTERVAL = timedelta(minutes=5)

# Values used when an option is missing (for example after a manual edit of the config entry).
OPTION_DEFAULTS: dict[str, bool | int] = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
    CONF_BURNER_POWER: DEFAULT_BURNER_POWER,
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
}
