"""Data update coordinator for the Solvis Heating integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, NoReturn

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, InvalidData, NoXmlInterface, Sc2Client
from .const import (
    AUTH_BACKOFF_AFTER,
    AUTH_BACKOFF_INTERVAL,
    AUTH_GRACE_PERIOD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPTION_DEFAULTS,
)
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
        scan_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.client = client
        # Options the entities were created with; used to detect option changes.
        self.applied_options: dict[str, Any] = {**OPTION_DEFAULTS, **entry.options}
        self._scan_interval = scan_interval
        self._auth_failures = 0
        self._auth_failure_since: datetime | None = None

    @property
    def auth_failures(self) -> int:
        """Return the number of polls in a row that the device rejected."""
        return self._auth_failures

    async def _async_update_data(self) -> Sc2Data:
        """Fetch the latest data from the SolvisRemote."""
        try:
            data = await self.client.async_get_data()
        except InvalidAuth as err:
            self._async_handle_rejected_login(err)
        except (CannotConnect, NoXmlInterface, InvalidData) as err:
            raise UpdateFailed(f"Error communicating with the SolvisRemote: {err}") from err

        if self._auth_failures:
            _LOGGER.info(
                "The SolvisRemote accepts the login again after %s rejected polls",
                self._auth_failures,
            )
            self._auth_failures = 0
            self._auth_failure_since = None
            self.update_interval = self._scan_interval
        return data

    def _async_handle_rejected_login(self, err: InvalidAuth) -> NoReturn:
        """Treat a rejected login as temporary until it lasts for a long time.

        The SolvisRemote rejected a valid login once after days of working polls. Asking for
        the password right away would stop the polling until somebody confirms the dialog, so
        an entry that has worked before only starts the reauthentication after a longer outage.
        """
        if self.data is None:
            # No poll has worked yet, so the saved login is wrong.
            raise ConfigEntryAuthFailed(
                "The SolvisRemote rejected the credentials"
            ) from err

        now = dt_util.utcnow()
        if self._auth_failure_since is None:
            self._auth_failure_since = now
        self._auth_failures += 1

        if now - self._auth_failure_since >= AUTH_GRACE_PERIOD:
            raise ConfigEntryAuthFailed(
                f"The SolvisRemote rejected the credentials for {AUTH_GRACE_PERIOD}"
            ) from err

        if self._auth_failures >= AUTH_BACKOFF_AFTER:
            self.update_interval = max(self._scan_interval, AUTH_BACKOFF_INTERVAL)
        raise UpdateFailed(
            "The SolvisRemote rejected the credentials "
            f"(rejected polls in a row: {self._auth_failures}), trying again"
        ) from err
