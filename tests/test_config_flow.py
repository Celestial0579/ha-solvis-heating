"""Tests for the config flow of the Solvis Heating integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.solvis_heating.api import (
    CannotConnect,
    InvalidAuth,
    InvalidData,
    NoXmlInterface,
)
from custom_components.solvis_heating.const import (
    CONF_BURNER_POWER,
    CONF_OVEN,
    CONF_SCAN_INTERVAL,
    CONF_SOLAR,
    CONF_SOLAR_EAST_WEST,
    CONF_WARMWATER_STATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from .const import ENTRY_DATA, ENTRY_OPTIONS, HOST, PASSWORD, USERNAME

USER_INPUT = {CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
SYSTEM_INPUT = {
    CONF_WARMWATER_STATION: True,
    CONF_SOLAR: True,
    CONF_SOLAR_EAST_WEST: False,
    CONF_OVEN: False,
    CONF_BURNER_POWER: 30,
}


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Solvis",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        unique_id=HOST,
    )


async def _start_user_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The user can add a SolvisRemote in two steps."""
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: " http://10.0.30.100/ "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "system"

    # The options are suggested from the connected sensors of the sample frame.
    defaults = {
        str(key): key.default() for key in result["data_schema"].schema if key.default
    }
    assert defaults[CONF_WARMWATER_STATION] is True
    assert defaults[CONF_SOLAR] is True
    assert defaults[CONF_SOLAR_EAST_WEST] is False

    with patch("custom_components.solvis_heating.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SYSTEM_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solvis"
    assert result["data"] == ENTRY_DATA
    assert result["options"] == {
        **SYSTEM_INPUT,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }
    assert result["result"].unique_id == HOST


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (NoXmlInterface, "no_xml_interface"),
        (InvalidData, "invalid_data"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client: MagicMock, exception: type[Exception], error: str
) -> None:
    """Errors are shown and the flow can be continued."""
    mock_client.async_get_data.side_effect = exception
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_client.async_get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "system"


async def test_user_flow_invalid_host(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """An address that cannot be parsed is rejected."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "http://"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """The same SolvisRemote cannot be added twice."""
    _entry().add_to_hass(hass)
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({CONF_SOLAR: False, CONF_SOLAR_EAST_WEST: True}, "east_west_requires_solar"),
        ({CONF_SOLAR_EAST_WEST: True, CONF_OVEN: True}, "east_west_and_oven"),
    ],
)
async def test_system_step_validation(
    hass: HomeAssistant,
    mock_client: MagicMock,
    changes: dict[str, bool],
    error: str,
) -> None:
    """Combinations of options that cannot exist are rejected."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SYSTEM_INPUT, **changes}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "system"
    assert result["errors"] == {"base": error}


async def test_reauth_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The login can be renewed."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_client.async_get_data.side_effect = InvalidAuth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_get_data.side_effect = None
    with patch("custom_components.solvis_heating.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: "new"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"


async def test_reconfigure_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The address can be changed."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch("custom_components.solvis_heating.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "http://10.0.30.101", CONF_USERNAME: "other", CONF_PASSWORD: "pw"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "10.0.30.101",
        CONF_USERNAME: "other",
        CONF_PASSWORD: "pw",
    }
    assert entry.unique_id == "10.0.30.101"


async def test_options_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The options can be changed."""
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_options = {
        **ENTRY_OPTIONS,
        CONF_WARMWATER_STATION: False,
        CONF_BURNER_POWER: 35,
        CONF_SCAN_INTERVAL: 120,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], new_options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == new_options

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
