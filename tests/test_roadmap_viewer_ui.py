"""
Roadmap T8: the viewer's interface, in a headless Chromium-family browser. The real index.html and app.js are loaded from files, with
fetch and EventSource stubbed by a script placed before app.js, and a scripted session then drives the page (keyboard, clicks, history,
search, live updates) and checks the DOM. The expected answers come from Python's reading of the library, never from app.js. Skipped,
with the reason, when no browser is installed. No server and no socket is involved.

Run from the repo root:
    python -m pytest tests/test_roadmap_viewer_ui.py
"""
import json
import re

import pytest
from test_roadmap_viewer import BROWSER, INDEX, VIEWER, dump_dom, expected_for

from roadmap import fixture

UI_STUBS = r"""
<script>
window.DATA = __DATA__;
window.errors = [];
window.addEventListener("error", (e) => window.errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => window.errors.push("rejection: " + e.reason));
window.STATE_NOW = JSON.parse(JSON.stringify(window.DATA.state));
window.BODIES = {};
window.calls = [];
window.fetch = (url, opts) => {
  url = String(url);
  window.calls.push([url, (opts && opts.method) || "GET", opts && opts.headers]);
  const ok = (obj) => Promise.resolve({ ok: true, status: 200, headers: { get: () => "1" }, json: () => Promise.resolve(obj) });
  if (url.startsWith("/api/state")) return ok(JSON.parse(JSON.stringify(window.STATE_NOW)));
  if (url.startsWith("/api/node/")) { const id = decodeURIComponent(url.slice(10)); return ok({ id, title: "", path: "", body: window.BODIES[id] || "", references: { files: [], commits: [] } }); }
  if (url.startsWith("/api/open/") && window.OPEN_FAILS) return Promise.resolve({ ok: false, status: 500, headers: { get: () => "1" }, json: () => Promise.resolve({ error: "WinError 2: cannot find the file" }) });
  if (url.startsWith("/api/open/")) return ok({ opened: "roadmap/nodes/stub.md" });
  return Promise.reject(new Error("unexpected fetch " + url));
};
window.EventSource = function () { window.es = this; this.listeners = {}; this.addEventListener = (n, f) => { this.listeners[n] = f; }; setTimeout(() => this.onopen && this.onopen(), 0); };
</script>
"""

