"""pytest glue: makes the check modules importable and gives tests the real model's context. Registers tools/testkit as tests/conftest.py does,
so a run of checks/ alone has the same options and records."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import checklib  # noqa: E402
import testkit.plugin as _testkit  # noqa: E402


def pytest_addoption(parser):
    _testkit.add_options(parser)


def pytest_configure(config):
    _testkit.register(config)


@pytest.fixture(scope="session")
def ctx():
    """The committed model and snapshot, at the neutral pose."""
    return checklib.Context.from_files()
