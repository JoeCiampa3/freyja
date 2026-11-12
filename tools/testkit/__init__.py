"""
testkit: what `fy test` and `fy state` use to avoid repeating a test run whose inputs have not changed (memo 61). Staleness is a hash
mismatch (CONVENTIONS section 1), here applied to test results. Nothing in this module depends on time.

Three things:

1. The tree key. `tree_key(root)` is the sha256 of the path and content of every file git tracks or would track (untracked and not
   ignored) in the working tree, leaving out NEUTRAL: docs/STATE.md, which `fy state` writes, and docs/memos/, which is written after the
   run it reports. It follows content, not commits: committing the working tree does not change it.

2. The last-full-run record, `.fy-cache/last_full.json` (gitignored, per clone). A run of the whole suite (tests/ and checks/, nothing
   deselected by -k, -m or --deselect, not stopped early) writes its counts beside the tree key, and only when the key is the same before
   and after the run. `last_full(root)` returns the record only while the tree key still matches, so `fy state` can report that run
   instead of repeating it.

3. The input-keyed skip (testkit/plugin.py). A test marked `@pytest.mark.inputs("tools/envelope", "data/makehuman", ...)` names every
   repo path its result depends on. When it passes, the hash of those files is stored in `.fy-cache/inputs.json`; while the hash is
   unchanged the test is skipped with a reason that says so, and `--rerun-cached` runs it. The key always includes the test's own file
   and ALWAYS (the pinned requirements, pytest.ini, the conftests, this package) and the Python version. A failure is never skipped
   and forgets the stored pass.

The skip is sound only if the marker's list is complete: a file the test reads that is not under a listed path can change without the
test running. List directories generously. Files git ignores are not inputs (the envelope's voxel cache, the processed gait arrays);
a test that depends on one must not carry the marker.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CACHE_DIR = ".fy-cache"
INPUTS_FILE = "inputs.json"
LAST_FULL_FILE = "last_full.json"
INPUTS_SCHEMA = "fy-inputs-cache/1"
LAST_FULL_SCHEMA = "fy-last-full/1"

# Left out of the tree key: a trailing slash names a directory.
NEUTRAL = ("docs/STATE.md", "docs/memos/")
# Part of every input key when present: what decides how any test runs.
ALWAYS = ("requirements.txt", "pytest.ini", "tests/conftest.py", "checks/conftest.py", "tools/testkit")


# How `fy test` and `fy state` spread the suite over pytest-xdist's workers: one file on one worker at a time, because module-scoped fixtures
# build whole bodies and must not be rebuilt on every worker.
PARALLEL = ("-n", "auto", "--dist", "loadfile")


def xdist_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("xdist") is not None


class InputsError(ValueError):
    """An `inputs` marker that cannot be turned into a key."""


def repo_files(root) -> list:
    """Repo-relative posix paths of every file in the working tree that git tracks or would track, sorted."""
    out = subprocess.run(["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=root, check=True, capture_output=True).stdout
    names = sorted({n for n in out.decode("utf-8").split("\0") if n and not n.startswith(CACHE_DIR + "/")})  # never its own records, ignored or not
    return [n for n in names if (Path(root) / n).is_file()]  # a tracked file deleted from the working tree is listed by -c


_SHA = {}


def _sha(path: Path) -> str:
    st = path.stat()
    memo = (str(path), st.st_mtime_ns, st.st_size)
    if memo not in _SHA:
        _SHA[memo] = hashlib.sha256(path.read_bytes()).hexdigest()
    return _SHA[memo]


def _key(root, names) -> str:
    h = hashlib.sha256()
    for n in sorted(names):
        h.update(n.encode("utf-8") + b"\0" + _sha(Path(root) / n).encode("ascii") + b"\n")
    return h.hexdigest()


def _under(name: str, path: str) -> bool:
    return name == path or name.startswith(path.rstrip("/") + "/")


def tree_key(root, neutral=NEUTRAL) -> str:
    return _key(root, [n for n in repo_files(root) if not any(_under(n, x) if x.endswith("/") else n == x for x in neutral)])


def select(files, paths) -> list:
    """The files under each path (a file or a directory, repo-relative); a path that names none is an error."""
    out = set()
    for p in paths:
        q = str(p).replace("\\", "/").strip("/")
        hit = [n for n in files if _under(n, q)]
        if not hit:
            raise InputsError(f"inputs path {str(p)!r} names no file that git tracks or would track")
        out.update(hit)
    return sorted(out)


def inputs_key(root, paths, files=None) -> str:
    files = repo_files(root) if files is None else files
    if not paths:
        raise InputsError("the inputs marker needs at least one path")
    names = set(select(files, paths)) | {n for n in files if any(_under(n, a) for a in ALWAYS)}
    version = "%d.%d.%d" % sys.version_info[:3]
    return hashlib.sha256(f"{_key(root, names)}|python {version}".encode("ascii")).hexdigest()


# ---- the two files under .fy-cache ----------------------------------------------------------------------------------------------

def _read(path: Path, schema: str):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("schema") == schema else None


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, path)


def passed_store(root) -> dict:
    """node id -> the input key it last passed on."""
    data = _read(Path(root) / CACHE_DIR / INPUTS_FILE, INPUTS_SCHEMA)
    return dict(data["passed"]) if data and isinstance(data.get("passed"), dict) else {}


def record_passes(root, passed: dict, forget=()):
    store = passed_store(root)
    for nodeid in forget:
        store.pop(nodeid, None)
    store.update(passed)
    _write(Path(root) / CACHE_DIR / INPUTS_FILE, {"schema": INPUTS_SCHEMA, "passed": store})


def write_last_full(root, key: str, tests: dict):
    _write(Path(root) / CACHE_DIR / LAST_FULL_FILE, {"schema": LAST_FULL_SCHEMA, "tree_key": key, "tests": {k: int(tests[k]) for k in ("passed", "cached", "failed", "skipped")}})


def last_full(root):
    """The record of the last full run, or None when there is none or the tree has changed since (NEUTRAL aside)."""
    data = _read(Path(root) / CACHE_DIR / LAST_FULL_FILE, LAST_FULL_SCHEMA)
    if not data or not isinstance(data.get("tests"), dict) or data.get("tree_key") != tree_key(root):
        return None
    return data