UI_TEST = r"""
<script>
(async () => {
  const D = window.DATA, fails = []; let checks = 0;
  const check = (name, ok, detail) => { checks++; if (!ok) fails.push(name + (detail === undefined ? "" : ": " + JSON.stringify(detail))); };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const key = (k, target) => (target || document.body).dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
  const title = (id) => D.state.nodes[id].title;
  const cur = () => ($("#crumbs .cur") || {}).textContent;
  const drawerTitle = () => ($("#drawer h3") || {}).textContent;
  const hash = () => decodeURIComponent(location.hash);
  const click = (el) => el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  const tool = (label) => $$("#crumbs .tools button").find((b) => b.getAttribute("aria-label") === label);
  const kids = D.children[D.root];
  try {
    await sleep(300);
    // --- boot
    check("no script errors at boot", window.errors.length === 0, window.errors);
    check("boots on the root", cur() === title(D.root) && $("#drawer").hidden === false && drawerTitle() === title(D.root), [cur(), drawerTitle()]);
    check("one band per live node", $$("svg.icicle g.band").length === D.live_count, $$("svg.icicle g.band").length);
    check("cards for the root and its children", $$("#view .card").length >= 1 + kids.length);
    check("problems badge counts errors and warnings", $("#badge").textContent === String(D.state.errors.length + D.state.warnings.length), $("#badge").textContent);
    check("status bar shows the node count and the live indicator", $("#statusbar").textContent.includes(D.state.node_count + " nodes") && $("#statusbar").textContent.includes("live"));
    // --- status is never colour alone
    check("every card carries a status label", $$("#view .card").every((c) => /(done|in progress|active|ready|expandable|blocked|not started|unknown|superseded)/.test(c.textContent)));
    check("every band has an accessible status", $$("svg.icicle g.band").every((g) => /, (done|in progress|active|ready|expandable|blocked|not started|unknown|superseded)/.test(g.getAttribute("aria-label"))));
    check("every band in the normal sidebar carries its status glyph as text, not colour alone", $$("svg.icicle g.band").every((g) => { const tx = g.querySelector("text"); return tx && /^[✓◐▶○+✕·?–!]/.test(tx.textContent); }), $$("svg.icicle g.band").filter((g) => !g.querySelector("text")).length);
    check("stub bands are hatched", $$("svg.icicle g.band").some((g) => g.querySelector("rect[fill^='url(#hatch)']")) === Object.values(D.state.nodes).some((n) => n.kind === "stub" && n.status !== "superseded"));
    check("legend names every status", ["done", "in progress", "active", "ready", "expandable", "blocked", "not started", "unknown"].every((s) => $(".legend").textContent.includes(s)));
    // --- keyboard: down, right, left, up, as Python's graph says
    const first = D.nav[D.root].ArrowDown;
    key("ArrowDown");
    check("Down selects the first child", drawerTitle() === title(first) && $("#view .card.sel .ct").textContent === title(first), drawerTitle());
    key("ArrowRight");
    check("Right selects the next sibling", drawerTitle() === title(D.nav[first].ArrowRight), drawerTitle());
    key("ArrowLeft");
    check("Left selects the previous sibling", drawerTitle() === title(first));
    key("ArrowDown"); key("ArrowUp");
    check("Up selects the parent", drawerTitle() === title(first));
    key("ArrowUp");
    check("Up again reaches the root", drawerTitle() === title(D.root));
    key("ArrowUp");
    check("Up at the root stays", drawerTitle() === title(D.root));
    // --- Enter refocuses; routing; history
    key("ArrowDown"); key("Enter"); await sleep(50);
    check("Enter refocuses (hash and breadcrumb)", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    $$("#crumbs button").find((b) => b.textContent === title(D.root)).click(); await sleep(50);
    check("a breadcrumb click refocuses", hash() === "#/node/" + D.root && cur() === title(D.root), [hash(), cur()]);
    history.back(); await sleep(80);
    check("back returns to the previous focus", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    history.forward(); await sleep(80);
    check("forward goes on", hash() === "#/node/" + D.root, hash());
    // --- maximise, zoom, select a leaf, Esc
    key("m");
    check("m maximises", document.body.classList.contains("maximised") && $("#maxbtn").getAttribute("aria-pressed") === "true" && $(".zoombar") !== null);
    const bandsMax = $$("svg.icicle g.band").length;
    const zoomTarget = $$("svg.icicle g.band").map((g) => g.dataset.id).find((id) => id !== D.root && (D.children[id] || []).length > 0);
    click($("svg.icicle g.band[data-id='" + zoomTarget + "'] rect"));
    check("clicking a band with children zooms in and stays maximised", document.body.classList.contains("maximised") && $$("svg.icicle g.band").length < bandsMax && hash() === "#/node/" + D.root, [$$("svg.icicle g.band").length, bandsMax]);
    check("the zoom bar can go up and back to the whole tree", !$$(".zoombar button").find((b) => b.textContent.includes("Up")).disabled);
    $$(".zoombar button").find((b) => b.textContent.includes("Whole tree")).click();
    check("Whole tree zooms back out", $$("svg.icicle g.band").length === bandsMax);
    const aLeaf = $$("svg.icicle g.band").map((g) => g.dataset.id).find((id) => (D.children[id] || []).length === 0);
    click($("svg.icicle g.band[data-id='" + aLeaf + "'] rect")); await sleep(50);
    check("selecting a leaf focuses it and restores the layout", !document.body.classList.contains("maximised") && hash() === "#/node/" + aLeaf && cur() === title(aLeaf), [hash(), cur()]);
    key("m"); key("Escape");
    check("Esc leaves the maximised mode", !document.body.classList.contains("maximised"));
    // --- leaf page: criterion, chain, dependents, markdown escaping
    window.BODIES[D.big_chain] = "Notes <img src=x onerror=window.pwned=1> **bold** [bad](javascript:window.pwned=1)";
    location.hash = "#/node/" + D.big_chain; await sleep(100);
    check("a leaf opens the single-node page", $(".page h1") && $(".page h1").textContent === title(D.big_chain) && $("#drawer").hidden === true);
    check("the page shows the criterion and its evaluation", $(".page").textContent.includes("Done when") && $(".page").textContent.includes("Evaluation"));
    const chainCards = $$(".chain .card").length;
    check("the chain of uncleared blockers is drawn", chainCards >= 2 && chainCards <= 60 && $(".chain svg path.edge") !== null, chainCards);
    check("the chain ends in the node itself", $$(".chain .card").some((c) => c.dataset.id === D.big_chain && c.classList.contains("sel")));
    check("markdown is rendered with raw html escaped", $(".md") && $(".md").innerHTML.includes("&lt;img") && $(".md strong") && !$(".md img") && !$(".md a[href^='javascript']") && window.pwned === undefined, $(".md") && $(".md").innerHTML);
    check("the page has Open in editor and Copy id", $$(".page .btns button").map((b) => b.textContent).join("|") === "Open in editor|Copy id");
    // --- the editor call: POST, token header, id from the selection
    window.calls.length = 0;
    key("e"); await sleep(30);
    const post = window.calls.find((c) => c[1] === "POST");
    check("e posts to /api/open/<id> with the token", post && post[0] === "/api/open/" + encodeURIComponent(D.big_chain) && post[2]["X-Roadmap-Token"] === "tok", post);
    check("the result is announced", $("#toast").textContent.includes("Opened"), $("#toast").textContent);
    window.OPEN_FAILS = true;
    key("e"); await sleep(30);
    check("a failed open shows the underlying error as a visible notice", $("#toast").textContent.includes("WinError 2") && $("#toast").classList.contains("show") && $("#toast").classList.contains("err"), $("#toast").textContent);
    $("#toast").click();
    check("a click dismisses the error notice", !$("#toast").classList.contains("show"));
    window.OPEN_FAILS = false;
    // --- search
    location.hash = "#/node/" + D.root; await sleep(60);
    key("/");
    check("/ focuses the search box", document.activeElement === $("#search"), [document.activeElement && document.activeElement.tagName, document.activeElement && document.activeElement.id, document.hasFocus()]);
    $("#search").value = "gear"; $("#search").dispatchEvent(new Event("input", { bubbles: true }));
    const cands = $$("#cands li button");
    check("typing lists candidates", cands.length >= 1 && cands.length <= 10, cands.length);
    key("ArrowDown", $("#search")); key("Enter", $("#search")); await sleep(60);
    check("Enter on a candidate focuses it", D.state.nodes[hash().slice(7)] !== undefined && hash() !== "#/node/" + D.root && $("#search").value === "", hash());
    // --- depth controls and superseded toggle
    location.hash = "#/node/" + D.root; await sleep(60);
    const n3 = $$("#view .card").length;
    tool("Show one level more").click();
    const n4 = $$("#view .card").length;
    tool("Show one level fewer").click();
    tool("Show one level fewer").click();
    const n2 = $$("#view .card").length;
    check("the depth controls change how many cards are drawn", n2 < n3 && n4 >= n3, [n2, n3, n4]);
    tool("Show one level more").click();
    const sup = Object.values(D.state.nodes).filter((n) => n.status === "superseded").length;
    const before = $$("svg.icicle g.band").length;
    const cb = $("#supcb"); cb.checked = true; cb.dispatchEvent(new Event("change", { bubbles: true }));
    check("superseded nodes are hidden by default and shown on request", sup > 0 && $$("svg.icicle g.band").length === before + sup, [before, sup, $$("svg.icicle g.band").length]);
    $("#supcb").checked = false; $("#supcb").dispatchEvent(new Event("change", { bubbles: true }));
    // --- a live change keeps focus, selection and layout
    location.hash = "#/node/" + first; await sleep(60);
    key("ArrowDown");
    const sel = D.nav[first].ArrowDown;
    key("m");
    window.STATE_NOW.nodes[first].title = "Renamed while open";
    window.es.listeners.changed(); await sleep(300);
    check("a changed event refetches and re-renders", $("#crumbs") && document.title.startsWith("Renamed while open"), document.title);
    check("focus and the maximised state survive it", hash() === "#/node/" + first && document.body.classList.contains("maximised") && $(".zoombar") !== null, hash());
    key("Escape");
    check("the selection survives it", cur() === "Renamed while open" && drawerTitle() === title(sel), [cur(), drawerTitle()]);
    // --- the selected node disappears: fall back, do not crash
    delete window.STATE_NOW.nodes[sel];
    window.STATE_NOW.nodes[first].children = window.STATE_NOW.nodes[first].children.filter((c) => c !== sel);
    window.es.listeners.changed(); await sleep(300);
    check("a vanished selection falls back without error", window.errors.length === 0 && $("#view").children.length > 0 && drawerTitle() === "Renamed while open", [window.errors, drawerTitle()]);
    // --- a broken graph shows what parsed, with the problem
    window.STATE_NOW.errors = [{ code: "parent-cycle", message: "rm.x -> rm.y -> rm.x", ids: [], paths: [] }];
    window.es.listeners.changed(); await sleep(300);
    check("errors raise a banner and the badge", $(".banner") && $(".banner").textContent.includes("error") && $("#badge").className === "badge");
    $("#tab-problems").click();
    check("the Problems tab lists the error", $("#side-body").textContent.includes("parent-cycle"));
    // --- an unknown route
    location.hash = "#/node/rm.does-not-exist"; await sleep(80);
    check("an unknown id shows a notice and falls back to the root", $$(".banner").some((b) => b.textContent.includes("rm.does-not-exist")) && cur() === title(D.root), cur());
    check("no script errors at the end", window.errors.length === 0, window.errors);
  } catch (e) { fails.push("exception: " + e + " " + (e.stack || "")); }
  document.getElementById("out").textContent = JSON.stringify({ fails, checks });
})();
</script>
<pre id="out">pending</pre>
"""


