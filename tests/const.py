"""Constants for the Solvis Heating tests."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.solvis_heating.const import (
    CONF_BURNER_POWER,
    CONF_OVEN,
    CONF_SCAN_INTERVAL,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
)

HOST = "10.0.30.100"
USERNAME = "solvis"
PASSWORD = "secret"

ENTRY_DATA = {CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
ENTRY_OPTIONS = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
    CONF_BURNER_POWER: 27,
    CONF_SCAN_INTERVAL: 60,
}

# Real data frame of a SolvisControl 2 (SolvisMax with solar, warm water station and two
# heating circuits), recorded on a mild afternoon: outside 19.8 degC, both heating circuit
# pumps running, burner off.
SAMPLE_FRAME = (
    "AA5555AA056B10081F060012006802EF005301A20132013401A2FE67016101C600C4097C016301C409C409C409"
    "00000000000000000000004C4C0D000000000000000064640000000000000000000098659F2B3107EC26F364"
    "0100010101000000020201010096CD0000001A0A1072650000000000000000"
).ljust(440, "0")

SAMPLE_XML = f"<xml>\n<data>{SAMPLE_FRAME}</data>\n</xml>"
