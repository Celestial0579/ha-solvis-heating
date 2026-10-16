"""Diagnostics for the Solvis Heating integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SolvisConfigEntry

TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolvisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    values = asdict(data)
    values["fetched_at"] = data.fetched_at.isoformat()
    values["controller_time"] = (
        data.controller_time.isoformat() if data.controller_time else None
    )
    values["clock_offset"] = data.clock_offset
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "data": values,
    }
