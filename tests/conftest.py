"""Fixtures for the Solvis Heating tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.solvis_heating.sc2xml import Sc2Data, parse_frame

from .const import SAMPLE_FRAME


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading of custom integrations in all tests."""


@pytest.fixture
def sample_data() -> Sc2Data:
    """Return the decoded sample frame."""
    return parse_frame(SAMPLE_FRAME, datetime(2026, 10, 16, 16, 9, 0, tzinfo=UTC))


@pytest.fixture
def mock_client(sample_data: Sc2Data) -> Generator[MagicMock]:
    """Mock the client used by the config flow and by the setup of the entry."""
    with (
        patch(
            "custom_components.solvis_heating.Sc2Client", autospec=True
        ) as client_class,
        patch("custom_components.solvis_heating.config_flow.Sc2Client", new=client_class),
    ):
        client = client_class.return_value
        client.async_get_data = AsyncMock(return_value=sample_data)
        yield client
