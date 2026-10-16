"""Sensors for the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_BURNER_POWER,
    CONF_OVEN,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
)
from .coordinator import SolvisConfigEntry, SolvisCoordinator
from .entity import SolvisEntity
from .sc2xml import Sc2Data

PARALLEL_UPDATES = 0

type ValueFn = Callable[[Sc2Data, Mapping[str, Any]], StateType]
type ExistsFn = Callable[[Mapping[str, Any]], bool]


@dataclass(frozen=True, kw_only=True)
class SolvisSensorEntityDescription(SensorEntityDescription):
    """Describes a Solvis sensor."""

    value_fn: ValueFn
    exists_fn: ExistsFn = lambda _options: True


def _has_warmwater_station(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_WARMWATER_STATION])


def _has_solar(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_SOLAR])


def _has_east_west(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_SOLAR]) and bool(options[CONF_SOLAR_EAST_WEST])


def _has_oven(options: Mapping[str, Any]) -> bool:
    return bool(options[CONF_OVEN])


def _temperature(
    key: str,
    sensor: int,
    *,
    exists_fn: ExistsFn = lambda _options: True,
    enabled_default: bool = True,
) -> SolvisSensorEntityDescription:
    """Describe a temperature sensor wired to input S<sensor>."""
    return SolvisSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled_default,
        exists_fn=exists_fn,
        value_fn=lambda data, _options: data.sensor(sensor),
    )


def _room_temperature(index: int) -> SolvisSensorEntityDescription:
    key = f"room_temperature_{index + 1}"
    return SolvisSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda data, _options: data.room_sensors[index],
    )


def _solar_difference(data: Sc2Data, _options: Mapping[str, Any]) -> StateType:
    flow, back = data.sensor(5), data.sensor(6)
    if flow is None or back is None:
        return None
    return round(flow - back, 1)


def _solar_pressure(data: Sc2Data, _options: Mapping[str, Any]) -> StateType:
    value = data.sensor(7)
    return value if value is not None and 0 <= value <= 10 else None


SENSORS: tuple[SolvisSensorEntityDescription, ...] = (
    _temperature("outside_temperature", 10),
    _temperature("buffer_top_temperature", 1),
    _temperature("buffer_reference_temperature", 3),
    _temperature("heating_buffer_top_temperature", 4),
    _temperature("heating_buffer_bottom_temperature", 9),
    _temperature("heating_circuit_1_flow_temperature", 12),
    _temperature("heating_circuit_2_flow_temperature", 13),
    SolvisSensorEntityDescription(
        key="burner_runtime",
        translation_key="burner_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data, _options: data.burner_hours,
    ),
    SolvisSensorEntityDescription(
        key="burner_starts",
        translation_key="burner_starts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data, _options: data.burner_starts,
    ),
    SolvisSensorEntityDescription(
        key="burner_stage_2_starts",
        translation_key="burner_stage_2_starts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data, _options: data.burner_starts_stage_2,
    ),
    SolvisSensorEntityDescription(
        key="burner_energy",
        translation_key="burner_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data, options: data.burner_hours * options[CONF_BURNER_POWER],
    ),
    _room_temperature(0),
    _room_temperature(1),
    _room_temperature(2),
    SolvisSensorEntityDescription(
        key="clock_offset",
        translation_key="clock_offset",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda data, _options: data.clock_offset,
    ),
    # Warm water station
    _temperature(
        "warm_water_station_temperature", 2, exists_fn=_has_warmwater_station
    ),
    _temperature("circulation_temperature", 11, exists_fn=_has_warmwater_station),
    SolvisSensorEntityDescription(
        key="warm_water_flow",
        translation_key="warm_water_flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=_has_warmwater_station,
        value_fn=lambda data, _options: data.flow_warm_water,
    ),
    # Solar
    _temperature("solar_flow_temperature", 5, exists_fn=_has_solar),
    _temperature("solar_return_temperature", 6, exists_fn=_has_solar),
    _temperature("solar_collector_temperature", 8, exists_fn=_has_solar),
    SolvisSensorEntityDescription(
        key="solar_temperature_difference",
        translation_key="solar_temperature_difference",
        native_unit_of_measurement="K",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=_has_solar,
        value_fn=_solar_difference,
    ),
    SolvisSensorEntityDescription(
        key="solar_pressure",
        translation_key="solar_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        exists_fn=_has_solar,
        value_fn=_solar_pressure,
    ),
    SolvisSensorEntityDescription(
        key="solar_volume_flow",
        translation_key="solar_volume_flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_solar,
        value_fn=lambda data, _options: data.flow_solar,
    ),
    SolvisSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        exists_fn=_has_solar,
        value_fn=lambda data, _options: data.solar_power_kw,
    ),
    SolvisSensorEntityDescription(
        key="solar_yield",
        translation_key="solar_yield",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        exists_fn=_has_solar,
        value_fn=lambda data, _options: data.solar_yield_kwh,
    ),
    SolvisSensorEntityDescription(
        key="solar_pump_runtime",
        translation_key="solar_pump_runtime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        exists_fn=_has_solar,
        value_fn=lambda data, _options: data.solar_pump_hours,
    ),
    # East/west solar or solid fuel oven (both use input S16)
    _temperature("solar_collector_2_temperature", 16, exists_fn=_has_east_west),
    _temperature("oven_temperature", 16, exists_fn=_has_oven),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolvisConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    options = coordinator.applied_options
    async_add_entities(
        SolvisSensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(options)
    )


class SolvisSensor(SolvisEntity, SensorEntity):
    """A measurement value of the controller."""

    entity_description: SolvisSensorEntityDescription

    def __init__(
        self,
        coordinator: SolvisCoordinator,
        description: SolvisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.coordinator.applied_options
        )
