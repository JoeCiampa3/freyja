"""Fetch and verify the MakeHuman target files that analysis/makehuman_attribution.py reads.

    python analysis/makehuman_fetch.py            # download what is missing or changed into data/makehuman/cache/targets, then verify
    python analysis/makehuman_fetch.py --verify   # verify only, no network
    python analysis/makehuman_fetch.py --pin DIR --used FILE.json   # (re)write the manifest from a fetched folder

The manifest is data/makehuman/mhm_sources.json: the upstream commit, every target's sha256 and size, the license of the targets folder and the pin of
base.obj (committed in this repo). Downloads come from the pinned commit, never from a branch, and a file whose hash differs from the manifest is
refused and never written. The cache is gitignored: the targets are tens of MB.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "data/makehuman/mhm_sources.json"
CACHE = REPO / "data/makehuman/cache/targets"


class FetchError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(manifest: dict, dest) -> dict:
    """{'missing': [...], 'changed': [...]} for the manifest's files under `dest` (no network)."""
    dest = Path(dest)
    out = {"missing": [], "changed": []}
    for rel, rec in manifest["files"].items():
        p = dest / rel
        if not p.exists():
            out["missing"].append(rel)
        elif sha256(p.read_bytes()) != rec["sha256"]:
            out["changed"].append(rel)
    return out


def _open(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def fetch(manifest: dict, dest, opener=_open, retries: int = 3) -> int:
    """Download every file that fails verification; return how many were downloaded. A wrong hash or a network failure raises FetchError."""
    dest = Path(dest)
    bad = verify(manifest, dest)
    todo = bad["missing"] + bad["changed"]
    for rel in todo:
        url = f"{manifest['base_url']}/{manifest['commit']}/{manifest['targets_path']}/{rel}"
        data, err = None, None
        for _ in range(retries):
            try:
                data = opener(url)
                break
            except Exception as e:                      # network errors are Joe's to hear about, not to guess around
                err = e
        if data is None:
            raise FetchError(f"network failure fetching {url}: {err}")
        if sha256(data) != manifest["files"][rel]["sha256"]:
            raise FetchError(f"{rel}: downloaded hash {sha256(data)[:12]} does not match the manifest {manifest['files'][rel]['sha256'][:12]}")
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return len(todo)


def pin(folder, used, old: dict) -> dict:
    """The manifest for the files in `used` (relative to the targets folder `folder`), keeping the commit and license fields of `old`."""
    folder = Path(folder)
    man = {k: v for k, v in old.items() if k != "files"}
    man["files"] = {}
    for rel in sorted(used):
        b = (folder / rel).read_bytes()
        man["files"][rel] = {"sha256": sha256(b), "bytes": len(b)}
    return man


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(MANIFEST)), ap.add_argument("--dest", default=str(CACHE))
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--pin", metavar="DIR"), ap.add_argument("--used", metavar="JSON")
    a = ap.parse_args(argv)
    man = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    if a.pin:
        used = json.loads(Path(a.used).read_text())
        new = pin(a.pin, used, man)
        Path(a.manifest).write_text(json.dumps(new, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"pinned {len(new['files'])} files")
        return 0
    if not a.verify:
        try:
            n = fetch(man, a.dest)
        except FetchError as e:
            print(f"STOP: {e}", file=sys.stderr)
            return 2
        print(f"downloaded {n} file(s)")
    bad = verify(man, a.dest)
    print(f"{len(man['files'])} files: {len(bad['missing'])} missing, {len(bad['changed'])} changed")
    return 1 if bad["missing"] or bad["changed"] else 0


if __name__ == "__main__":
    sys.exit(main())
