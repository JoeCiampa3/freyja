"""
The pytest side of testkit (see the package docstring). tests/conftest.py and checks/conftest.py both call `add_options` and `register`;
the plugin object is registered once and applies to every item, whichever conftest loaded it.

Under pytest-xdist the workers decide the skips (they run the setup hook) and attach the input key to the report; the controller, which
receives every report, is the only process that writes .fy-cache.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from . import InputsError, inputs_key, passed_store, record_passes, repo_files, tree_key, write_last_full

NAME = "fy-testkit"
SKIP_REASON = "inputs unchanged since this test last passed (inputs sha256:{key}); --rerun-cached runs it"
KEY, CACHED = "fy_inputs_key", "fy_inputs_cached"


def add_options(parser):
    try:
        parser.addoption("--rerun-cached", action="store_true", default=False,
                         help="run the tests marked `inputs` even when their inputs are unchanged since they last passed")
    except ValueError:  # the other conftest added it already
        pass


def register(config):
    if not config.pluginmanager.has_plugin(NAME):
        config.pluginmanager.register(Plugin(config), NAME)


def is_full(config) -> bool:
    """Whether this session runs the whole suite: tests/ and checks/ (or the root), nothing deselected by expression, nothing only collected."""
    root = Path(config.rootpath).resolve()
    base = Path(config.invocation_params.dir)
    args = {(base / str(a).split("::")[0]).resolve() for a in config.args}
    opt = config.option
    partial = (getattr(opt, "keyword", ""), getattr(opt, "markexpr", ""), getattr(opt, "deselect", None), getattr(opt, "collectonly", False),
               getattr(opt, "lf", False))
    return args in ({root / "tests", root / "checks"}, {root}) and not any(partial)


class Plugin:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.rootpath)
        self.worker = hasattr(config, "workerinput")
        self.rerun = bool(config.getoption("--rerun-cached", default=False))
        self.files = None
        self.store = None
        self.passed, self.forget, self.cached = {}, set(), 0
        self.start_key = None
        self.note = None

    # ---- workers (and a run without xdist): the skip ----

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        markers = list(item.iter_markers("inputs"))  # the function's, its class's and its module's: the key covers all of them
        if not markers:
            return
        paths = [a for m in markers for a in m.args]
        if self.files is None:
            self.files = repo_files(self.root)
        try:
            if not paths:
                raise InputsError("the inputs marker needs at least one path")
            own = Path(item.path).resolve().relative_to(self.root.resolve()).as_posix()
            key = inputs_key(self.root, [*paths, own], self.files)
        except InputsError as e:
            pytest.fail(f"{item.nodeid}: {e}", pytrace=False)
        item.user_properties.append((KEY, key))
        if self.store is None:
            self.store = passed_store(self.root)
        if not self.rerun and self.store.get(item.nodeid) == key:
            item.user_properties.append((CACHED, True))
            pytest.skip(SKIP_REASON.format(key=key[:12]))

    # ---- the controller (and a run without xdist): the records ----

    def pytest_sessionstart(self, session):
        if not self.worker and is_full(self.config):
            self.start_key = tree_key(self.root)

    def pytest_runtest_logreport(self, report):
        if self.worker:
            return
        props = {p[0]: p[1] for p in report.user_properties}
        key = props.get(KEY)
        if key is None:
            return
        if report.when == "setup" and report.skipped and props.get(CACHED):
            self.cached += 1
        elif report.failed:
            self.forget.add(report.nodeid)
            self.passed.pop(report.nodeid, None)
        elif report.when == "call" and report.passed and not hasattr(report, "wasxfail") and report.nodeid not in self.forget:
            self.passed[report.nodeid] = key

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.worker:
            return
        if self.passed or self.forget:
            record_passes(self.root, self.passed, self.forget)
        if self.start_key is None or int(exitstatus) not in (0, 1) or session.shouldstop or session.shouldfail:
            return
        reporter = self.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is None:
            return
        if tree_key(self.root) != self.start_key:
            self.note = "testkit: the tree changed during the run, so no last-full-run record was written (`fy state` will run the suite itself)"
            return
        n = lambda k: len(reporter.stats.get(k, []))  # noqa: E731
        write_last_full(self.root, self.start_key, {"passed": n("passed"), "cached": self.cached, "failed": n("failed") + n("error"),
                                                    "skipped": n("skipped") - self.cached})

    def pytest_terminal_summary(self, terminalreporter):
        if self.worker:
            return
        if self.cached:
            terminalreporter.write_line(f"testkit: {self.cached} skipped on unchanged inputs (--rerun-cached runs them)")
        if self.note:
            terminalreporter.write_line(self.note)
