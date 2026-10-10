"""
Freyja watcher
==============
Leave this running in a terminal. Whenever the numbers the model uses change in
the Google Sheet (or you edit freyja_template.xml), it rebuilds models/freyja.xml
by itself, using exactly the same checked build as pre_processor.py.

    freyja.venv\\Scripts\\python scripts\\watch.py
    freyja.venv\\Scripts\\python scripts\\watch.py --interval 10 --debounce 3
    freyja.venv\\Scripts\\python scripts\\watch.py --xlsx "C:\\path\\sheet.xlsx"   (watch a local copy)

Stop it with Ctrl+C.

HOW IT DETECTS CHANGES
    Every --interval seconds it reads the three named ranges the model uses
    (bsip, pos, rom: one small request) and compares them with the last build.
    It does NOT use Google Drive's "last modified" time: measured on this sheet
    it was unreliable (reported real edits 0.5 s to 2 min late, and missed some
    entirely), while reading the cells is immediate. A side benefit: edits to
    tabs or cells the model doesn't read never trigger anything.

WHAT IT GUARANTEES
    * Debounce: after a change it waits until the data has been stable for
      --debounce seconds, so editing several cells causes ONE rebuild.
    * A bad edit never kills it and never replaces the last good freyja.xml;
      it tells you what is wrong and rebuilds when you fix it.
    * Network or Google hiccups are retried with a growing delay (up to 5 min).
    * If the rebuilt XML is byte-identical to the current file, nothing is written.
    * Idle polls print nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pre_processor as pp

DEFAULT_INTERVAL_S = 20
DEFAULT_DEBOUNCE_S = 5
MAX_DEBOUNCE_WAIT_S = 60  # if someone keeps editing for a minute, build what we have
MAX_BACKOFF_S = 300


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def nap(seconds: float):
    """time.sleep in half-second slices, so Ctrl+C reacts right away even in a 20 s wait."""
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        time.sleep(min(0.5, left))


sheet_fingerprint = pp.sheet_fingerprint  # lives in pre_processor: the snapshot metadata uses it too


def file_fingerprint(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "missing"


class Watcher:
    """One call to step() = one poll. It returns how many seconds to wait before
    the next one. `sleep`/`clock`/`out` are injectable so tests don't wait."""

    def __init__(self, source, build, template: Path, interval: float = DEFAULT_INTERVAL_S,
                 debounce: float = DEFAULT_DEBOUNCE_S, sleep=nap, clock=time.monotonic, out=log):
        self.source, self.build, self.template = source, build, template
        self.interval, self.debounce = interval, debounce
        self.sleep, self.clock, self.out = sleep, clock, out
        self.last_sheet_fp = None  # fingerprint of the data we last built (or tried to build)
        self.last_template_fp = None
        self.failures = 0  # consecutive failed reads of the sheet
        self.last_error = None
        self.blocked = False  # a build is waiting on something outside the data (file locked)
        self.last_warnings = None

    # --- one poll ----------------------------------------------------------
    def step(self) -> float:
        try:
            tables = self._read()
            tpl_fp = file_fingerprint(self.template)
            sheet_fp = sheet_fingerprint(tables)
            if sheet_fp == self.last_sheet_fp and tpl_fp == self.last_template_fp:
                return self.interval  # nothing changed: silent

            if self.blocked:
                pass  # retrying a build that was blocked earlier: already announced
            elif self.last_sheet_fp is None:
                self.out("first build ...")
            else:
                what = " and ".join(n for n, changed in (("sheet", sheet_fp != self.last_sheet_fp),
                                                         ("template", tpl_fp != self.last_template_fp)) if changed)
                self.out(f"change detected ({what}); waiting for {self.debounce:g}s of quiet before rebuilding")
                if sheet_fp != self.last_sheet_fp:
                    tables, sheet_fp = self._wait_until_stable(tables, sheet_fp)
                tpl_fp = file_fingerprint(self.template)
            if self._rebuild(tables):  # False = environment problem (file locked): try again next poll
                self.last_sheet_fp, self.last_template_fp = sheet_fp, tpl_fp  # also after a failed build: don't retry identical data
            return self.interval
        except KeyboardInterrupt:
            raise
        except pp.SheetAccessError as e:
            return self._read_failed(str(e))
        except Exception as e:  # a bug must not end the watcher either
            self.out(f"unexpected error ({type(e).__name__}: {e}); still watching. Details:\n"
                     + "".join("    " + ln for ln in traceback.format_exc().splitlines(True)))
            return self.interval

    def _read(self) -> dict:
        tables = self.source.fetch()
        if self.failures:
            self.out(f"sheet reachable again (after {self.failures} failed attempt(s))")
            self.failures, self.last_error = 0, None
        return tables

    def _read_failed(self, message: str) -> float:
        self.failures += 1
        delay = min(MAX_BACKOFF_S, self.interval * 2 ** min(self.failures - 1, 6))
        if message != self.last_error:  # say it once, not every retry
            self.last_error = message
            self.out(f"cannot read the sheet: {message}\n    will keep retrying (next attempt in {delay:g}s, "
                     "then slower; this is only printed again if the problem changes)")
        return delay

    def _wait_until_stable(self, tables: dict, fp: str):
        """Poll every `debounce` seconds until two reads in a row agree."""
        deadline = self.clock() + MAX_DEBOUNCE_WAIT_S
        while True:
            self.sleep(self.debounce)
            newer = self.source.fetch()
            newer_fp = sheet_fingerprint(newer)
            if newer_fp == fp:
                return newer, fp
            if self.clock() >= deadline:
                self.out(f"still being edited after {MAX_DEBOUNCE_WAIT_S}s; building with the latest values")
                return newer, newer_fp
            tables, fp = newer, newer_fp

    # --- one build ---------------------------------------------------------
    def _rebuild(self, tables: dict) -> bool:
        """Returns True if this data is 'dealt with' (built, or failed because of
        the data itself), False if it should be retried at the next poll."""
        if not self.blocked:
            self.out("rebuilding ...")
        try:
            r = self.build(tables)
        except pp.BuildError as e:
            if e.transient:
                if not self.blocked:  # say it once, not every poll
                    self.out("REBUILD BLOCKED: " + " ".join(e.errors) + " Will retry at the next check.")
                self.blocked = True
                return False
            self.blocked = False
            self.out(f"REBUILD FAILED while {e.stage} - {len(e.errors)} problem(s):\n"
                     + "\n".join(f"    ERROR {x}" for x in e.errors)
                     + "\n    freyja.xml was NOT changed (the last good model is still in place). "
                       "Waiting for the next edit.")
            return True
        except Exception as e:
            self.blocked = False
            self.out(f"REBUILD FAILED unexpectedly ({type(e).__name__}: {e}); freyja.xml was NOT changed. Details:\n"
                     + "".join("    " + ln for ln in traceback.format_exc().splitlines(True)))
            return True
        self.blocked = False

        if r.status == "unchanged":
            self.out(f"rebuilt, but the result is identical to the current model; nothing written "
                     f"({r.placeholders} placeholders)")
        else:
            self.out(f"OK: model {r.status}, {r.placeholders} placeholders substituted"
                     + (f", {r.model_line}" if r.model_line else "")
                     + (f", {len(r.warnings)} warning(s)" if r.warnings else ""))
        if r.warnings and r.warnings != self.last_warnings:  # list them once, then only when they change
            self.out("warnings:\n" + "\n".join(f"    WARNING {w}" for w in r.warnings))
        self.last_warnings = r.warnings
        return True


