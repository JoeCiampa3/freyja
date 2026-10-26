"""Volume-extractor brief 6, item 9: the landmark picker hides helper geometry. An OBJ with more than 13,380 vertices (MakeHuman's base.obj) shows only the faces whose vertices are all in
the body, says so, and takes no picks. The pure block of index.html that decides this is run in a headless browser engine (skipped, with the reason, when none is installed); the
page's wiring is checked in its source."""
import json
import re
from pathlib import Path

import pytest
from test_roadmap_viewer import BROWSER, dump_dom

PICKER = Path(__file__).resolve().parents[1] / "tools" / "landmark-picker" / "index.html"
BLOCK = re.compile(r"// ---- helper geometry .*?\n(.*?)// ---- end helper geometry ----", re.S)

HARNESS = """<!doctype html><meta charset="utf-8"><title>picker logic</title><pre id="out">pending</pre>
<script>
%s
const res = {};
const quad = [0, 1, 2, 3], helperQuad = [5, 13379, 13380, 6], allHelper = [13380, 13381, 13382], tri = [10, 11, 12];
res.body_only = bodyFaces([quad, tri], 13380, 13380).length;                          // an exact body: nothing hidden
res.with_helpers = bodyFaces([quad, helperQuad, allHelper, tri], 19158, 13380);          // the two faces that touch a helper vertex go
res.has = [hasHelpers(13380, 13380), hasHelpers(13381, 13380), hasHelpers(19158, 13380), hasHelpers(100, 13380)];
document.getElementById("out").textContent = JSON.stringify(res);
</script>"""


def run_block(tmp_path):
    m = BLOCK.search(PICKER.read_text(encoding="utf-8"))
    assert m, "the pure helper-geometry block is missing from index.html"
    page = tmp_path / "h.html"
    page.write_text(HARNESS % m.group(1), encoding="utf-8")
    dom = dump_dom(page.resolve().as_uri(), tmp_path)
    out = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S).group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    assert out != "pending", "the harness script did not run"
    return json.loads(out)


def test_only_faces_whose_vertices_are_all_in_the_body_are_kept(tmp_path):
    if BROWSER is None:
        pytest.skip("no Chromium-family browser (msedge, chrome, chromium) found")
    r = run_block(tmp_path)
    assert r["body_only"] == 2
    assert r["with_helpers"] == [[0, 1, 2, 3], [10, 11, 12]]
    assert r["has"] == [False, True, True, False]


def test_the_page_says_helper_geometry_hidden_and_takes_no_picks_on_such_a_file():
    text = PICKER.read_text(encoding="utf-8")
    assert "Helper geometry hidden" in text and "helper geometry hidden" in text
    assert "picksEnabled = !helper" in text
    assert re.search(r"function pick\(e\) \{\s*if \(!mesh\) return;\s*if \(!picksEnabled\)", text), "pick() must return before assigning when picks are disabled"
    assert "bodyFaces(polys, nV, TOPOLOGY)" in text and "v.slice(0, 3 * TOPOLOGY)" in text             # the faces are filtered and the helper vertices are not in the geometry
    assert "const TOPOLOGY = 13380;" in text
