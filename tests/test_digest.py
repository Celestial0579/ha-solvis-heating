"""Tests for the HTTP Digest authentication."""

from __future__ import annotations

import hashlib
import re

import pytest

from custom_components.solvis_heating.digest import (
    DigestError,
    build_authorization,
    parse_challenge,
)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def _response(header: str) -> str:
    match = re.search(r'response="([0-9a-f]+)"', header)
    assert match
    return match.group(1)


def test_rfc2617_example() -> None:
    """The example of RFC 2617 section 3.5 gives the documented response."""
    challenge = parse_challenge(
        'Digest realm="testrealm@host.com", qop="auth,auth-int", '
        'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", '
        'opaque="5ccc069c403ebaf9f0171e9517f40e41"'
    )
    header = build_authorization(
        challenge,
        "Mufasa",
        "Circle Of Life",
        "GET",
        "/dir/index.html",
        nonce_count=1,
        cnonce="0a4f113b",
    )
    assert _response(header) == "6629fae49393a05397450978507c4ef1"
    assert 'opaque="5ccc069c403ebaf9f0171e9517f40e41"' in header
    assert "qop=auth" in header
    assert "nc=00000001" in header
    assert 'cnonce="0a4f113b"' in header


def test_solvis_challenge_without_qop() -> None:
    """The SolvisRemote sends an RFC 2069 challenge without qop."""
    challenge = parse_challenge(
        'Digest realm="SolvisRemote", nonce="47434374a747343444a4344a7434777b", '
        'stale=FALSE, domain="/"'
    )
    assert challenge.realm == "SolvisRemote"
    assert challenge.qop is None
    assert challenge.stale is False

    header = build_authorization(challenge, "solvis", "secret", "GET", "/sc2_val.xml")
    ha1 = _md5("solvis:SolvisRemote:secret")
    ha2 = _md5("GET:/sc2_val.xml")
    assert _response(header) == _md5(f"{ha1}:47434374a747343444a4344a7434777b:{ha2}")
    assert "qop=" not in header
    assert "nc=" not in header
    assert header.startswith('Digest username="solvis", realm="SolvisRemote"')


def test_stale_flag() -> None:
    """A stale nonce is recognised."""
    challenge = parse_challenge('Digest realm="r", nonce="n", stale=TRUE')
    assert challenge.stale is True


def test_username_is_quoted() -> None:
    """Quotes and backslashes in the user name are escaped."""
    challenge = parse_challenge('Digest realm="r", nonce="n"')
    header = build_authorization(challenge, 'a"b\\c', "pw", "GET", "/")
    assert 'username="a\\"b\\\\c"' in header


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        'Basic realm="x"',
        'Digest realm="x"',
        'Digest nonce="n"',
        'Digest realm="x", nonce="n", algorithm=SHA-256',
        'Digest realm="x", nonce="n", qop="auth-int"',
    ],
)
def test_unsupported_challenges(header: str | None) -> None:
    """Challenges that cannot be answered raise an error."""
    with pytest.raises(DigestError):
        parse_challenge(header)
