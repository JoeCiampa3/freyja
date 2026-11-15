"""Address reading for a characterization: every value enters through `tools/thread`'s address resolution (adr-0045 D2), and every address read is
recorded, so the generator's `consumes` is exactly what it resolved (brief G-F3)."""
from __future__ import annotations

from pathlib import Path


class CharacterizationError(Exception):
    """A characterization cannot be computed as the brief states it: a missing or unresolvable input, or a stop the brief names. The message says which."""


class Reader:
    def __init__(self, root, build=None):
        from thread import build as tb
        self.root = Path(root)
        self.build = build if build is not None else tb.build_root(self.root)
        if self.build.errors:
            raise CharacterizationError("the thread build has errors: " + "; ".join(f"{i.code}: {i.message}" for i in self.build.errors[:3]))
        self.read: set = set()

    def get(self, address: str):
        """The value at an address; CharacterizationError naming the address and why when it does not resolve."""
        ok, value = self.build.resolve(address)
        if not ok:
            raise CharacterizationError(f"{address}: {self.build.why_unresolved(address)}")
        self.read.add(address)
        return value

    @property
    def consumes(self) -> list:
        return sorted(self.read)
