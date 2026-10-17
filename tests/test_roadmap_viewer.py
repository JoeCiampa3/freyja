"""
Roadmap T8: the viewer (tools/roadmap/viewer/). Two kinds of test.

Static: the vendored files are the pinned ones, nothing loads from outside the page's own directory, the markup is compatible with the
server's Content-Security-Policy, and the server serves every file the page needs.

Logic: app.js keeps its pure logic (index, icicle layout, keyboard navigation, query resolution, blocker chain, Markdown) in
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

sys.path.insert(0, str(REPO / "analysis"))
import tag_palette  # noqa: E402  (its NEUTRAL is the grey the viewer must use for "no tag")

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


def test_the_untagged_grey_in_the_page_is_the_one_the_tag_colours_were_checked_against():
    """Brief 3 T3: the grey for a node without the chosen tag is defined once, for both themes, and is the palette script's NEUTRAL."""
    assert INDEX.count(f"--c-untagged: {tag_palette.NEUTRAL};") == 1
    assert tag_palette.min_contrast(tag_palette.NEUTRAL) >= tag_palette.CONTRAST_MIN  # and it is visible on both themes too
    for needed in ('id="map-colour"', 'id="map-legend"'):
        assert needed in INDEX


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
  // --- relative depth
  check("relative depth", L.relativeDepth(idx, D.deep, idx.rootId) === idx.depthOf[D.deep] && L.relativeDepth(idx, idx.rootId, D.deep) === -1);

  // --- brief 2: child order, active leaves
  for (const [id, want] of Object.entries(D.ordered)) { const got = L.orderedChildren(idx, id); if (!eq(got, want)) check("child order of " + id, false, [got, want]); }
  checks += Object.keys(D.ordered).length;
  check("the child order ranks active, ready, expandable, blocked, in_progress, not_started, done", eq(L.CHILD_ORDER, ["active", "ready", "expandable", "blocked", "in_progress", "not_started", "done"]));
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
  // --- breadcrumb
  const cp = (f, ex) => L.crumbParts(idx, f, ex).map((q) => (q.kind === "gap" ? "…" : q.id));
  check("a deep breadcrumb collapses to root, …, grandparent, parent, node", eq(cp(D.deep, false), D.crumb_collapsed), cp(D.deep, false));
  check("clicking the … shows the full path", eq(cp(D.deep, true), D.crumb_full), cp(D.deep, true));
  check("a breadcrumb with four ancestors is never collapsed", eq(cp(D.crumb_four, false), D.crumb_four_full) && L.crumbParts(idx, D.crumb_four, false).every((q) => q.kind !== "gap"), cp(D.crumb_four, false));
  check("the root's breadcrumb is just the root", eq(cp(D.root, false), [D.root]));
  check("breadcrumb titles are cut at 28 characters and keep the full title", L.crumbParts(idx, D.deep, true).every((q) => q.kind === "gap" || (q.full === D.state.nodes[q.id].title && (D.shorts[q.id] && q.kind === "node" ? true : q.label.length <= 28 && (q.full.length <= 28 ? q.label === q.full : q.label.endsWith("…"))))));
  // --- brief 3 T1: the short label
  check("the data has short labels to test with", Object.values(D.shorts).filter(Boolean).length > D.children[D.root].length, D.shorts);
  for (const f of [D.deep, D.crumb_four, D.root]) for (const expanded of [true, false]) {
    const parts = L.crumbParts(idx, f, expanded).filter((q) => q.kind !== "gap");
    const want = parts.map((q, k) => [q.id, q.full, k === parts.length - 1 ? (q.full.length <= 28 ? q.full : q.full.slice(0, 27) + "…") : (D.shorts[q.id] || (q.full.length <= 28 ? q.full : q.full.slice(0, 27) + "…"))]);
    check("breadcrumb segments other than the last use the short label, the last keeps its title: " + f, eq(parts.map((q) => [q.id, q.full, q.label]), want), parts.map((q) => q.label));
  }
  check("a short label is used by breadcrumb segments, so some segment differs from its title", L.crumbParts(idx, D.deep, true).some((q) => q.kind === "node" && D.shorts[q.id] && q.label !== q.full.slice(0, 28)));
  check("shortOf falls back to the title and ignores an empty label", L.shortOf({ title: "T title", short: null }) === "T title" && L.shortOf({ title: "T title", short: "" }) === "T title" && L.shortOf({ title: "T", short: "S" }) === "S" && L.shortOf(undefined) === "");
  check("truncateTitle", L.truncateTitle("x".repeat(40), 28).length === 28 && L.truncateTitle("short", 28) === "short");
  // --- brief 3 T3: colour by tag
  const V = D.state.tag_vocabulary;
  check("the state carries the vocabulary the tags.yaml file holds", eq(V, D.vocab), Object.keys(V));
  check("the Colour by namespaces are those in the vocabulary, region before phase, and none without a vocabulary", eq(L.tagNamespaces(V), ["region", "phase"]) && eq(L.tagNamespaces({}), []) && eq(L.tagNamespaces(undefined), []) && eq(L.tagNamespaces({ zeta: [{ value: "a", colour: null }], region: [{ value: "b", colour: null }], alpha: [{ value: "c", colour: null }] }), ["region", "alpha", "zeta"]), L.tagNamespaces(V));
  for (const ns of Object.keys(D.vocab)) {
    const liveIds = Object.keys(idx.depthOf);
    const bad = liveIds.filter((id) => L.tagValueOf(idx.nodes[id], ns) !== D.tag_values[ns][id] || (L.tagFill(V, ns, idx.nodes[id]) || null) !== D.tag_fills[ns][id]);
    check("colour mapping for " + ns + ": every node's value and fill match Python's reading of the node files and tags.yaml", bad.length === 0, bad.slice(0, 3).map((id) => [id, L.tagValueOf(idx.nodes[id], ns), L.tagFill(V, ns, idx.nodes[id]), D.tag_values[ns][id], D.tag_fills[ns][id]]));
    check("colour mapping for " + ns + ": some nodes are tagged and some are not, so the grey fallback is real", liveIds.some((id) => D.tag_fills[ns][id]) && liveIds.some((id) => D.tag_fills[ns][id] === null), ns);
    const lg = L.legendEntries(idx, V, ns);
    check("legend for " + ns + ": every vocabulary value in file order with its count, and the untagged count", eq(lg.entries.map((e) => e.value), D.vocab_order[ns]) && lg.entries.every((e) => e.count === D.tag_legend[ns][e.value] && e.colour === D.vocab_colour[ns][e.value]) && lg.none === D.tag_legend[ns]._none, lg);
    check("legend for " + ns + ": the counts add up to the nodes shown", lg.entries.reduce((s, e) => s + e.count, 0) + lg.none === liveIds.length);
    const only = D.busiest_region;
    check("a value that carries the node, and none: " + ns, ns !== "region" || (liveIds.filter((id) => L.carries(idx.nodes[id], ns, only)).length === D.tag_legend.region[only] && liveIds.filter((id) => L.carries(idx.nodes[id], ns, "_none")).length === D.tag_legend.region._none && L.carries(idx.nodes[liveIds[0]], ns, null) === true));
  }
  const vv = (...e) => e.map(([value, colour]) => ({ value, colour }));
  check("a value without a colour is drawn grey but still counted", L.tagFill({ region: vv(["head", null], ["neck", "#112233"]) }, "region", { tags: ["region:head"] }) === null && L.tagFill({ region: vv(["head", null], ["neck", "#112233"]) }, "region", { tags: ["region:neck"] }) === "#112233" && L.tagFill({ region: vv(["head", null]) }, "region", { tags: [] }) === null && L.tagFill({ region: vv(["head", null]) }, "region", { tags: ["region:zzz"] }) === null && L.tagFill({}, "region", { tags: ["region:head"] }) === null && L.legendEntries({ depthOf: { a: 0, b: 1 }, nodes: { a: { tags: ["region:head"] }, b: { tags: [] } } }, { region: vv(["head", null], ["neck", "#112233"]) }, "region").entries.map((e) => e.value + e.count).join() === "head1,neck0");
  check("a free tag is never a namespace value, and only the first value of a namespace colours a node", L.tagValueOf({ tags: ["arm", "x:region"] }, "region") === null && L.tagValueOf({ tags: ["region:head", "region:neck"] }, "region") === "head");
  for (const [q, want] of Object.entries(D.tag_queries)) {
    const got = L.outlineVisible(idx, q, []);
    check("search " + JSON.stringify(q) + " keeps the matching nodes and their ancestors", eq(got, want), [got && got.length, want.length]);
  }
  check("a tag search is not a text search, and combines with the status chips", L.tagQuery("tag:region:x") === "region:x" && L.tagQuery("  TAG:  cad ") === "cad" && L.tagQuery("tagline") === null && L.tagQuery("rm.tag:x") === null && L.tagQuery("tag:") === "" && eq(L.outlineVisible(idx, "tag:cad", ["done", "ready", "blocked", "active", "in_progress", "not_started", "expandable"]), L.outlineVisible(idx, "tag:cad", [])));
  const route = (id, p) => L.routeFormat(id, p);
  check("the hash is the plain route when the view is the default", route("rm.a-b") === "#/node/rm.a-b" && route("rm.a-b", {}) === "#/node/rm.a-b" && route("rm.a-b", { colour: undefined, only: null, map: false }) === "#/node/rm.a-b");
  for (const p of [{ colour: "region" }, { colour: "phase", only: "spec" }, { colour: "region", only: "_none" }, { colour: "region", only: "whole-body", map: "1" }, { map: "1" }]) {
    const h = route("rm.a-b", p), back = L.routeParams(h);
    check("the hash round trips " + JSON.stringify(p), L.routeParse(h) === "rm.a-b" && eq(back, p), [h, back]);
  }
  check("a malformed hash reads as no parameters, and unknown parameters are kept out", eq(L.routeParams("#/node/rm.a?"), {}) && eq(L.routeParams("#/other?colour=region"), {}) && eq(L.routeParams(""), {}) && eq(L.routeParams("#/node/rm.a?colour=region&zzz=1"), { colour: "region" }) && L.routeParse("#/node/rm.a?colour=region") === "rm.a");
  // --- focus layout: the shown nodes, the geometry, the links
  const LY = L.LAYOUT;
  const overlaps = (a, b) => a.x < b.x + b.w - 0.5 && b.x < a.x + a.w - 0.5 && a.y < b.y + b.h - 0.5 && b.y < a.y + a.h - 0.5;
  for (const c of D.shown) {
    const tag = c.focus + " depth " + c.depth + (c.more.length ? " expanded" : "");
    const lay = L.focusLayout(idx, c.focus, { depth: c.depth, more: new Set(c.more) });
    const cards = lay.items.filter((i) => i.kind === "card"), mores = lay.items.filter((i) => i.kind === "more");
    check("layout shows exactly the expected nodes: " + tag, eq(cards.map((i) => i.id).sort(), c.ids), [cards.length, c.ids.length]);
    check("layout offers the expected +k more cards: " + tag, eq(mores.map((i) => [i.of, i.count]).sort(), c.more_cards), mores.map((i) => [i.of, i.count]));
    let bad = [];
    for (let a = 0; a < lay.items.length; a++) {
      const A = lay.items[a];
      if (A.x < 0 || A.y < 0 || A.x + A.w > lay.width + 1e-6 || A.y + A.h > lay.height + 1e-6) bad.push(["outside", A.id]);
      for (let b = a + 1; b < lay.items.length; b++) if (overlaps(A, lay.items[b])) bad.push(["overlap", A.id, lay.items[b].id]);
    }
    check("no card overlaps another or leaves the canvas: " + tag, bad.length === 0, bad.slice(0, 3));
    const byKey = {}; for (const i of lay.items) byKey[i.key] = i;
    check("every card but the focus has exactly one link ending on its edge: " + tag, lay.links.length === lay.items.length - 1 && lay.links.every((lk) => {
      const t = byKey[lk.to], par = byKey[lk.from], pts = lk.pts, last = pts[pts.length - 1], first = pts[0];
      const onTop = Math.abs(last[1] - t.y) < 0.5 && last[0] >= t.x - 0.5 && last[0] <= t.x + t.w + 0.5;
      const onLeft = Math.abs(last[0] - t.x) < 0.5 && last[1] >= t.y - 0.5 && last[1] <= t.y + t.h + 0.5;
      return par && (onTop || onLeft) && Math.abs(first[0] - (par.x + par.w / 2)) < 0.5 && Math.abs(first[1] - (par.y + par.h)) < 0.5;
    }), lay.links.length);
    // compact layout: a node's childless children stack in one column; its interior children spread along one row, right of the column
    const byParent = {}; for (const i of lay.items) if (i.parent) (byParent[i.parent] = byParent[i.parent] || []).push(i);
    let shapeBad = [];
    for (const [par, kids] of Object.entries(byParent)) {
      const column = kids.filter((k) => k.column), row = kids.filter((k) => !k.column);
      if (column.some((k) => Math.abs(k.x - column[0].x) > 1e-6)) shapeBad.push(["column x", par]);
      for (let q = 1; q < column.length; q++) if (!(column[q].y > column[q - 1].y)) shapeBad.push(["column order", par]);
      if (row.some((k) => Math.abs(k.y - row[0].y) > 1e-6)) shapeBad.push(["row y", par]);
      for (let q = 1; q < row.length; q++) if (!(row[q].x > row[q - 1].x)) shapeBad.push(["row order", par]);
      if (column.length && row.length && !(row[0].x >= column[0].x + column[0].w)) shapeBad.push(["row right of column", par]);
      const childless = kids.filter((k) => k.kind === "card" && D.children[k.id].length === 0);
      if (childless.some((k) => !k.column)) shapeBad.push(["a childless child outside the column", par]);
      if (kids.some((k) => k.kind === "card" && D.children[k.id].length > 0 && k.column)) shapeBad.push(["an interior child in the column", par]);
      const want = (D.ordered[par] || []).filter((k) => kids.some((kk) => kk.id === k));
      const gotCol = column.filter((k) => k.kind === "card").map((k) => k.id), gotRow = row.map((k) => k.id);
      if (!eq(gotCol, want.filter((k) => D.children[k].length === 0)) || !eq(gotRow, want.filter((k) => D.children[k].length > 0))) shapeBad.push(["child order", par]);
      if (column.some((k) => k.kind === "more") && column[column.length - 1].kind !== "more") shapeBad.push(["more card last", par]);
      const P = byKey[par], left = Math.min.apply(null, kids.map((k) => k.x)), right = Math.max.apply(null, kids.map((k) => k.x + k.w));
      if (P.x + P.w / 2 < left - 0.5 || P.x + P.w / 2 > right + 0.5) shapeBad.push(["parent centred over its children", par]);
    }
    check("compact layout: childless children in one column, interior children in one row, in child order: " + tag, shapeBad.length === 0, shapeBad.slice(0, 3));
  }
  check("the focus node is the first item at the top left of the canvas padding", (() => { const lay = L.focusLayout(idx, D.root, { depth: 1, more: new Set() }); return lay.items[0].id === D.root && lay.items[0].y === LY.pad; })());
  check("a node with more than 8 children offers a +k more card at depth 1", L.focusLayout(idx, D.wide, { depth: 1, more: new Set() }).items.some((i) => i.kind === "more" && i.count === D.children[D.wide].length - 8));
  // --- automatic depth
  for (const f of [D.root, D.mixed, D.big_interior]) for (const wd of [380, 600, 900, 1300, 2000, 5000]) {
    const d = L.autoDepth(idx, f, wd);
    const w = L.focusLayout(idx, f, { depth: d, more: new Set() }).width;
    const useful = L.usefulDepth(idx, f);
    const next = d < Math.min(L.MAX_DEPTH, useful) ? L.focusLayout(idx, f, { depth: d + 1, more: new Set() }).width : Infinity;
    check("auto depth fits the width or is 1: " + f + " @" + wd, d >= 1 && d <= L.MAX_DEPTH && (w <= wd || d === 1), [d, w]);
    check("auto depth is the largest that fits: " + f + " @" + wd, next > wd, [d, next]);
  }
  check("auto depth never falls as the width grows", [D.root, D.mixed, D.big_interior].every((f) => { let last = 0; for (const wd of [300, 500, 800, 1200, 2000, 3000, 8000]) { const d = L.autoDepth(idx, f, wd); if (d < last) return false; last = d; } return true; }));
  check("useful depth is the height of the subtree", L.usefulDepth(idx, D.root) === D.max_depth, [L.usefulDepth(idx, D.root), D.max_depth]);
  // --- the map
  const markerStatuses = ["done", "ready", "active", "blocked", "expandable"];
  check("every leaf and stub status has its own marker shape", new Set(markerStatuses.map(L.markerShape)).size === markerStatuses.length, markerStatuses.map(L.markerShape));
  check("every status the library can emit has a marker shape", Object.keys(L.STATUS).every((s) => typeof L.markerShape(s) === "string" && L.markerShape(s) !== ""));
  check("a ring with no progress has no wedge, a full one is a disc, a half is an arc", L.ringWedge(0, 7) === "" && /A7,7/.test(L.ringWedge(0.5, 7)) && /A7,7/.test(L.ringWedge(1, 7)));
  const live = D.live_count, nBranch = D.children[D.root].length;
  for (const mode of ["radial", "top"]) {
    const M = L.mapLayout(idx, mode);
    const by = {}; for (const n of M.nodes) by[n.id] = n;
    check("map " + mode + ": every live node is placed once", M.nodes.length === live && Object.keys(by).length === live, M.nodes.length);
    check("map " + mode + ": one link per non-root node", M.links.length === live - 1 && M.links.every((lk) => by[lk.source] && by[lk.target] && idx.parent[lk.target] === lk.source));
    check("map " + mode + ": a sector for each first-layer branch, in tree order", eq(M.sectors.map((q) => q.id), D.children[D.root]), M.sectors.map((q) => q.id));
    check("map " + mode + ": a sector's label is its branch's short label, and its title stays beside it", M.sectors.every((q) => q.label === (D.shorts[q.id] || D.state.nodes[q.id].title) && q.title === D.state.nodes[q.id].title) && M.sectors.every((q) => D.shorts[q.id]), M.sectors.map((q) => [q.label, q.title]));
    check("map " + mode + ": depth is carried by every node", M.nodes.every((n) => n.depth === idx.depthOf[n.id]));
    check("map " + mode + ": no two neighbours on a level are closer than the minimum gap", M.minGap >= L.MAP_MIN_GAP - 1e-6, M.minGap);
    check("map " + mode + ": titles appear at the zoom where neighbours are label-height apart", Math.abs(L.labelZoom(M) * M.minGap - L.LABEL_PX) < 1e-6);
    check("map " + mode + ": no coordinate is NaN", M.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y)));
    if (mode === "radial") {
      check("radial: the root is at the centre", by[D.root].x === 0 && by[D.root].y === 0 && by[D.root].r === 0);
      check("radial: a ring is a depth (radius = depth x step)", M.nodes.every((n) => Math.abs(n.r - n.depth * M.step) < 1e-6 && Math.abs(Math.hypot(n.x, n.y) - n.r) < 1e-6), M.step);
      let span = 0; for (const q of M.sectors) span += q.a1 - q.a0;
      check("radial: the sectors tile the circle", Math.abs(span - 2 * Math.PI) < 1e-6, span);
      const inSector = (n, q) => { const a = ((n.angle - q.a0) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI); return a <= (q.a1 - q.a0) + 1e-9; };
      const branchOf = (id) => { let c = id; while (idx.parent[c] && idx.parent[c] !== D.root) c = idx.parent[c]; return c; };
      check("radial: every node lies inside its own branch's sector", M.nodes.filter((n) => n.id !== D.root).every((n) => inSector(n, M.sectors.find((q) => q.id === branchOf(n.id)))));
    } else {
      check("top-down: a level is a row (y = depth x step)", M.nodes.every((n) => Math.abs(n.y - n.depth * M.step) < 1e-6), M.step);
      check("top-down: sectors are disjoint, ordered bands that contain their branch", M.sectors.every((q, k) => q.x1 > q.x0 && (k === 0 || q.x0 >= M.sectors[k - 1].x1 - 1e-6)) &&
        M.nodes.filter((n) => n.id !== D.root).every((n) => { const b = (() => { let c = n.id; while (idx.parent[c] && idx.parent[c] !== D.root) c = idx.parent[c]; return c; })(); const q = M.sectors.find((s2) => s2.id === b); return n.x >= q.x0 - 1e-6 && n.x <= q.x1 + 1e-6; }));
    }
  }
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


