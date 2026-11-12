"""Test collection hooks. Tests marked `fusion` need Joe's live Fusion and its MCP server (Stage 3b); they are deselected unless asked for with `--fusion`
or a `-m` expression that names the marker, so `fy test`, the hook and any machine without Fusion stay green.

tools/testkit is registered here and in checks/conftest.py: the `inputs` marker's skip on unchanged inputs and the last-full-run record (memo 61)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import testkit.plugin as _testkit  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--fusion", action="store_true", default=False, help="run the tests marked `fusion` (needs Fusion and its MCP server)")
    _testkit.add_options(parser)


def pytest_configure(config):
    _testkit.register(config)


def pytest_collection_modifyitems(config, items):
    expr = config.getoption("-m") or ""
    if config.getoption("--fusion") or ("fusion" in expr and "not fusion" not in expr):
        return
    keep, drop = [], []
    for item in items:
        (drop if item.get_closest_marker("fusion") else keep).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep
