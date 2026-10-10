"""
Run records (CONVENTIONS section 6): ids, git state, file hashes, deterministic JSON and schema
validation on write. The schema is docs/schemas/run-summary-1.schema.json.

A run record is an event: its run_id encodes the start time and nothing else in it is time-dependent.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import platform
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA_FILE = REPO / "docs" / "schemas" / "run-summary-1.schema.json"
RUNS_DIR = REPO / "sim" / "runs"
NAME_RE = re.compile(r"^[a-z0-9_-]+$")  # CONVENTIONS section 3 segment, without dots (the id's own separators)


class RecordError(ValueError):
    """A run record that does not satisfy run-summary/1."""


def make_run_id(scenario: str, start: dt.datetime) -> str:
    """run.<YYYYMMDD>-<HHMM>-<scenario>"""
    if not NAME_RE.match(scenario):
        raise ValueError(f"scenario name '{scenario}' must be lowercase letters, digits, underscore or hyphen")
    return f"run.{start:%Y%m%d-%H%M}-{scenario}"


def run_dir_name(run_id: str) -> str:
    return run_id.removeprefix("run.")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _git(repo, *args) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout


def git_state(repo=None) -> dict:
    """HEAD commit, whether tracked files differ from it, and the hash of `git diff HEAD` (None when
    clean). Untracked files do not count: they are not part of the commit the run claims to come from,
    and the run's own output directory is untracked until committed."""
    repo = repo or REPO
    commit = _git(repo, "rev-parse", "HEAD").decode().strip()
    diff = _git(repo, "diff", "HEAD")
    return {"git_commit": commit, "git_dirty": bool(diff), "diff_sha256": hashlib.sha256(diff).hexdigest() if diff else None}


def env_versions() -> dict:
    import mujoco
    import numpy
    return {"mujoco": mujoco.__version__, "python": platform.python_version(), "numpy": numpy.__version__}


def load_summaries(runs_dir=None) -> list:
    """Every sim/runs/*/summary.json, oldest run id first. Records are returned as written (not re-validated)."""
    found = [json.loads(p.read_text(encoding="utf-8")) for p in Path(runs_dir or RUNS_DIR).glob("*/summary.json")]
    return sorted(found, key=lambda r: r["run_id"])


def load_schema(path=None) -> dict:
    return json.loads(Path(path or SCHEMA_FILE).read_text(encoding="utf-8"))


def _plain(x):
    """numpy scalars and arrays to plain JSON types; refuse NaN and infinity (JSON cannot carry them)."""
    if hasattr(x, "tolist"):
        x = x.tolist()
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        raise RecordError(f"non-finite number {x} cannot be recorded")
    return x


def validate(record, schema=None):
    """Raise RecordError listing every violation; return silently when the record is valid."""
    import jsonschema
    validator = jsonschema.Draft202012Validator(schema or load_schema())
    errors = sorted(validator.iter_errors(record), key=lambda e: list(map(str, e.path)))
    if errors:
        raise RecordError("; ".join(f"{'.'.join(map(str, e.path)) or '<record>'}: {e.message}" for e in errors))


def dumps(record) -> str:
    """Deterministic JSON: sorted keys, two-space indent, LF, one trailing newline."""
    return json.dumps(_plain(record), indent=2, sort_keys=True, allow_nan=False) + "\n"


def write_summary(record, runs_dir=None, schema=None) -> Path:
    """Validate, then write <runs_dir>/<id minus 'run.'>/summary.json. Nothing is created when invalid."""
    plain = _plain(record)
    validate(plain, schema)
    path = Path(runs_dir or RUNS_DIR) / run_dir_name(plain["run_id"]) / "summary.json"
    text = dumps(plain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path
