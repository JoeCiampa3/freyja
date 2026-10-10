"""pytest glue: makes the check modules importable and gives tests the real model's context."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import checklib  # noqa: E402


@pytest.fixture(scope="session")
def ctx():
    """The committed model and snapshot, at the neutral pose."""
    return checklib.Context.from_files()
