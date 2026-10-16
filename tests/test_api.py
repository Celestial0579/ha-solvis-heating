"""Tests for the client of the SolvisRemote."""

from __future__ import annotations

import hashlib
import re

from aiohttp import web
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.solvis_heating.api import (
    CannotConnect,
    InvalidAuth,
    InvalidData,
    NoXmlInterface,
    Sc2Client,
    normalize_host,
)

from .const import PASSWORD, SAMPLE_XML, USERNAME

REALM = "SolvisRemote"
NONCE = "47434374a747343444a4344a7434777b"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def _challenge() -> web.Response:
    return web.Response(
        status=401,
        headers={
            "WWW-Authenticate": f'Digest realm="{REALM}", nonce="{NONCE}", stale=FALSE, domain="/"'
        },
    )


def _make_app(body: str = SAMPLE_XML, status: int = 200) -> web.Application:
    """Return a web application that behaves like the SolvisRemote."""
    calls: list[str | None] = []

    async def handler(request: web.Request) -> web.Response:
        authorization = request.headers.get("Authorization")
        calls.append(authorization)
        if not authorization:
            return _challenge()
        fields = dict(re.findall(r'(\w+)="([^"]*)"', authorization))
        ha1 = _md5(f"{USERNAME}:{REALM}:{PASSWORD}")
        ha2 = _md5("GET:/sc2_val.xml")
        expected = _md5(f"{ha1}:{NONCE}:{ha2}")
        if fields.get("username") != USERNAME or fields.get("response") != expected:
            return _challenge()
        if status != 200:
            return web.Response(status=status)
        return web.Response(text=body, content_type="text/xml")

    app = web.Application()
    app["calls"] = calls
    app.router.add_get("/sc2_val.xml", handler)
    return app


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.0.30.100", "10.0.30.100"),
        (" 10.0.30.100 ", "10.0.30.100"),
        ("http://10.0.30.100/", "10.0.30.100"),
        ("HTTP://Solvis.Local/sc2_val.xml", "solvis.local"),
        ("10.0.30.100:8080", "10.0.30.100:8080"),
        ("http://user:pw@10.0.30.100:81/x", "10.0.30.100:81"),
        ("[fe80::1]:80", "[fe80::1]:80"),
    ],
)
def test_normalize_host(value: str, expected: str) -> None:
    """The host is reduced to host and optional port."""
    assert normalize_host(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "http://", "http://host:notaport"])
def test_normalize_host_invalid(value: str) -> None:
    """Invalid input raises a ValueError."""
    with pytest.raises(ValueError):  # noqa: PT011
        normalize_host(value)


@pytest.mark.usefixtures("socket_enabled")
async def test_client_reads_data(hass: HomeAssistant, aiohttp_server) -> None:
    """The client answers the Digest challenge and decodes the frame."""
    app = _make_app()
    server = await aiohttp_server(app)
    client = Sc2Client(
        async_get_clientsession(hass), f"127.0.0.1:{server.port}", USERNAME, PASSWORD
    )

    data = await client.async_get_data()
    assert data.sensor(10) == 19.8
    assert len(app["calls"]) == 2  # challenge, then authenticated request

    # The challenge is cached, the next poll needs a single request.
    await client.async_get_data()
    assert len(app["calls"]) == 3


@pytest.mark.usefixtures("socket_enabled")
async def test_client_wrong_password(hass: HomeAssistant, aiohttp_server) -> None:
    """Rejected credentials raise InvalidAuth."""
    server = await aiohttp_server(_make_app())
    client = Sc2Client(
        async_get_clientsession(hass), f"127.0.0.1:{server.port}", USERNAME, "wrong"
    )
    with pytest.raises(InvalidAuth):
        await client.async_get_data()


@pytest.mark.usefixtures("socket_enabled")
async def test_client_missing_xml_interface(
    hass: HomeAssistant, aiohttp_server
) -> None:
    """A device without the XML file raises NoXmlInterface."""
    server = await aiohttp_server(_make_app(status=404))
    client = Sc2Client(
        async_get_clientsession(hass), f"127.0.0.1:{server.port}", USERNAME, PASSWORD
    )
    with pytest.raises(NoXmlInterface):
        await client.async_get_data()


@pytest.mark.usefixtures("socket_enabled")
async def test_client_invalid_data(hass: HomeAssistant, aiohttp_server) -> None:
    """A response that is not a data frame raises InvalidData."""
    server = await aiohttp_server(_make_app(body="<xml><data>AA55</data></xml>"))
    client = Sc2Client(
        async_get_clientsession(hass), f"127.0.0.1:{server.port}", USERNAME, PASSWORD
    )
    with pytest.raises(InvalidData):
        await client.async_get_data()


@pytest.mark.usefixtures("socket_enabled")
async def test_client_unreachable(hass: HomeAssistant) -> None:
    """A closed port raises CannotConnect."""
    client = Sc2Client(async_get_clientsession(hass), "127.0.0.1:1", USERNAME, PASSWORD)
    with pytest.raises(CannotConnect):
        await client.async_get_data()
