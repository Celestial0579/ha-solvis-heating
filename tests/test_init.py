"""Tests for the setup of the Solvis Heating integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.solvis_heating.api import CannotConnect, InvalidAuth
from custom_components.solvis_heating.const import (
    CONF_OVEN,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
    DOMAIN,
)
from custom_components.solvis_heating.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .const import ENTRY_DATA, ENTRY_OPTIONS, HOST


def _entry(**option_changes: bool) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Solvis",
        data=ENTRY_DATA,
        options={**ENTRY_OPTIONS, **option_changes},
        unique_id=HOST,
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The entry sets up, provides the entities and unloads."""
    entry = _entry()
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.solvis_outside_temperature")
    assert state is not None
    assert state.state == "19.8"
    assert state.attributes["unit_of_measurement"] == "°C"

    assert hass.states.get("sensor.solvis_heating_circuit_1_flow_temperature").state == "38.0"
    assert hass.states.get("sensor.solvis_solar_yield").state == "25843"
    assert hass.states.get("sensor.solvis_burner_runtime").state == "26008"
    assert hass.states.get("sensor.solvis_warm_water_station_temperature").state == "23.9"
    # Collector difference is the flow minus the return temperature of the solar circuit.
    assert float(hass.states.get("sensor.solvis_solar_temperature_difference").state) == -0.2
    # Input without a connected sensor.
    assert hass.states.get("sensor.solvis_circulation_temperature").state == "unknown"

    pump = hass.states.get("binary_sensor.solvis_heating_circuit_1_pump")
    assert pump.state == "on"
    assert pump.attributes["output_level"] == 100
    assert hass.states.get("binary_sensor.solvis_burner").state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_select_the_entities(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Entities of options that are switched off are not created."""
    entry = _entry(**{CONF_SOLAR: False, CONF_WARMWATER_STATION: False})
    await _setup(hass, entry)

    registry = er.async_get(hass)
    keys = {
        item.unique_id.removeprefix(f"{entry.entry_id}_")
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "outside_temperature" in keys
    assert "burner" in keys
    assert not keys & {"solar_yield", "solar_pump", "warm_water_station_temperature"}
    # Output A6 is the third heating circuit pump when no east/west solar is used.
    assert "heating_circuit_3_pump" in keys
    assert not keys & {"solar_valve_1", "oven_pump"}

    await hass.config_entries.async_unload(entry.entry_id)


async def test_east_west_and_oven_options(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """East/west solar and oven change the meaning of the shared inputs and outputs."""
    entry = _entry(**{CONF_SOLAR_EAST_WEST: True})
    await _setup(hass, entry)
    registry = er.async_get(hass)
    keys = {
        item.unique_id.removeprefix(f"{entry.entry_id}_")
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert {"solar_valve_1", "solar_valve_2", "solar_collector_2_temperature"} <= keys
    assert "heating_circuit_3_pump" not in keys
    await hass.config_entries.async_unload(entry.entry_id)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Oven",
        data={**ENTRY_DATA, "host": "10.0.30.102"},
        options={**ENTRY_OPTIONS, CONF_OVEN: True},
        unique_id="10.0.30.102",
    )
    await _setup(hass, entry)
    keys = {
        item.unique_id.removeprefix(f"{entry.entry_id}_")
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert {"oven_pump", "oven_temperature"} <= keys
    assert "burner_stage_2" not in keys
    await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Rejected credentials start the reauthentication."""
    mock_client.async_get_data.side_effect = InvalidAuth
    entry = _entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == SOURCE_REAUTH for flow in flows)


async def test_connection_failure_is_retried(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """An unreachable device is retried later."""
    mock_client.async_get_data.side_effect = CannotConnect
    entry = _entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The diagnostics redact the login and contain the raw frame."""
    entry = _entry()
    await _setup(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["username"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["password"] == "**REDACTED**"
    assert diagnostics["data"]["raw"].startswith("AA5555AA056B")
    assert diagnostics["data"]["clock_offset"] == -29
    assert diagnostics["data"]["controller_time"] == "16:08:31"

    await hass.config_entries.async_unload(entry.entry_id)
