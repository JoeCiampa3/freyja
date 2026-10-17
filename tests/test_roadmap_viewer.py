"""
Roadmap T8: the viewer (tools/roadmap/viewer/). Two kinds of test.

Static: the vendored files are the pinned ones, nothing loads from outside the page's own directory, the markup is compatible with the
server's Content-Security-Policy, and the server serves every file the page needs.

Logic: app.js keeps its pure logic (index, active leaves, outline, keyboard navigation, query resolution, blocker chain, Markdown) in
window.RoadmapLogic. These tests run it in a headless Chromium-family browser (Edge, Chrome or Chromium) on a generated page, against
expected values that Python computes independently from the library. They are skipped, with the reason, when no such browser is installed.
No server and no socket is involved: the page is a file.

Run from the repo root:
    python -m pytest tests/test_roadmap_viewer.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from rmhelp import REPO, leaf, make

import roadmap
from roadmap import fixture, query, render, server

VIEWER = REPO / "tools" / "roadmap" / "viewer"
INDEX = (VIEWER / "index.html").read_text(encoding="utf-8")
APP = (VIEWER / "app.js").read_text(encoding="utf-8")


# ---- static

def test_vendored_files_are_the_pinned_ones_and_recorded_beside_them():
    record = (VIEWER / "VENDORED.md").read_text(encoding="utf-8")
    for name, version, licence in (("d3.min.js", "7.9.0", "ISC"), ("marked.min.js", "12.0.2", "MIT")):
        digest = hashlib.sha256((VIEWER / name).read_bytes()).hexdigest()
        row = next(l for l in record.splitlines() if l.startswith(f"| `{name}`"))
        assert digest in row and version in row and licence in row, name
        assert (VIEWER / (name.split(".")[0] + ".LICENSE.txt")).stat().st_size > 500
    head = (VIEWER / "d3.min.js").read_text(encoding="utf-8")[:120]
    assert "v7.9.0" in head
    assert "marked v12.0.2" in (VIEWER / "marked.min.js").read_text(encoding="utf-8")[:120]
    assert b"\r" not in (VIEWER / "d3.min.js").read_bytes() and b"\r" not in (VIEWER / "marked.min.js").read_bytes()  # LF, so the hash survives a checkout


def test_nothing_loads_from_outside_the_viewer_directory():
    scripts = re.findall(r'<script[^>]*\bsrc="([^"]+)"', INDEX)
    assert scripts == ["d3.min.js", "marked.min.js", "app.js"]
    assert all((VIEWER / s).is_file() for s in scripts)
    assert not re.findall(r'<link[^>]+href=', INDEX) and not re.findall(r"@import|url\(", INDEX)
    for name, text in (("index.html", INDEX), ("app.js", APP)):
        urls = [u for u in re.findall(r"https?://[^\s\"')]+", text) if u != "http://www.w3.org/2000/svg"]
        assert urls == [], (name, urls)
    assert "cdn" not in INDEX.lower() and "cdn" not in APP.lower()


def test_the_page_is_compatible_with_the_content_security_policy():
    """script-src 'self' only: no inline script, no inline event handler, no eval."""
    assert not re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", INDEX)
    assert not re.search(r"\son[a-z]+\s*=", re.sub(r"<style.*?</style>", "", INDEX, flags=re.S))
    assert "eval(" not in APP and "new Function" not in APP and "document.write" not in APP
    assert "javascript:" not in INDEX


def test_app_js_never_builds_html_from_data_except_through_the_markdown_renderer():
    sites = [m.start() for m in re.finditer(r"innerHTML|insertAdjacentHTML|outerHTML", APP)]
    assert len(sites) == 1 and "renderMarkdown(info.body)" in APP[sites[0] - 80: sites[0] + 80]


def test_the_server_serves_the_page_and_every_file_it_needs(tmp_path):
    app = server.App(make(tmp_path / "r", {"rm.root": {"title": "T"}}), port=8765)
    h = {"Host": "127.0.0.1:8765"}
    page = app.handle("GET", "/", h)
    assert page.status == 200 and b"roadmap-token" in page.body and b"__ROADMAP_TOKEN__" not in page.body
    for name in ("d3.min.js", "marked.min.js", "app.js", "VENDORED.md", "d3.LICENSE.txt", "marked.LICENSE.txt"):
        r = app.handle("GET", "/" + name, h)
        assert r.status == 200 and r.body == (VIEWER / name).read_bytes(), name
    assert app.handle("GET", "/d3.min.js", h).headers["Content-Type"].startswith("text/javascript")


def test_the_status_glyphs_and_palette_cover_every_status_the_library_can_emit():
    from roadmap.derive import STATUSES
    for s in STATUSES:
        assert f'"{s}"' in APP.split("const STATUS = {")[1].split("};")[0].replace(": {", '": {').replace(" ", "") or re.search(rf"\b{s}\b", APP.split("const STATUS = {")[1].split("};")[0]), s
        assert f"--c-{s}:" in INDEX, s
        assert f".s-{s} " in INDEX, s


# ---- logic, in a headless browser

def find_browser():
    names = ["msedge", "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(p):
            return p
    return None


BROWSER = find_browser()


def dump_dom(url, workdir):
    """The DOM after scripts ran. A pipe captures nothing from the Windows msedge launcher, so there the output goes through a file."""
    base = ["--headless", "--disable-gpu", "--no-sandbox", f"--user-data-dir={workdir / 'profile'}", "--allow-file-access-from-files", "--window-size=1500,900", "--virtual-time-budget=20000", "--dump-dom"]
    if os.name == "nt":
        out = workdir / "dom.txt"
        quoted = ",".join(f'"{a}"' for a in base + [url])
        ps = f'$p = Start-Process -FilePath "{BROWSER}" -ArgumentList {quoted} -RedirectStandardOutput "{out}" -RedirectStandardError "{workdir / "err.txt"}" -Wait -PassThru -NoNewWindow; exit $p.ExitCode'
        proc = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        try:
            proc.wait(timeout=90)  # no pipe to drain: the browser's helper processes inherit it and can outlive the launcher
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            pytest.fail("the headless browser did not finish within 90 s")
        return out.read_text(encoding="utf-8") if out.exists() else ""
    return subprocess.run([BROWSER, *base, url], capture_output=True, text=True, timeout=90).stdout


HARNESS = r"""
<!doctype html><meta charset="utf-8"><title>viewer logic</title>
<script>window.ROADMAP_TEST = true; window.DATA = __DATA__;</script>
<script src="__VIEWER__/d3.min.js"></script><script src="__VIEWER__/marked.min.js"></script><script src="__VIEWER__/app.js"></script>
<pre id="out">pending</pre>
<script>
const L = window.RoadmapLogic, D = window.DATA, fails = []; let checks = 0;
const check = (name, ok, detail) => { checks++; if (!ok) fails.push(name + (detail === undefined ? "" : ": " + JSON.stringify(detail))); };
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
try {
  // --- index
  const idx = L.buildIndex(D.state, false);
  check("root", idx.rootId === D.root, [idx.rootId, D.root]);
  check("live node count", Object.keys(idx.depthOf).length === D.live_count, [Object.keys(idx.depthOf).length, D.live_count]);
  for (const [id, kids] of Object.entries(D.children)) check("children of " + id, eq(idx.children[id], kids), [idx.children[id], kids]);
  check("leaf count at the root", idx.leafCount[idx.rootId] === D.leaf_total, [idx.leafCount[idx.rootId], D.leaf_total]);
  const withSup = L.buildIndex(D.state, true);
  check("superseded shown on request", Object.keys(withSup.depthOf).length === Object.keys(D.state.nodes).length);
  // --- navigation against Python's graph
  for (const [id, want] of Object.entries(D.nav)) for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]) {
    const got = L.navigate(idx, id, key);
    if (got !== want[key]) { check("navigate " + key + " from " + id, false, [got, want[key]]); }
  }
  checks += Object.keys(D.nav).length * 4;
  check("navigate ignores other keys and unknown ids", L.navigate(idx, idx.rootId, "x") === idx.rootId && L.navigate(idx, "rm.nope", "ArrowUp") === "rm.nope");
  // --- query resolution, parity with tools/roadmap/query.py
  for (const [q, want] of D.queries) {
    const got = L.resolveQuery(D.state.nodes, q);
    check("query " + JSON.stringify(q), got.status === want.status && eq(got.ids, want.ids), [got.status, got.ids, want]);
  }
  // --- blocker chain
  for (const [id, want] of Object.entries(D.chains)) {
    const c = L.blockerChain(D.state.nodes, id, 60);
    const col = {}; c.cols.forEach((ids, i) => ids.forEach((n) => { col[n] = i; }));
    check("chain nodes of " + id, eq(c.cols.flat().sort(), want.nodes), [c.cols.flat().sort(), want.nodes]);
    check("chain edges of " + id, eq(c.edges.map((e) => e.join(">")).sort(), want.edges), [c.edges, want.edges]);
    check("chain flows left to right into " + id, c.edges.every(([b, n]) => col[b] < col[n]) && col[id] === c.cols.length - 1);
  }
  check("a chain is capped", L.blockerChain(D.state.nodes, D.big_chain, 3).count <= 3 && L.blockerChain(D.state.nodes, D.big_chain, 3).truncated === true);
  // --- brief 2 T7: active leaves and the outline
  check("active leaves are the leaves marked active", eq(L.activeLeaves(idx), D.active_leaves) && D.active_leaves.length > 0, L.activeLeaves(idx));
  // --- outline
  for (const c of D.outline_filters) {
    const got = L.outlineVisible(idx, c.text, c.statuses);
    check("outline filter " + JSON.stringify([c.text, c.statuses]), c.visible === null ? got === null : eq(got, c.visible), [got && got.length, c.visible && c.visible.length]);
  }
  const rowsOf = (o) => L.outlineRows(idx, o).map((r) => [r.id, r.depth]);
  check("a collapsed outline shows only the root", eq(rowsOf({ open: new Set(), text: "", statuses: [] }), [[D.root, 0]]));
  check("an outline opened along a path lists the siblings along it", eq(rowsOf({ open: new Set(D.path_open), text: "", statuses: [] }), D.outline_rows_path));
  check("under a filter the outline lists matches and their ancestors, in tree order, regardless of what is open", eq(rowsOf({ open: new Set(), text: D.outline_filters[0].text, statuses: [] }), D.outline_rows_filter));
  check("outline rows know whether they have children", L.outlineRows(idx, { open: new Set(D.path_open), text: "", statuses: [] }).every((r) => r.hasKids === (D.children[r.id].length > 0)));
  // --- subtree and relative depth
  const st = L.subtree(idx, idx.rootId, 2, 0);
  check("subtree depth", st.children.every((c) => c.children.every((g) => g.children.length === 0 && g.hidden === idx.children[g.id].length)));
  check("relative depth", L.relativeDepth(idx, D.deep, idx.rootId) === idx.depthOf[D.deep] && L.relativeDepth(idx, idx.rootId, D.deep) === -1);
  // --- markdown
  const md = (s) => L.renderMarkdown(s);
  // the <\/ below keeps the HTML parser from ending this script element
  const bad1 = md("hello <script>alert(1)<\/script> world <img src=x onerror=alert(1)>");
  check("raw html is escaped", !/<script|<img/i.test(bad1) && bad1.includes("&lt;script&gt;"), bad1);
  const bad2 = md("[click](javascript:alert(1)) and [ok](https://example.org/a) and [rel](../x.md) and ![pic](http://evil/x.png)");
  check("unsafe links are dropped", !/href="javascript/i.test(bad2) && !/<img/i.test(bad2) && /href="https:\/\/example.org\/a"/.test(bad2) && !/href="\.\.\/x\.md"/.test(bad2), bad2);
  check("safe links get rel and target", /rel="noopener noreferrer" target="_blank"/.test(bad2));
  const ok = md("# Title\n\n- one\n- **two**\n\n`code` and\n\n```\nblock <b>\n```\n");
  check("markdown renders", /<h1>Title<\/h1>/.test(ok) && /<strong>two<\/strong>/.test(ok) && /<code>code<\/code>/.test(ok) && ok.includes("block &lt;b&gt;"), ok);
  check("markdown of nothing", md("") === "" || md(null) === "");
  // --- routing
  check("route round trip", L.routeParse(L.routeFormat("rm.a-b")) === "rm.a-b" && L.routeParse("#/other") === null && L.routeParse("") === null && L.routeParse("#/node/%E0%A4%A") === null);
  // --- a broken graph still gets an index
  const broken = L.buildIndex(D.broken, false);
  check("several roots get a virtual root", broken.rootId === L.VROOT && broken.children[L.VROOT].length === D.broken_roots, broken.rootId);
  check("an empty roadmap has no root", L.buildIndex({ nodes: {} }, false).rootId === null);
  check("status info falls back to unknown", L.statusInfo("nonsense").label === "unknown");
} catch (e) { fails.push("exception: " + e + " " + (e.stack || "")); }
document.getElementById("out").textContent = JSON.stringify({ fails, checks });
</script>
"""


def expected_brief2(rm, live, children, parent, root, depth, deep):
    """What brief 2's pure sidebar logic must return, computed here from the library's states and the stated rules, never from app.js."""
    active_leaves = sorted(i for i in live if not children[i] and rm.nodes[i].active)

    def chain(i):  # root .. i
        out = []
        while i:
            out.append(i)
            i = parent[i]
        return out[::-1]

    def visible(text, statuses):
        t = text.strip().lower()
        if not t and not statuses:
            return None
        hit = [i for i in live if (not t or t in i.lower() or t in rm.nodes[i].title.lower()) and (not statuses or rm.status(i) in statuses)]
        vis = set(hit)
        for i in hit:
            vis.update(chain(i))
        return sorted(vis)

    filters = [{"text": "femur", "statuses": []}, {"text": "", "statuses": ["ready"]}, {"text": "", "statuses": ["done", "blocked"]},
               {"text": "cable", "statuses": ["ready"]}, {"text": "zzzzzz", "statuses": []}, {"text": "  ", "statuses": []}]
    for f in filters:
        f["visible"] = visible(f["text"], f["statuses"])
    assert filters[0]["visible"] and len(filters[0]["visible"]) > 1 and filters[-1]["visible"] is None

    def rows(open_set, vis):
        out = []

        def walk(i, d):
            if vis is not None and i not in vis:
                return
            out.append([i, d])
            if vis is not None or i in open_set:
                for c in children[i]:
                    walk(c, d + 1)
        walk(root, 0)
        return out
    path_open = chain(deep)
    return {"active_leaves": active_leaves, "outline_filters": filters, "path_open": path_open,
            "outline_rows_path": rows(set(path_open), None), "outline_rows_filter": rows(set(), set(filters[0]["visible"]))}


def expected_for(root):
    rm = roadmap.compute(root)
    state = render.state_dict(rm)
    live = [i for i in sorted(rm.nodes) if not rm.nodes[i].superseded]
    children = {i: [c for c in rm.children(i) if not rm.nodes[c].superseded] for i in live}
    parent = {i: rm.nodes[i].parent for i in live}
    roots = [i for i in live if parent[i] is None]
    assert len(roots) == 1
    leaf_total = sum(1 for i in live if not children[i])

    def depth(i):
        return 0 if parent[i] is None else 1 + depth(parent[i])
    nav = {}
    for i in live:
        sib = children[parent[i]] if parent[i] else roots
        k = sib.index(i)
        nav[i] = {"ArrowUp": parent[i] or i, "ArrowDown": children[i][0] if children[i] else i,
                  "ArrowLeft": sib[max(0, k - 1)], "ArrowRight": sib[min(len(sib) - 1, k + 1)]}
    ids = sorted(rm.nodes)
    some = ids[3], ids[7], ids[11]
    queries = ["", "   ", ids[5], ids[5][3:], ids[5].upper(), "  " + ids[8] + " ", "femur", "FEMUR", "gearbox", "cable 0", "no such thing", "rm.zzzz", "zzzz",
               "n00", "rm.n0", "bench", "mount", "rm.nope-cable", "rm.cable", "cabel", "gearbx", "pelvis-", "rm.n01-gearbox", "x", "rm.", "rm"] + [i[:-3] for i in some] + [i + "x" for i in some]
    expected_q = []
    for q in queries:
        status, got = query.resolve(rm, q)
        expected_q.append([q, {"status": status, "ids": got if status != "ok" else [got]}])
    blocked = [i for i in live if rm.uncleared(i) and not children[i]]
    chains = {}
    for i in blocked[:6]:
        seen, edges, queue = {i}, set(), [i]
        while queue:
            n = queue.pop()
            for b in rm.uncleared(n):
                edges.add(f"{b}>{n}")
                if b not in seen:
                    seen.add(b)
                    queue.append(b)
        chains[i] = {"nodes": sorted(seen), "edges": sorted(edges)}
    big = max(blocked, key=lambda i: len(chains[i]["nodes"]) if i in chains else 0)
    deep = max(live, key=depth)
    # a deliberately broken state: two roots, one node whose parent is missing
    broken = {"nodes": {"rm.a": {"title": "A", "status": "ready", "kind": "leaf", "parent": None},
                        "rm.b": {"title": "B", "status": "ready", "kind": "leaf", "parent": None},
                        "rm.c": {"title": "C", "status": "blocked", "kind": "leaf", "parent": "rm.gone"}}}
    return {"state": state, "root": roots[0], "live_count": len(live), "children": children, "leaf_total": leaf_total, "max_depth": max(depth(i) for i in live),
            "nav": nav, "queries": expected_q, "chains": chains, "big_chain": big, "deep": deep, "broken": broken, "broken_roots": 3, **expected_brief2(rm, live, children, parent, roots[0], depth, deep)}


@pytest.fixture(scope="module")
def logic_result(tmp_path_factory):
    if BROWSER is None:
        pytest.skip("no Chromium-family browser (msedge, chrome, chromium) found; the viewer logic tests need one")
    work = tmp_path_factory.mktemp("viewer")
    root = work / "fx"
    fixture.generate(120, root, seed=4)
    page = work / "harness.html"
    data = json.dumps(expected_for(root), sort_keys=True).replace("</", "<\\/")
    page.write_text(HARNESS.replace("__DATA__", data).replace("__VIEWER__", VIEWER.resolve().as_uri()), encoding="utf-8")
    dom = dump_dom(page.resolve().as_uri(), work)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    assert m, "the harness page produced no output; DOM began: " + dom[:300]
    text = m.group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    assert text != "pending", "the harness script did not run to the end"
    return json.loads(text)


def test_viewer_logic_passes_in_a_real_browser_engine(logic_result):
    assert logic_result["fails"] == [], logic_result["fails"][:8]
    assert logic_result["checks"] > 400  # the assertions really ran: a count, so an empty harness cannot pass


def test_the_harness_detects_a_wrong_answer(tmp_path):
    """Mutation: the same harness against a deliberately wrong expectation must report failures."""
    if BROWSER is None:
        pytest.skip("no Chromium-family browser found")
    root = tmp_path / "fx"
    fixture.generate(60, root, seed=4)
    exp = expected_for(root)
    exp["root"] = "rm.wrong"
    exp["queries"][4][1]["ids"] = ["rm.wrong"]
    first = next(iter(exp["nav"]))
    exp["nav"][first]["ArrowDown"] = "rm.wrong"
    page = tmp_path / "h.html"
    page.write_text(HARNESS.replace("__DATA__", json.dumps(exp).replace("</", "<\\/")).replace("__VIEWER__", VIEWER.resolve().as_uri()), encoding="utf-8")
    dom = dump_dom(page.resolve().as_uri(), tmp_path)
    out = json.loads(re.search(r'<pre id="out">(.*?)</pre>', dom, re.S).group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    names = " ".join(out["fails"])
    assert "root" in names and "query" in names and "navigate" in names


def test_python_and_the_viewer_agree_on_the_query_rules_for_the_documented_cases(tmp_path):
    root = fixture.generate(30, tmp_path / "f", seed=1) and tmp_path / "f"
    rm = roadmap.compute(root)
    ids = sorted(rm.nodes)
    assert query.resolve(rm, ids[2])[0] == "ok" and query.resolve(rm, "zzz")[0] == "none" and query.resolve(rm, "n0")[0] == "ambiguous"
