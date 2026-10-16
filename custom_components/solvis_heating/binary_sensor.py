"""Binary sensors for the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_OVEN,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
)
from .coordinator import SolvisConfigEntry, SolvisCoordinator
from .entity import SolvisEntity

PARALLEL_UPDATES = 0

type ExistsFn = Callable[[Mapping[str, Any]], bool]


@dataclass(frozen=True, kw_only=True)
class SolvisBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Solvis binary sensor (an output A1..A14 of the controller)."""

    output: int
    exists_fn: ExistsFn = lambda _options: True


def _has_warmwater_station(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_WARMWATER_STATION])


def _has_solar(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_SOLAR])


def _has_east_west(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_SOLAR]) and bool(options[CONF_SOLAR_EAST_WEST])


def _has_oven(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_OVEN])


def _has_third_circuit(options: Mapping[str, Any]) -> bool:
    # Output A6 is the pump of heating circuit 3, or valve 1 of an east/west solar system.
    return not _has_east_west(options)


def _has_second_burner_stage(options: Mapping[str, Any]) -> bool:
    # Output A13 is the second burner stage, or the pump of a solid fuel oven.
    return not _has_oven(options)


def _output(
    key: str,
    output: int,
    *,
    exists_fn: ExistsFn = lambda _options: True,
    enabled_default: bool = True,
) -> SolvisBinarySensorEntityDescription:
    return SolvisBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=enabled_default,
        output=output,
        exists_fn=exists_fn,
    )


BINARY_SENSORS: tuple[SolvisBinarySensorEntityDescription, ...] = (
    _output("heating_circuit_1_pump", 3),
    _output("heating_circuit_2_pump", 4),
    _output(
        "heating_circuit_3_pump", 6, exists_fn=_has_third_circuit, enabled_default=False
    ),
    _output("heating_circuit_1_mixer_opening", 8, enabled_default=False),
    _output("heating_circuit_1_mixer_closing", 9, enabled_default=False),
    _output("heating_circuit_2_mixer_opening", 10, enabled_default=False),
    _output("heating_circuit_2_mixer_closing", 11, enabled_default=False),
    _output("burner", 12),
    _output("burner_stage_2", 13, exists_fn=_has_second_burner_stage),
    _output("buffer_charging", 14),
    _output("warm_water_station_pump", 2, exists_fn=_has_warmwater_station),
    _output("circulation_pump", 5, exists_fn=_has_warmwater_station),
    _output("solar_pump", 1, exists_fn=_has_solar),
    _output("solar_valve_1", 6, exists_fn=_has_east_west),
    _output("solar_valve_2", 7, exists_fn=_has_east_west),
    _output("oven_pump", 13, exists_fn=_has_oven),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolvisConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    options = coordinator.applied_options
    async_add_entities(
        SolvisBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(options)
    )


class SolvisBinarySensor(SolvisEntity, BinarySensorEntity):
    """An output of the controller (pump, mixer, burner)."""

    entity_description: SolvisBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SolvisCoordinator,
        description: SolvisBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the output is active."""
        return self.coordinator.data.output(self.entity_description.output) > 0

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        """Return the raw value of the output (0 to 100, for modulating outputs)."""
        return {"output_level": self.coordinator.data.output(self.entity_description.output)}
