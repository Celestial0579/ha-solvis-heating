"""Decoder for the ``sc2_val.xml`` data frame of the SolvisRemote (SolvisControl 2).

The XML file contains a single ``<data>`` element with a hexadecimal string::

    <xml><data>AA5555AA056B...</data></xml>

Layout (offsets in bytes, multi-byte values are little endian):

=======  ======  ==============================================================
Offset   Length  Content
=======  ======  ==============================================================
0        6       Header ``AA 55 55 AA 05 6B``
6        3       Clock of the controller (hour, minute, second)
9        2       Device type
11       2       Device number
13       32      S1..S16, signed 16 bit, 0.1 degC (>= 220 degC: sensor missing)
45       2       S18 volume flow warm water, 0.1 l/min
47       2       S17 volume flow solar, l/h
49       6       Analog inputs 1..3 (unused)
55       4       Analog outputs 1..4 (unused)
59       6       Room sensors RF1..RF3, signed 16 bit, 0.1 degC
65       14      Outputs A1..A14, one byte each
79       2       Z1 burner runtime (h)
81       2       Z2 burner starts
83       2       Z3 burner starts stage 2
85       2       Z4 solar pump runtime (h)
87       2       SE solar yield (kWh)
89       15      Unused
104      2       SL solar power, 0.1 kW
=======  ======  ==============================================================

The format was reverse engineered by the community, see the ``sc2xmlreader`` project.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import re

FRAME_HEADER = "AA5555AA056B"
FRAME_MIN_CHARS = 212

# According to the Solvis documentation 220 degC means "sensor interrupted" and
# -30 degC means "sensor short circuit" for the temperature inputs.
SENSOR_MAX = 220.0
SENSOR_MIN = -30.0

_DATA_RE = re.compile(r"<data>\s*([0-9A-Fa-f\s]+?)\s*</data>", re.IGNORECASE)

_OFF_TIME = 6
_OFF_TYPE = 9
_OFF_NUMBER = 11
_OFF_SENSORS = 13
_OFF_S18 = 45
_OFF_S17 = 47
_OFF_ROOM = 59
_OFF_OUTPUTS = 65
_OFF_Z1 = 79
_OFF_Z2 = 81
_OFF_Z3 = 83
_OFF_Z4 = 85
_OFF_SE = 87
_OFF_SL = 104

SENSOR_COUNT = 16
OUTPUT_COUNT = 14
ROOM_COUNT = 3


class Sc2DecodeError(Exception):
    """Raised when a data frame cannot be decoded."""


@dataclass(frozen=True, slots=True)
class Sc2Data:
    """Decoded measurement values of the controller."""

    raw: str
    fetched_at: datetime
    controller_time: time | None
    device_type: int
    device_number: int
    sensors: tuple[float | None, ...]
    flow_warm_water: float
    flow_solar: int
    room_sensors: tuple[float | None, ...]
    outputs: tuple[int, ...]
    burner_hours: int
    burner_starts: int
    burner_starts_stage_2: int
    solar_pump_hours: int
    solar_yield_kwh: int
    solar_power_kw: float

    def sensor(self, number: int) -> float | None:
        """Return the temperature of sensor ``S<number>`` (1..16), ``None`` if missing."""
        return self.sensors[number - 1]

    def output(self, number: int) -> int:
        """Return the raw value of output ``A<number>`` (1..14), 0 means off."""
        return self.outputs[number - 1]

    @property
    def clock_offset(self) -> int | None:
        """Seconds the controller clock is ahead of the local time (wraps at midnight)."""
        if self.controller_time is None:
            return None
        controller = _seconds_of_day(self.controller_time)
        local = _seconds_of_day(self.fetched_at)
        return (controller - local + 43200) % 86400 - 43200


def _seconds_of_day(value: time | datetime) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def extract_frame(xml_text: str) -> str:
    """Return the hexadecimal frame from the XML document."""
    match = _DATA_RE.search(xml_text)
    if match is None:
        raise Sc2DecodeError("The response contains no <data> element")
    return "".join(match.group(1).split()).upper()


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=False)


def _s16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=True)


def _temperature(raw: int) -> float | None:
    value = raw / 10
    if value >= SENSOR_MAX or value <= SENSOR_MIN:
        return None
    return value


def parse_frame(frame: str, fetched_at: datetime) -> Sc2Data:
    """Decode a hexadecimal data frame."""
    if len(frame) < FRAME_MIN_CHARS:
        raise Sc2DecodeError(f"The frame is too short ({len(frame)} characters)")
    if not frame.startswith(FRAME_HEADER):
        raise Sc2DecodeError("The frame does not start with the expected header")
    try:
        data = bytes.fromhex(frame[:FRAME_MIN_CHARS])
    except ValueError as err:
        raise Sc2DecodeError("The frame is not valid hexadecimal data") from err

    hour, minute, second = data[_OFF_TIME : _OFF_TIME + 3]
    controller_time = (
        time(hour, minute, second) if hour < 24 and minute < 60 and second < 60 else None
    )

    sensors = tuple(
        _temperature(_s16(data, _OFF_SENSORS + 2 * index)) for index in range(SENSOR_COUNT)
    )
    room_sensors = tuple(
        None if raw == 0 else _temperature(raw)
        for raw in (_s16(data, _OFF_ROOM + 2 * index) for index in range(ROOM_COUNT))
    )
    outputs = tuple(data[_OFF_OUTPUTS + index] for index in range(OUTPUT_COUNT))

    return Sc2Data(
        raw=frame,
        fetched_at=fetched_at,
        controller_time=controller_time,
        device_type=_u16(data, _OFF_TYPE),
        device_number=_u16(data, _OFF_NUMBER),
        sensors=sensors,
        flow_warm_water=_u16(data, _OFF_S18) / 10,
        flow_solar=_u16(data, _OFF_S17),
        room_sensors=room_sensors,
        outputs=outputs,
        burner_hours=_u16(data, _OFF_Z1),
        burner_starts=_u16(data, _OFF_Z2),
        burner_starts_stage_2=_u16(data, _OFF_Z3),
        solar_pump_hours=_u16(data, _OFF_Z4),
        solar_yield_kwh=_u16(data, _OFF_SE),
        solar_power_kw=_u16(data, _OFF_SL) / 10,
    )