class XlsxSource:
    """Same interface as GoogleSheetSource, for a local file (handy offline)."""

    def __init__(self, path: str):
        self.path = path

    def fetch(self) -> dict:
        return pp.fetch_xlsx(self.path)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild freyja.xml automatically when the sheet changes.")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S, metavar="SEC",
                    help=f"seconds between checks (default {DEFAULT_INTERVAL_S}; minimum 2)")
    ap.add_argument("--debounce", type=float, default=DEFAULT_DEBOUNCE_S, metavar="SEC",
                    help=f"seconds the data must stay unchanged before rebuilding (default {DEFAULT_DEBOUNCE_S})")
    ap.add_argument("--xlsx", metavar="FILE", help="watch a downloaded copy instead of the Google Sheet")
    ap.add_argument("--strict", action="store_true", help="missing ROM values fail the build instead of leaving joints unlimited")
    ap.add_argument("--no-archive", action="store_true", help="skip the CSV archive")
    ap.add_argument("--template", type=Path, default=pp.TEMPLATE)
    ap.add_argument("--output", type=Path, default=pp.OUTPUT)
    args = ap.parse_args(argv)
    if args.interval < 2:
        ap.error("--interval must be at least 2 seconds (Google limits read requests)")
    if args.debounce < 0:
        ap.error("--debounce cannot be negative")
    return args


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # never crash on an odd character in the console
    args = parse_args(argv)
    try:
        source = XlsxSource(args.xlsx) if args.xlsx else pp.GoogleSheetSource()
    except pp.SheetAccessError as e:  # nothing configured: retrying cannot help
        sys.exit(str(e))

    def build(tables):
        return pp.build_model(tables, template=args.template, output=args.output, strict=args.strict,
                              archive=not args.no_archive,
                              snapshot_dir=pp.PARAMS_DIR if args.output == pp.OUTPUT else None)

    watcher = Watcher(source, build, args.template, args.interval, args.debounce)
    log(f"watching {'xlsx ' + args.xlsx if args.xlsx else 'the Google Sheet'} every {args.interval:g}s "
        f"(rebuild after {args.debounce:g}s of quiet) -> {args.output.name}. Ctrl+C to stop.")
    try:
        while True:
            nap(max(0.0, watcher.step()))
    except KeyboardInterrupt:
        log("stopped (Ctrl+C)")


if __name__ == "__main__":
    main()