CHILD_RANK = ["active", "ready", "expandable", "blocked", "in_progress", "not_started", "done"]
MAX_KIDS = 8
TITLE_CUT = 28


def cut(title):
    return title if len(title) <= TITLE_CUT else title[:TITLE_CUT - 1] + "\u2026"


def expected_brief2(rm, live, children, parent, root, depth, deep):
    """What brief 2's pure logic must return, computed here from the library's states and the stated rules, never from app.js."""
    def rank(i):
        s = rm.status(i)
        return CHILD_RANK.index(s) if s in CHILD_RANK else len(CHILD_RANK)
    ordered = {i: sorted(children[i], key=lambda c: (rank(c), c)) for i in live if children[i]}
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
    interior_deep = next(i for i in chain(deep)[::-1] if children[i])
    four = next(i for i in live if depth(i) == 4)
    crumb_full = chain(deep)
    crumb_collapsed = [crumb_full[0], "\u2026", crumb_full[-3], crumb_full[-2], crumb_full[-1]]

    def visible_set(focus, depth_, more):
        out = []

        def rec(i, level):
            out.append(i)
            if level >= depth_ or not children[i]:
                return
            kids = ordered[i]
            take = kids if (i in more or len(kids) <= MAX_KIDS) else kids[:MAX_KIDS]
            for k in take:
                rec(k, level + 1)
        rec(focus, 0)
        return sorted(out)

    def more_cards(focus, depth_, more):
        out = []

        def rec(i, level):
            if level >= depth_ or not children[i]:
                return
            kids = ordered[i]
            if len(kids) > MAX_KIDS and i not in more:
                out.append([i, len(kids) - MAX_KIDS])
            for k in (kids if (i in more or len(kids) <= MAX_KIDS) else kids[:MAX_KIDS]):
                rec(k, level + 1)
        rec(focus, 0)
        return sorted(out)
    wide = max(live, key=lambda i: (len(children[i]), i))  # the 120-node fixture of seed 4 has one node of 9 children
    mixed = min((i for i in live if sum(1 for c in children[i] if not children[c]) >= 2 and any(children[c] for c in children[i])), key=lambda i: (depth(i), i), default=root)
    big_interior = max((i for i in live if children[i]), key=lambda i: (sum(1 for _ in rm.graph.descendants(i)), i))
    shown = []
    for focus, d, more in [(root, 1, []), (root, 2, []), (root, 3, []), (mixed, 2, []), (mixed, 4, []), (wide, 1, []), (wide, 1, [wide]), (wide, 3, []), (interior_deep, 3, []), (big_interior, 12, [])]:
        shown.append({"focus": focus, "depth": d, "more": more, "ids": visible_set(focus, d, set(more)), "more_cards": more_cards(focus, d, set(more))})
    return {"ordered": ordered, "active_leaves": active_leaves, "outline_filters": filters, "path_open": path_open,
            "outline_rows_path": rows(set(path_open), None), "outline_rows_filter": rows(set(), set(filters[0]["visible"])),
            "crumb_collapsed": crumb_collapsed, "crumb_full": crumb_full, "crumb_four": four, "crumb_four_full": chain(four),
            "shown": shown, "wide": wide, "mixed": mixed, "big_interior": big_interior}


