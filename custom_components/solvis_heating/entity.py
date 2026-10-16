"""Base entity for the Solvis Heating integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import SolvisCoordinator


class SolvisEntity(CoordinatorEntity[SolvisCoordinator]):
    """Base class of all Solvis entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolvisCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
