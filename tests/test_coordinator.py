"""Tests for the handling of rejected logins."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant

from custom_components.solvis_heating.api import InvalidAuth
from custom_components.solvis_heating.const import (
    AUTH_BACKOFF_AFTER,
    AUTH_BACKOFF_INTERVAL,
    AUTH_GRACE_PERIOD,
    DOMAIN,
)
from custom_components.solvis_heating.coordinator import SolvisCoordinator
from custom_components.solvis_heating.sc2xml import Sc2Data

from .const import ENTRY_DATA, ENTRY_OPTIONS, HOST

OUTSIDE = "sensor.solvis_outside_temperature"


class _Clock:
    """Replacement for the time source of the coordinator."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    def utcnow(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """Control the time that measures how long the logins have been rejected."""
    fake = _Clock()
    monkeypatch.setattr("custom_components.solvis_heating.coordinator.dt_util", fake)
    return fake


async def _setup(hass: HomeAssistant) -> SolvisCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Solvis",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        unique_id=HOST,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def _refresh(hass: HomeAssistant, coordinator: SolvisCoordinator) -> None:
    await coordinator.async_refresh()
    await hass.async_block_till_done()


def _reauth_started(hass: HomeAssistant) -> bool:
    return any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_one_rejected_poll_is_only_a_hiccup(
    hass: HomeAssistant, mock_client: MagicMock, sample_data: Sc2Data, clock: _Clock
) -> None:
    """A single rejected poll makes the entities unavailable but asks for nothing."""
    coordinator = await _setup(hass)

    mock_client.async_get_data.side_effect = InvalidAuth
    await _refresh(hass, coordinator)
    assert not coordinator.last_update_success
    assert coordinator.auth_failures == 1
    assert hass.states.get(OUTSIDE).state == "unavailable"
    assert not _reauth_started(hass)

    mock_client.async_get_data.side_effect = None
    mock_client.async_get_data.return_value = sample_data
    await _refresh(hass, coordinator)
    assert coordinator.last_update_success
    assert coordinator.auth_failures == 0
    assert hass.states.get(OUTSIDE).state == "19.8"


async def test_repeated_rejections_slow_the_polling_down(
    hass: HomeAssistant, mock_client: MagicMock, sample_data: Sc2Data, clock: _Clock
) -> None:
    """After a few rejected polls the device is asked less often, until it accepts again."""
    coordinator = await _setup(hass)
    normal = coordinator.update_interval

    mock_client.async_get_data.side_effect = InvalidAuth
    for _ in range(AUTH_BACKOFF_AFTER):
        clock.now += timedelta(minutes=1)
        await _refresh(hass, coordinator)
    assert coordinator.update_interval == AUTH_BACKOFF_INTERVAL
    assert not _reauth_started(hass)

    mock_client.async_get_data.side_effect = None
    mock_client.async_get_data.return_value = sample_data
    await _refresh(hass, coordinator)
    assert coordinator.update_interval == normal
    assert coordinator.auth_failures == 0


async def test_long_rejection_starts_reauthentication(
    hass: HomeAssistant, mock_client: MagicMock, clock: _Clock
) -> None:
    """Rejections that last for the whole grace period ask for the password again."""
    coordinator = await _setup(hass)
    mock_client.async_get_data.side_effect = InvalidAuth

    await _refresh(hass, coordinator)
    assert not _reauth_started(hass)

    clock.now += AUTH_GRACE_PERIOD
    await _refresh(hass, coordinator)
    assert _reauth_started(hass)
