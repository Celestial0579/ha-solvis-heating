"""Client for the XML interface of the SolvisRemote."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

import aiohttp

from homeassistant.util import dt as dt_util

from .digest import DigestChallenge, DigestError, build_authorization, parse_challenge
from .sc2xml import Sc2Data, Sc2DecodeError, extract_frame, parse_frame

_LOGGER = logging.getLogger(__name__)

XML_PATH = "/sc2_val.xml"
REQUEST_TIMEOUT = 15
MAX_RESPONSE_BYTES = 65536


class SolvisError(Exception):
    """Base class for errors raised by the client."""


class CannotConnect(SolvisError):
    """The SolvisRemote cannot be reached or answers unexpectedly."""


class InvalidAuth(SolvisError):
    """The credentials were rejected."""


class NoXmlInterface(SolvisError):
    """The SolvisRemote does not provide the XML interface."""


class InvalidData(SolvisError):
    """The data of the SolvisRemote cannot be decoded."""


def normalize_host(value: str) -> str:
    """Return ``host`` or ``host:port`` from user input.

    A scheme, path, credentials and surrounding spaces are removed.
    """
    text = value.strip()
    if not text:
        raise ValueError("The host is empty")
    if "://" not in text:
        text = f"http://{text}"
    parts = urlsplit(text)
    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError as err:
        raise ValueError("The host is invalid") from err
    if not hostname:
        raise ValueError("The host is invalid")
    host = hostname.lower()
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    return f"{host}:{port}" if port else host


class Sc2Client:
    """Read the data frame of a SolvisControl 2 through the SolvisRemote."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._host = host
        self._username = username
        self._password = password
        self._challenge: DigestChallenge | None = None
        self._nonce_count = 0

    @property
    def url(self) -> str:
        """Return the address of the XML file."""
        return f"http://{self._host}{XML_PATH}"

    async def async_get_data(self) -> Sc2Data:
        """Fetch and decode the current data frame."""
        text = await self._async_get_xml()
        try:
            return parse_frame(extract_frame(text), dt_util.now())
        except Sc2DecodeError as err:
            raise InvalidData(str(err)) from err

    async def _async_get_xml(self) -> str:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                status, authenticate, body = await self._async_request()
                if status == 401:
                    self._set_challenge(authenticate)
                    status, authenticate, body = await self._async_request()
                    if status == 401:
                        self._challenge = None
                        raise InvalidAuth("The credentials were rejected")
        except TimeoutError as err:
            raise CannotConnect(f"Timeout while connecting to {self._host}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Cannot connect to {self._host}: {err}") from err

        if status == 404:
            raise NoXmlInterface(f"{self._host} does not provide {XML_PATH}")
        if status != 200:
            raise CannotConnect(f"Unexpected HTTP status {status} from {self._host}")
        return body

    def _set_challenge(self, header: str | None) -> None:
        try:
            self._challenge = parse_challenge(header)
        except DigestError as err:
            raise CannotConnect(str(err)) from err
        self._nonce_count = 0

    async def _async_request(self) -> tuple[int, str | None, str]:
        headers: dict[str, str] = {}
        if self._challenge is not None:
            self._nonce_count += 1
            headers["Authorization"] = build_authorization(
                self._challenge,
                self._username,
                self._password,
                "GET",
                XML_PATH,
                nonce_count=self._nonce_count,
            )
        async with self._session.get(
            self.url, headers=headers, allow_redirects=False
        ) as response:
            authenticate = response.headers.get("WWW-Authenticate")
            body = ""
            if response.status == 200:
                if (response.content_length or 0) > MAX_RESPONSE_BYTES:
                    raise InvalidData("The response is unexpectedly large")
                body = (await response.read()).decode("utf-8", errors="replace")
            return response.status, authenticate, body
