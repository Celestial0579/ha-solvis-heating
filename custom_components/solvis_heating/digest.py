"""Minimal HTTP Digest authentication for the SolvisRemote web server.

The SolvisRemote answers with an RFC 2069 style challenge (no ``qop``), for example::

    Digest realm="SolvisRemote", nonce="...", stale=FALSE, domain="/"

This module also understands the RFC 2617 ``qop=auth`` variant. MD5 is mandated by the
protocol and is only used for the challenge/response exchange with the device.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import re

_PARAM_RE = re.compile(r'([A-Za-z0-9_-]+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^\s,]*))')


class DigestError(Exception):
    """Raised when a challenge cannot be answered."""


@dataclass(frozen=True, slots=True)
class DigestChallenge:
    """Parsed ``WWW-Authenticate: Digest`` challenge."""

    realm: str
    nonce: str
    opaque: str | None = None
    algorithm: str | None = None
    qop: str | None = None
    stale: bool = False


def parse_challenge(header: str | None) -> DigestChallenge:
    """Parse the value of a ``WWW-Authenticate`` header."""
    if not header:
        raise DigestError("The server did not send a WWW-Authenticate header")
    scheme, _, rest = header.strip().partition(" ")
    if scheme.lower() != "digest":
        raise DigestError(f"Unsupported authentication scheme: {scheme}")

    params: dict[str, str] = {}
    for match in _PARAM_RE.finditer(rest):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        params[match.group(1).lower()] = value.replace('\\"', '"')

    realm = params.get("realm")
    nonce = params.get("nonce")
    if realm is None or nonce is None:
        raise DigestError("The Digest challenge has no realm or nonce")

    algorithm = params.get("algorithm")
    if algorithm is not None and algorithm.upper() != "MD5":
        raise DigestError(f"Unsupported digest algorithm: {algorithm}")

    qop: str | None = None
    if "qop" in params:
        offered = {item.strip().lower() for item in params["qop"].split(",")}
        if "auth" not in offered:
            raise DigestError("The server only offers an unsupported qop")
        qop = "auth"

    return DigestChallenge(
        realm=realm,
        nonce=nonce,
        opaque=params.get("opaque"),
        algorithm=algorithm,
        qop=qop,
        stale=params.get("stale", "").lower() == "true",
    )


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()  # noqa: S324


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_authorization(
    challenge: DigestChallenge,
    username: str,
    password: str,
    method: str,
    uri: str,
    *,
    nonce_count: int = 1,
    cnonce: str | None = None,
) -> str:
    """Build the value of the ``Authorization`` header answering a challenge."""
    ha1 = _md5(f"{username}:{challenge.realm}:{password}")
    ha2 = _md5(f"{method}:{uri}")

    nc = f"{nonce_count:08x}"
    if challenge.qop:
        cnonce = cnonce or os.urandom(8).hex()
        response = _md5(f"{ha1}:{challenge.nonce}:{nc}:{cnonce}:auth:{ha2}")
    else:
        response = _md5(f"{ha1}:{challenge.nonce}:{ha2}")

    parts = [
        f'username="{_quote(username)}"',
        f'realm="{challenge.realm}"',
        f'nonce="{challenge.nonce}"',
        f'uri="{uri}"',
        f'response="{response}"',
    ]
    if challenge.opaque:
        parts.append(f'opaque="{challenge.opaque}"')
    if challenge.algorithm:
        parts.append(f'algorithm="{challenge.algorithm}"')
    if challenge.qop:
        parts.extend(["qop=auth", f"nc={nc}", f'cnonce="{cnonce}"'])
    return "Digest " + ", ".join(parts)