def expected_tags(root, rm, live, parent):
    """Brief 3 T3, computed from the node files and roadmap/tags.yaml with plain Python (never from the viewer's code): the colour each node
    should be drawn in for each namespace (None: the grey), the legend counts, and the nodes a `tag:` search should keep."""
    import yaml
    vocab = yaml.safe_load((Path(root) / "roadmap" / "tags.yaml").read_text(encoding="utf-8"))["namespaces"]

    def value_of(i, ns):
        for t in rm.nodes[i].tags:
            if t.startswith(ns + ":"):
                return t.split(":", 1)[1]
        return None
    values = {ns: {i: value_of(i, ns) for i in live} for ns in vocab}
    fills = {ns: {i: (vocab[ns].get(v) if v is not None else None) for i, v in values[ns].items()} for ns in vocab}
    legend = {ns: {**{v: sum(1 for i in live if values[ns][i] == v) for v in vocab[ns]}, "_none": sum(1 for i in live if values[ns][i] is None)} for ns in vocab}

    def kept(tag):
        hit = {i for i in live if tag.lower() in [t.lower() for t in rm.nodes[i].tags]}
        out = set(hit)
        for i in hit:
            p = parent[i]
            while p:
                out.add(p)
                p = parent[p]
        return sorted(out)
    busiest = max(vocab["region"], key=lambda v: legend["region"][v])
    queries = [f"tag:region:{busiest}", "tag:phase:spec", "tag:cad", "TAG:CAD", "tag:  region:" + busiest + "  ", "tag:region:nonesuch", "tag:", "tag:arm", "tag:region", "Tag:phase:SIM"]
    wanted = {q: kept(q.strip()[4:].strip()) if q.strip()[4:].strip() else [] for q in queries}
    assert len(wanted[queries[0]]) > 3 and wanted["tag:region:nonesuch"] == [] and wanted["tag:cad"] and wanted["tag:cad"] == wanted["TAG:CAD"]
    assert wanted["tag:region"] == [] and wanted["tag:arm"], "free tag 'arm' exists in the fixture; the bare namespace is not a tag"
    as_state = {ns: [{"value": v, "colour": c} for v, c in vals.items()] for ns, vals in vocab.items()}  # the order of the file, as the state lists it
    return {"untagged": tag_palette.NEUTRAL, "vocab": as_state, "vocab_order": {ns: list(vals) for ns, vals in vocab.items()}, "vocab_colour": vocab, "tag_values": values, "tag_fills": fills, "tag_legend": legend, "tag_queries": wanted, "busiest_region": busiest}


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
    extra = expected_brief2(rm, live, children, parent, roots[0], depth, deep)
    shorts = {i: rm.nodes[i].short for i in live}  # from the node files, not from the state the viewer reads
    return {"shorts": shorts, **expected_tags(root, rm, live, parent), "state": state, "root": roots[0], "live_count": len(live), "children": children, "leaf_total": leaf_total, "max_depth": max(depth(i) for i in live),
            "nav": nav, "queries": expected_q, "chains": chains, "big_chain": big, "deep": deep, "broken": broken, "broken_roots": 3, **extra}


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
    assert logic_result["checks"] > 450  # the assertions really ran: a count, so an empty harness cannot pass


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
