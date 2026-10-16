"""The Solvis Heating integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Sc2Client
from .const import OPTION_DEFAULTS
from .coordinator import SolvisConfigEntry, SolvisCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolvisConfigEntry) -> bool:
    """Set up Solvis Heating from a config entry."""
    client = Sc2Client(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = SolvisCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolvisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: SolvisConfigEntry) -> None:
    """Reload the entry when its options changed.

    Updates of the connection data (reauthentication, reconfiguration) reload the entry
    themselves, so only react to option changes here.
    """
    if {**OPTION_DEFAULTS, **entry.options} != entry.runtime_data.applied_options:
        await hass.config_entries.async_reload(entry.entry_id)
