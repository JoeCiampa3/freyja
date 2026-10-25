"""analysis/makehuman_v2.py and analysis/makehuman_fetch.py: the v2 .mhm differs from v1 by exactly the lines the brief names, v1 is untouched, the MakeHuman
readouts follow the Ruler's own arithmetic, and the pinned MakeHuman inputs verify by hash. Offline."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

import makehuman_fetch as F  # noqa: E402
import makehuman_v2 as V2  # noqa: E402

V1 = REPO / "data/makehuman/freyja-body-v1.mhm"


def test_v1_mhm_is_untouched():
    assert hashlib.sha256(V1.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12] == V2.V1_MHM_SHA256_12      # LF form, as committed


def test_v2_differs_from_v1_by_exactly_the_named_lines():
    v1 = V1.read_text().splitlines()
    v2 = V2.v2_mhm_text(V1.read_text()).splitlines()
    removed = [l for l in v1 if l not in v2]
    added = [l for l in v2 if l not in v1]
    assert removed == ["modifier macrodetails-height/Height 0.623000", "pose standing02.bvh"]
    assert added == ["modifier macrodetails-height/Height 0.625000", "modifier measure/measure-upperleg-height-decr|incr 0.269000",
                     "modifier measure/measure-lowerleg-height-decr|incr -0.515000"]
    assert len(v2) == len(v1) + 1                                       # 2 removed, 3 added
    assert [l for l in v2 if l in v1] == [l for l in v1 if l in v2]      # the rest keeps its order


def test_committed_v2_is_what_the_function_makes():
    assert (REPO / "data/makehuman/freyja-body-v2.mhm").read_text() == V2.v2_mhm_text(V1.read_text())


def test_v2_mhm_edit_refuses_a_v1_that_has_changed():
    with pytest.raises(ValueError):
        V2.v2_mhm_text("modifier macrodetails-height/Height 0.5\n")


def test_measure_follows_the_rulers_arithmetic_open_list_not_closed():
    V = np.array([[0.0, 0, 0], [0.3, 0, 0], [0.3, 0.4, 0], [0, 0, 0]])   # dm
    assert V2.mh_measure_cm(V, [0, 1, 2]) == pytest.approx(10 * (0.3 + 0.4))          # open: no segment back to the first vertex
    assert V2.mh_measure_cm(V, [0, 1, 2, 3]) == pytest.approx(10 * (0.3 + 0.4 + 0.5))  # closed by repeating the first vertex
    assert V2.mh_measure_cm(V, [0, 2]) == pytest.approx(10 * 0.5)                      # a chord is its length


def test_height_is_the_body_bounding_box_in_y_in_cm():
    V = np.zeros((5, 3))
    V[:, 1] = [0.1, 1.7, 0.9, -0.2, 3.0]
    assert V2.height_cm(V, n_body=4) == pytest.approx(10 * 1.9)           # the fifth vertex is a helper and is ignored


def test_manifest_verify_reports_missing_and_changed_files(tmp_path):
    (tmp_path / "a.target").write_bytes(b"abc")
    (tmp_path / "b.target").write_bytes(b"xyz")
    man = {"files": {"a.target": {"sha256": hashlib.sha256(b"abc").hexdigest(), "bytes": 3},
                     "b.target": {"sha256": hashlib.sha256(b"not xyz").hexdigest(), "bytes": 7},
                     "c.target": {"sha256": hashlib.sha256(b"c").hexdigest(), "bytes": 1}}}
    bad = F.verify(man, tmp_path)
    assert bad == {"missing": ["c.target"], "changed": ["b.target"]}


def test_fetch_downloads_only_what_fails_verification_and_refuses_a_wrong_hash(tmp_path):
    good = b"good bytes"
    man = {"commit": "c0ffee", "base_url": "https://example.invalid/raw", "targets_path": "t", "files": {"x/y.target": {"sha256": hashlib.sha256(good).hexdigest(), "bytes": len(good)}}}
    calls = []

    def ok(url):
        calls.append(url)
        return good

    F.fetch(man, tmp_path, opener=ok)
    assert (tmp_path / "x/y.target").read_bytes() == good
    assert calls == ["https://example.invalid/raw/c0ffee/t/x/y.target"]
    F.fetch(man, tmp_path, opener=ok)
    assert len(calls) == 1                                                  # second run finds the file verified and downloads nothing
    (tmp_path / "x/y.target").write_bytes(b"corrupt")
    with pytest.raises(F.FetchError):
        F.fetch(man, tmp_path, opener=lambda url: b"still wrong")
    assert (tmp_path / "x/y.target").read_bytes() == b"corrupt"             # a bad download never replaces the file


def test_tracked_base_obj_matches_its_pin():
    p = REPO / "data/makehuman/base.obj"
    man = json.loads((REPO / "data/makehuman/mhm_sources.json").read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest() == man["base_obj"]["sha256"]
    assert man["base_obj"]["sha256"].startswith("8e761e66")
    assert "CC0" in p.read_text(errors="replace")[:600]
    assert man["targets_license"]["spdx"] == "CC0-1.0" and man["commit"]


def test_manifest_lists_each_target_once_with_a_64_hex_hash():
    man = json.loads((REPO / "data/makehuman/mhm_sources.json").read_text())
    assert len(man["files"]) > 100
    for rel, rec in man["files"].items():
        assert rel.endswith(".target") and len(rec["sha256"]) == 64 and rec["bytes"] > 0
