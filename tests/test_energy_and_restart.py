"""Burner energy as a meter (#7) and the grace period after a restart (#8)."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from custom_components.solvis_heating.api import InvalidAuth
from custom_components.solvis_heating.const import CONF_BURNER_POWER, DOMAIN, HAS_WORKED
from custom_components.solvis_heating.sc2xml import Sc2Data

from .const import ENTRY_DATA, ENTRY_OPTIONS, HOST


def _entry(data: dict | None = None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, title="Solvis", data=data or ENTRY_DATA, options=ENTRY_OPTIONS, unique_id=HOST,
        entry_id="solvis1",
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    entry.add_to_hass(hass)
    ok = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return ok


def _energy_id(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "solvis1_burner_energy")
    assert entity_id
    return entity_id


def _energy(hass: HomeAssistant) -> float:
    return float(hass.states.get(_energy_id(hass)).state)


async def _hours(hass: HomeAssistant, entry: MockConfigEntry, sample_data: Sc2Data, hours: int) -> None:
    entry.runtime_data.async_set_updated_data(replace(sample_data, burner_hours=hours))
    await hass.async_block_till_done()


async def test_power_change_applies_from_then_on(
    hass: HomeAssistant, mock_client: MagicMock, sample_data: Sc2Data
) -> None:
    entry = _entry()
    assert await _setup(hass, entry)
    start = sample_data.burner_hours
    assert _energy(hass) == start * 27  # first start: estimate for the runtime so far

    await _hours(hass, entry, sample_data, start + 10)
    assert _energy(hass) == (start + 10) * 27

    entry.runtime_data.applied_options[CONF_BURNER_POWER] = 15  # power changed
    await _hours(hass, entry, sample_data, start + 10)
    assert _energy(hass) == (start + 10) * 27  # no jump when the power changes
    await _hours(hass, entry, sample_data, start + 12)
    assert _energy(hass) == (start + 10) * 27 + 2 * 15

    await _hours(hass, entry, sample_data, 5)  # counter went back (controller replaced)
    assert _energy(hass) == (start + 10) * 27 + 2 * 15
    await _hours(hass, entry, sample_data, 6)
    assert _energy(hass) == (start + 10) * 27 + 3 * 15


async def test_meter_continues_after_restart(
    hass: HomeAssistant, mock_client: MagicMock, sample_data: Sc2Data
) -> None:
    """Restored without stored hours (0.1.2): continue from the old value without a jump."""
    mock_restore_cache_with_extra_data(
        hass, ((State("sensor.solvis_burner_energy_estimated", "1000.0"), None),)
    )
    er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "solvis1_burner_energy", suggested_object_id="solvis_burner_energy_estimated"
    )
    entry = _entry()
    assert await _setup(hass, entry)
    assert _energy(hass) == 1000.0
    await _hours(hass, entry, sample_data, sample_data.burner_hours + 1)
    assert _energy(hass) == 1027.0


async def test_meter_restores_hours(hass: HomeAssistant, mock_client: MagicMock, sample_data: Sc2Data) -> None:
    """Runtime while Home Assistant was stopped is counted once."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("sensor.solvis_burner_energy_estimated", "1000.0"),
                {"burner_hours": sample_data.burner_hours - 2},
            ),
        ),
    )
    er.async_get(hass).async_get_or_create(
        "sensor", DOMAIN, "solvis1_burner_energy", suggested_object_id="solvis_burner_energy_estimated"
    )
    assert await _setup(hass, _entry())
    assert _energy(hass) == 1000.0 + 2 * 27


async def test_rejected_first_poll_with_working_credentials_is_retried(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """#8: credentials that worked before get the grace period also right after a restart."""
    mock_client.async_get_data.side_effect = InvalidAuth
    entry = _entry({**ENTRY_DATA, HAS_WORKED: True})
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not any(f["context"]["source"] == SOURCE_REAUTH for f in hass.config_entries.flow.async_progress())


async def test_first_accepted_poll_sets_the_marker(hass: HomeAssistant, mock_client: MagicMock) -> None:
    entry = _entry()
    assert await _setup(hass, entry)
    assert entry.data[HAS_WORKED] is True
