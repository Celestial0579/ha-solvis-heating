"""Data update coordinator for the Solvis Heating integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidAuth, InvalidData, NoXmlInterface, Sc2Client
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, OPTION_DEFAULTS
from .sc2xml import Sc2Data

_LOGGER = logging.getLogger(__name__)

type SolvisConfigEntry = ConfigEntry[SolvisCoordinator]


class SolvisCoordinator(DataUpdateCoordinator[Sc2Data]):
    """Fetch the data of the SolvisRemote."""

    config_entry: SolvisConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SolvisConfigEntry, client: Sc2Client
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        # Options the entities were created with; used to detect option changes.
        self.applied_options: dict[str, Any] = {**OPTION_DEFAULTS, **entry.options}

    async def _async_update_data(self) -> Sc2Data:
        """Fetch the latest data from the SolvisRemote."""
        try:
            return await self.client.async_get_data()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(
                "The SolvisRemote rejected the credentials"
            ) from err
        except (CannotConnect, NoXmlInterface, InvalidData) as err:
            raise UpdateFailed(f"Error communicating with the SolvisRemote: {err}") from err
