"""Tests for the decoder of the SolvisRemote data frame."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.solvis_heating.sc2xml import (
    FRAME_MIN_CHARS,
    Sc2Data,
    Sc2DecodeError,
    extract_frame,
    parse_frame,
)

from .const import SAMPLE_FRAME, SAMPLE_XML

NOW = datetime(2026, 10, 16, 16, 9, 0, tzinfo=UTC)


def test_extract_frame() -> None:
    """The frame is read from the XML document."""
    assert extract_frame(SAMPLE_XML) == SAMPLE_FRAME
    assert extract_frame(f"<xml><data>\n{SAMPLE_FRAME[:50]}\n{SAMPLE_FRAME[50:]} </data></xml>") == SAMPLE_FRAME


def test_extract_frame_without_data() -> None:
    """A document without data element is rejected."""
    with pytest.raises(Sc2DecodeError):
        extract_frame("<xml></xml>")


def test_temperatures(sample_data: Sc2Data) -> None:
    """The temperatures are decoded little endian with one decimal."""
    assert sample_data.sensor(1) == 61.6
    assert sample_data.sensor(2) == 23.9
    assert sample_data.sensor(3) == 33.9
    assert sample_data.sensor(4) == 41.8
    assert sample_data.sensor(5) == 30.6
    assert sample_data.sensor(6) == 30.8
    assert sample_data.sensor(8) == 35.9
    assert sample_data.sensor(9) == 35.3
    assert sample_data.sensor(10) == 19.8
    assert sample_data.sensor(12) == 38.0
    assert sample_data.sensor(13) == 35.5


def test_missing_sensors_are_none(sample_data: Sc2Data) -> None:
    """Inputs without a sensor (250 degC, -35 degC) are reported as missing."""
    for number in (7, 11, 14, 15, 16):
        assert sample_data.sensor(number) is None
    assert sample_data.room_sensors == (None, None, None)


def test_outputs(sample_data: Sc2Data) -> None:
    """Both heating circuit pumps run, the burner is off."""
    assert sample_data.output(3) == 100
    assert sample_data.output(4) == 100
    assert sample_data.output(12) == 0
    assert len(sample_data.outputs) == 14


def test_counters(sample_data: Sc2Data) -> None:
    """The counters are unsigned 16 bit values."""
    assert sample_data.burner_hours == 26008
    assert sample_data.burner_starts == 11167
    assert sample_data.burner_starts_stage_2 == 1841
    assert sample_data.solar_pump_hours == 9964
    assert sample_data.solar_yield_kwh == 25843
    assert sample_data.solar_power_kw == 0.0
    assert sample_data.flow_warm_water == 0.0
    assert sample_data.flow_solar == 0


def test_device(sample_data: Sc2Data) -> None:
    """Device type and number are read."""
    assert (sample_data.device_type, sample_data.device_number) == (6, 18)


def test_clock_offset(sample_data: Sc2Data) -> None:
    """The offset between the controller clock (16:08:31) and the local time is reported."""
    assert str(sample_data.controller_time) == "16:08:31"
    assert sample_data.clock_offset == -29


def test_clock_offset_wraps_at_midnight() -> None:
    """A controller clock just after midnight is close to a local time just before."""
    data = parse_frame(SAMPLE_FRAME, datetime(2026, 10, 16, 23, 59, 50, tzinfo=UTC))
    # controller 16:08:31 versus 23:59:50 is a large negative offset, not a wrapped one
    assert data.clock_offset == (16 * 3600 + 8 * 60 + 31) - (23 * 3600 + 59 * 60 + 50)
    # A controller clock at 00:10:05 is 10 min 15 s ahead of a local time of 23:59:50.
    midnight = SAMPLE_FRAME[:12] + "000A05" + SAMPLE_FRAME[18:]
    data = parse_frame(midnight, datetime(2026, 10, 16, 23, 59, 50, tzinfo=UTC))
    assert data.clock_offset == 615


@pytest.mark.parametrize(
    "frame",
    [
        "",
        "AA5555AA056B00",
        "BB" + SAMPLE_FRAME[2:],
        SAMPLE_FRAME[: FRAME_MIN_CHARS - 1],
        SAMPLE_FRAME[:100] + "ZZ" + SAMPLE_FRAME[102:],
    ],
)
def test_invalid_frames(frame: str) -> None:
    """Short, foreign or non-hexadecimal frames are rejected."""
    with pytest.raises(Sc2DecodeError):
        parse_frame(frame, NOW)
