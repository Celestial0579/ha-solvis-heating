"""Config flow for the Solvis Heating integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    CannotConnect,
    InvalidAuth,
    InvalidData,
    NoXmlInterface,
    Sc2Client,
    normalize_host,
)
from .const import (
    CONF_BURNER_POWER,
    CONF_OVEN,
    CONF_SCAN_INTERVAL,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
    DEFAULT_BURNER_POWER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TITLE,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OPTION_DEFAULTS,
)
from .sc2xml import Sc2Data

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)


def _number(minimum: int, maximum: int, unit: str) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _system_schema(
    defaults: Mapping[str, Any], *, with_interval: bool
) -> vol.Schema:
    """Return the schema of the system options."""
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_WARMWATER_STATION, default=defaults[CONF_WARMWATER_STATION]
        ): BooleanSelector(),
        vol.Required(CONF_SOLAR, default=defaults[CONF_SOLAR]): BooleanSelector(),
        vol.Required(
            CONF_SOLAR_EAST_WEST, default=defaults[CONF_SOLAR_EAST_WEST]
        ): BooleanSelector(),
        vol.Required(CONF_OVEN, default=defaults[CONF_OVEN]): BooleanSelector(),
        vol.Required(
            CONF_BURNER_POWER, default=defaults[CONF_BURNER_POWER]
        ): _number(1, 1000, "kW"),
    }
    if with_interval:
        schema[
            vol.Required(CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL])
        ] = _number(MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL, "s")
    return vol.Schema(schema)


def _validate_system(user_input: Mapping[str, Any]) -> dict[str, str]:
    """Validate the combination of system options."""
    if user_input[CONF_SOLAR_EAST_WEST] and not user_input[CONF_SOLAR]:
        return {"base": "east_west_requires_solar"}
    if user_input[CONF_SOLAR_EAST_WEST] and user_input[CONF_OVEN]:
        return {"base": "east_west_and_oven"}
    return {}


def _without_password(user_input: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the input without the password so it is not sent back to the browser."""
    if user_input is None:
        return None
    return {key: value for key, value in user_input.items() if key != CONF_PASSWORD}


def _clean_options(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Return the options with number inputs converted to integers."""
    options = dict(user_input)
    for key in (CONF_BURNER_POWER, CONF_SCAN_INTERVAL):
        if key in options:
            options[key] = int(options[key])
    return options


def detect_options(data: Sc2Data) -> dict[str, Any]:
    """Derive suggested system options from the connected sensors."""
    return {
        **OPTION_DEFAULTS,
        CONF_WARMWATER_STATION: data.sensor(2) is not None,
        CONF_SOLAR: data.sensor(8) is not None or data.sensor(5) is not None,
        CONF_BURNER_POWER: DEFAULT_BURNER_POWER,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }


class SolvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solvis Heating."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection: dict[str, Any] = {}
        self._detected: dict[str, Any] = dict(OPTION_DEFAULTS)

    async def _async_try_connect(
        self, host: str, username: str, password: str
    ) -> tuple[Sc2Data | None, str | None]:
        """Try to read the data; return the data or an error key."""
        client = Sc2Client(async_get_clientsession(self.hass), host, username, password)
        try:
            return await client.async_get_data(), None
        except CannotConnect as err:
            _LOGGER.debug("Cannot connect to %s: %s", host, err)
            return None, "cannot_connect"
        except InvalidAuth:
            return None, "invalid_auth"
        except NoXmlInterface:
            return None, "no_xml_interface"
        except InvalidData as err:
            _LOGGER.debug("Invalid data from %s: %s", host, err)
            return None, "invalid_data"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception while connecting to %s", host)
            return None, "unknown"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the connection data."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                data, error = await self._async_try_connect(
                    host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                if error is None and data is not None:
                    self._connection = {
                        CONF_HOST: host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                    self._detected = detect_options(data)
                    return await self.async_step_system()
                errors["base"] = error or "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, _without_password(user_input)
            ),
            errors=errors,
        )

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the system options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_system(user_input)
            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data=self._connection,
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        **_clean_options(user_input),
                    },
                )

        return self.async_show_form(
            step_id="system",
            data_schema=self.add_suggested_values_to_schema(
                _system_schema(self._detected, with_interval=False), user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the reauthentication when the credentials were rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, error = await self._async_try_connect(
                entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if error is None and data is not None:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
            errors["base"] = error or "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                AUTH_SCHEMA,
                _without_password(user_input)
                or {CONF_USERNAME: entry.data[CONF_USERNAME]},
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or the credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host = normalize_host(user_input[CONF_HOST])
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            else:
                if any(
                    other.unique_id == host and other.entry_id != entry.entry_id
                    for other in self._async_current_entries()
                ):
                    return self.async_abort(reason="already_configured")
                data, error = await self._async_try_connect(
                    host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                if error is None and data is not None:
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=host,
                        data_updates={
                            CONF_HOST: host,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                errors["base"] = error or "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                _without_password(user_input)
                or {
                    CONF_HOST: entry.data[CONF_HOST],
                    CONF_USERNAME: entry.data[CONF_USERNAME],
                },
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SolvisOptionsFlow:
        """Create the options flow."""
        return SolvisOptionsFlow()


class SolvisOptionsFlow(OptionsFlow):
    """Handle the options of a Solvis Heating entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the system options and the update interval."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_system(user_input)
            if not errors:
                return self.async_create_entry(data=_clean_options(user_input))

        current = {**OPTION_DEFAULTS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _system_schema(current, with_interval=True), user_input
            ),
            errors=errors,
        )
