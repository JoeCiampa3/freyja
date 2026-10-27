"""The name rule for inherited parameters (CONVENTIONS section 3, CAD terms): `in_` plus the address with `snapshot#/` removed and every other `#`, `/`, `.`
and `-` replaced by `_`."""
from __future__ import annotations

import re

PREFIX = "in_"
_NAME_RE = re.compile(r"^in_[A-Za-z0-9_]+$")
_ADDRESS_RE = re.compile(r"^[^#\s]+#/[^\s]+$")


def inherited_name(address: str) -> str:
    """The Fusion name of the parameter inherited from an address. ValueError when the address is not a pointer to a value or the result is not a valid name."""
    if not isinstance(address, str) or not _ADDRESS_RE.match(address):
        raise ValueError(f"no parameter name for {address!r}: expected <source>#/<pointer>, a pointer into the source")
    body = address[len("snapshot#/"):] if address.startswith("snapshot#/") else address
    name = PREFIX + re.sub(r"[/.\-]", "_", body.replace("#/", "_"))
    if not _NAME_RE.match(name):
        raise ValueError(f"no parameter name for {address!r}: {name!r} has characters Fusion names cannot carry")
    return name


def names_for(addresses) -> dict:
    """{address: name}; ValueError when two different addresses map to one name."""
    out, owner = {}, {}
    for a in addresses:
        n = inherited_name(a)
        if n in owner and owner[n] != a:
            raise ValueError(f"addresses {owner[n]!r} and {a!r} both map to {n!r}")
        owner[n] = a
        out[a] = n
    return out