def build_ui_page(exp, workdir):
    html = INDEX.replace("__ROADMAP_TOKEN__", "tok")
    for name in ("d3.min.js", "marked.min.js", "app.js"):
        html = html.replace(f'src="{name}"', f'src="{(VIEWER / name).resolve().as_uri()}"')
    stubs = UI_STUBS.replace("__DATA__", json.dumps(exp, sort_keys=True).replace("</", "<\\/"))
    html = html.replace('<script src="file:', stubs + '<script src="file:', 1)  # the stubs run before app.js; d3 and marked do not read them
    page = workdir / "ui.html"
    page.write_text(html.replace("</body>", UI_TEST + "</body>"), encoding="utf-8")
    return page


def read_out(dom):
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    assert m, "the page produced no output; DOM began: " + dom[:300]
    text = m.group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    assert text != "pending", "the page script did not run to the end"
    return json.loads(text)


@pytest.fixture(scope="module")
def ui_result(tmp_path_factory):
    if BROWSER is None:
        pytest.skip("no Chromium-family browser (msedge, chrome, chromium) found; the viewer interface tests need one")
    work = tmp_path_factory.mktemp("viewer_ui")
    root = work / "fx"
    fixture.generate(120, root, seed=4)
    page = build_ui_page(expected_for(root), work)
    return read_out(dump_dom(page.resolve().as_uri(), work))


def test_the_interface_behaves_in_a_real_browser_engine(ui_result):
    assert ui_result["fails"] == [], ui_result["fails"][:8]
    assert ui_result["checks"] >= 45  # a count, so a script that stops early cannot pass
