"""
Roadmap T8 (brief 1 T8, brief 2 T7): the viewer's interface, in a headless Chromium-family browser. The real index.html and
app.js are loaded from files, with fetch and EventSource stubbed by a script placed before app.js, and a scripted session then drives the
page (keyboard, clicks, history, search, the sidebar, live updates) and checks the DOM. The expected answers come from
Python's reading of the library, never from app.js. Skipped, with the reason, when no browser is installed. No server and no socket is
involved.

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
window.PINS = [];
window.fetch = (url, opts) => {
  url = String(url);
  const method = (opts && opts.method) || "GET";
  window.calls.push([url, method, opts && opts.headers]);
  const reply = (status, obj) => Promise.resolve({ ok: status < 400, status, headers: { get: () => "1" }, json: () => Promise.resolve(obj) });
  const ok = (obj) => reply(200, obj);
  if (url.startsWith("/api/state")) return ok(JSON.parse(JSON.stringify(window.STATE_NOW)));
  if (url.startsWith("/api/node/")) { const id = decodeURIComponent(url.slice(10)); return ok({ id, title: "", path: "", body: window.BODIES[id] || "", references: { files: [], commits: [] } }); }
  if (url.startsWith("/api/open/") && window.OPEN_FAILS) return reply(500, { error: "WinError 2: cannot find the file" });
  if (url.startsWith("/api/open/")) return ok({ opened: "roadmap/nodes/stub.md" });
  if (url === "/api/pins") return ok({ pins: window.PINS.slice().sort() });
  if (url.startsWith("/api/pin/") || url.startsWith("/api/unpin/")) {
    if (window.PIN_FAILS) return reply(500, { error: "disk full" });
    const id = decodeURIComponent(url.slice(url.indexOf("pin/") + 4));
    const have = new Set(window.PINS);
    if (url.startsWith("/api/pin/")) have.add(id); else have.delete(id);
    window.PINS = Array.from(have).sort();
    return ok({ pins: window.PINS.slice() });
  }
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
  const ptr = (el, type, x, y) => el.dispatchEvent(new PointerEvent(type, { clientX: x, clientY: y, pointerId: 1, bubbles: true, button: 0, buttons: type === "pointerup" ? 0 : 1 }));
  const wheel = (el, dy, x, y) => el.dispatchEvent(new WheelEvent("wheel", { deltaY: dy, clientX: x, clientY: y, bubbles: true, cancelable: true }));
  const tool = (label) => $$("#crumbs .tools button").find((b) => b.getAttribute("aria-label") === label);
  const goTo = async (id) => { location.hash = "#/node/" + id; await sleep(80); };
  const kids = D.children[D.root];
  const isInterior = (id) => D.children[id].length > 0;
  const prog = (id) => { let d = 0, t = 0; (function f(x) { if (!D.children[x].length) { t++; if (D.state.nodes[x].status === "done") d++; return; } D.children[x].forEach(f); })(id); return [d, t]; };
  const chain = (id) => { const out = []; for (let c = id; c; c = D.state.nodes[c].parent) out.push(c); return out.reverse(); };
  const L = window.RoadmapLogic, IDX = L.buildIndex(D.state, false);
  const xy = (el) => ({ x: parseFloat(el.style.left), y: parseFloat(el.style.top) });
  const stage = () => $("#view .stage");
  const tf = () => { const s = stage(); return s ? [parseFloat(s.dataset.k), parseFloat(s.dataset.tx), parseFloat(s.dataset.ty)] : null; };
  const depthShown = () => Number($("#view").dataset.depth);
  const rowIds = () => $$(".orow").map((r) => r.dataset.id);
  const centre = (el) => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };
  try {
    await sleep(300);
    // =================================================================== boot
    check("no script errors at boot", window.errors.length === 0, window.errors);
    check("boots on the root", cur() === title(D.root) && $("#drawer").hidden === false && drawerTitle() === title(D.root), [cur(), drawerTitle()]);
    check("problems badge counts errors and warnings", $("#badge").textContent === String(D.state.errors.length + D.state.warnings.length), $("#badge").textContent);
    check("status bar shows the node count and the live indicator", $("#statusbar").textContent.includes(D.state.node_count + " nodes") && $("#statusbar").textContent.includes("live"));
    check("the pins were requested at boot", window.calls.some((c) => c[0] === "/api/pins" && c[1] === "GET"));
        check("the icicle and the sidebar maximise control are gone", $("svg.icicle") === null && $("#maxbtn") === null && !$(".zoombar"));
    check("the tabs are Outline, Frontier, Problems, in that order", $$(".tabs [role=tab]").map((b) => b.dataset.tab).join("|") === "outline|frontier|problems" && $("#tab-outline").textContent === "Outline");

    // =================================================================== working panel
    check("a working panel sits above the tabs", $("#working") && $("#working").compareDocumentPosition($(".tabs")) & Node.DOCUMENT_POSITION_FOLLOWING);
    const activeRows = () => $$("#wg-active .wrow").map((r) => r.dataset.id);
    check("Active lists every leaf marked active, as the repo says", JSON.stringify(activeRows()) === JSON.stringify(D.active_leaves), activeRows());
    check("a working row shows status glyph, title and id", $$("#wg-active .wrow").every((r) => r.querySelector(".sw") && r.querySelector(".wt").textContent === title(r.dataset.id) && r.querySelector(".wid").textContent === r.dataset.id));
    check("Pinned starts empty and says so", $$("#wg-pinned .wrow").length === 0 && $("#wg-pinned").textContent.includes("Pinned"));
    $("#working-toggle").click();
    check("the working panel collapses and the tabs stay", $("#working").classList.contains("collapsed") && $("#working-toggle").getAttribute("aria-expanded") === "false" && $$(".tabs [role=tab]").length === 3);
    $("#working-toggle").click();
    check("and expands again", !$("#working").classList.contains("collapsed"));
    const firstActive = D.active_leaves[0];
    click($("#wg-active .wrow[data-id='" + firstActive + "']"));
    await sleep(80);
    check("clicking a working row focuses the node", hash() === "#/node/" + firstActive && cur() === title(firstActive), [hash(), cur()]);
    await goTo(D.root);

    // =================================================================== outline
    check("the outline starts collapsed except the path to the focus (the root: its children show)", JSON.stringify(rowIds()) === JSON.stringify([D.root, ...kids]), rowIds().length);
    const rowOf = (id) => $(".orow[data-id='" + id + "']");
    const pad = (id) => parseFloat(rowOf(id).style.paddingLeft);
    check("each level indents about 12 px", Math.abs(pad(kids[0]) - pad(D.root) - 12) < 1.5, [pad(D.root), pad(kids[0])]);
    check("interior rows show done/total, leaves do not", rowOf(D.root).querySelector(".frac").textContent === prog(D.root).join("/") && kids.every((k) => (rowOf(k).querySelector(".frac") !== null) === isInterior(k) && (!isInterior(k) || rowOf(k).querySelector(".frac").textContent === prog(k).join("/"))));
    check("rows carry a status glyph and the full title on hover", $$(".orow").every((r) => r.querySelector(".sw") && r.querySelector(".ot").getAttribute("title") === title(r.dataset.id)));
    const kidInterior = kids.find(isInterior);
    rowOf(kidInterior).querySelector(".otoggle").click();
    check("a toggle expands a row", JSON.stringify(rowIds()) === JSON.stringify([D.root, ...kids.flatMap((k) => k === kidInterior ? [k, ...D.children[k]] : [k])]), rowIds().length);
    rowOf(kidInterior).querySelector(".otoggle").click();
    check("and collapses it again", rowIds().length === 1 + kids.length);
    await goTo(D.deep);
    check("a deep focus expands the path to it", JSON.stringify(rowIds()) === JSON.stringify(D.outline_rows_path.map((r) => r[0])), [rowIds().length, D.outline_rows_path.length]);
    check("the path stays highlighted and the focus row is marked", $$(".orow.onpath").length === chain(D.deep).length && $(".orow.focus").dataset.id === D.deep, $$(".orow.onpath").length);
    const sb = $("#side-body").getBoundingClientRect(), fr = $(".orow.focus").getBoundingClientRect();
    check("the focus row is scrolled into view", fr.top >= sb.top - 1 && fr.bottom <= sb.bottom + 1, [fr.top, fr.bottom, sb.top, sb.bottom]);
    await goTo(D.root);
    // search filters the outline to the matches and their ancestors
    $("#search").value = D.outline_filters[0].text; $("#search").dispatchEvent(new Event("input", { bubbles: true }));
    check("search filters the outline to matches plus ancestors", JSON.stringify(rowIds()) === JSON.stringify(D.outline_rows_filter.map((r) => r[0])), [rowIds().length, D.outline_rows_filter.length]);
    check("and still lists candidates like the CLI's query", $$("#cands li").length >= 1);
    key("Escape", $("#search"));
    check("Esc in the search box clears the filter", $("#search").value === "" && rowIds().length === 1 + kids.length);
    // status chips
    check("there are chips for ready, active, blocked, expandable and done", $$(".chips-status button").map((b) => b.dataset.status).join("|") === "ready|active|blocked|expandable|done");
    const chip = (s) => $(".chips-status button[data-status='" + s + "']");
    chip("ready").click();
    const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
    check("a status chip narrows the outline to those statuses and their ancestors", chip("ready").getAttribute("aria-pressed") === "true" && sameSet(rowIds(), D.outline_filters[1].visible), [rowIds().length, D.outline_filters[1].visible.length]);
    chip("ready").click();
    chip("done").click(); chip("blocked").click();
    check("chips combine as 'any of'", sameSet(rowIds(), D.outline_filters[2].visible), [rowIds().length, D.outline_filters[2].visible.length]);
    chip("done").click(); chip("blocked").click();
    $("#search").value = D.outline_filters[3].text; $("#search").dispatchEvent(new Event("input", { bubbles: true }));
    chip("ready").click();
    check("search and chips narrow together", sameSet(rowIds(), D.outline_filters[3].visible), [rowIds().length, D.outline_filters[3].visible.length]);
    chip("ready").click(); key("Escape", $("#search"));
    check("clearing both restores the outline", rowIds().length === 1 + kids.length && $$(".chips-status button[aria-pressed=true]").length === 0);

    // =================================================================== the main view (unchanged by T7)
    check("cards for the root and its children", $$("#view .card").length >= 1 + kids.length);
    check("every card carries a status label", $$("#view .card").every((c) => /(done|in progress|active|ready|expandable|blocked|not started|unknown|superseded)/.test(c.textContent)));
    check("legend names every status", ["done", "in progress", "active", "ready", "expandable", "blocked", "not started", "unknown"].every((s) => $(".legend").textContent.includes(s)));
    // keyboard: down, right, left, up, as Python's graph says
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
    key("ArrowDown"); key("Enter"); await sleep(50);
    check("Enter refocuses (hash and breadcrumb)", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    $$("#crumbs button").find((b) => b.textContent === title(D.root)).click(); await sleep(50);
    check("a breadcrumb click refocuses", hash() === "#/node/" + D.root && cur() === title(D.root), [hash(), cur()]);
    history.back(); await sleep(80);
    check("back returns to the previous focus", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    history.forward(); await sleep(80);
    check("forward goes on", hash() === "#/node/" + D.root, hash());
    // depth controls and the superseded toggle
    const n3 = $$("#view .card").length;
    tool("Show one level more").click();
    const n4 = $$("#view .card").length;
    tool("Show one level fewer").click();
    tool("Show one level fewer").click();
    const n2 = $$("#view .card").length;
    check("the depth controls change how many cards are drawn", n2 < n3 && n4 >= n3, [n2, n3, n4]);
    tool("Show one level more").click();
    const sup = Object.values(D.state.nodes).filter((n) => n.status === "superseded").length;
    $("#search").value = "retired"; $("#search").dispatchEvent(new Event("input", { bubbles: true }));
    const supRows = () => rowIds().filter((id) => D.state.nodes[id].status === "superseded").length;
    const before = supRows();
    const cb = $("#supcb"); cb.checked = true; cb.dispatchEvent(new Event("change", { bubbles: true }));
    check("superseded nodes are hidden by default and shown on request", sup > 0 && before === 0 && supRows() === sup, [before, sup, supRows()]);
    $("#supcb").checked = false; $("#supcb").dispatchEvent(new Event("change", { bubbles: true }));
    key("Escape", $("#search"));

    // =================================================================== the single-node page
    window.BODIES[D.big_chain] = "Notes <img src=x onerror=window.pwned=1> **bold** [bad](javascript:window.pwned=1)";
    await goTo(D.big_chain);
    check("a leaf opens the single-node page", $(".page h1") && $(".page h1").textContent === title(D.big_chain) && $("#drawer").hidden === true);
    check("the page shows the criterion and its evaluation", $(".page").textContent.includes("Done when") && $(".page").textContent.includes("Evaluation"));
    const chainCards = $$(".chain .card").length;
    check("the chain of uncleared blockers is drawn", chainCards >= 2 && chainCards <= 60 && $(".chain svg path.edge") !== null, chainCards);
    check("the chain ends in the node itself", $$(".chain .card").some((c) => c.dataset.id === D.big_chain && c.classList.contains("sel")));
    check("markdown is rendered with raw html escaped", $(".md") && $(".md").innerHTML.includes("&lt;img") && $(".md strong") && !$(".md img") && !$(".md a[href^='javascript']") && window.pwned === undefined, $(".md") && $(".md").innerHTML);
    check("the page has Open in editor and Copy id", $$(".page .btns button").map((b) => b.textContent).join("|") === "Open in editor|Copy id");
    // the editor call: POST, token header, id from the selection
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

    // =================================================================== search and keys that must be ignored while typing
    await goTo(D.root);
    key("/");
    check("/ focuses the search box", document.activeElement === $("#search"));
    window.calls.length = 0; key("e", $("#search"));
    check("keys are ignored while typing in an input", !window.calls.some((c) => c[1] === "POST"));
    $("#search").value = "gear"; $("#search").dispatchEvent(new Event("input", { bubbles: true }));
    const cands = $$("#cands li button");
    check("typing lists candidates", cands.length >= 1 && cands.length <= 10, cands.length);
    key("ArrowDown", $("#search")); key("Enter", $("#search")); await sleep(60);
    check("Enter on a candidate focuses it", hash().startsWith("#/node/") && $("#search").value === "" && hash() !== "#/node/" + D.root, hash());
    await goTo(D.root);
    $("#search").value = "gear"; $("#search").dispatchEvent(new Event("input", { bubbles: true })); $("#search").blur(); await sleep(200);
    key("Escape");
    check("Esc outside the box clears a standing search", $("#search").value === "");

    // =================================================================== live updates, errors
    location.hash = "#/node/" + first; await sleep(60);
    key("ArrowDown");
    const sel = D.nav[first].ArrowDown;
    window.STATE_NOW.nodes[first].title = "Renamed while open";
    window.es.listeners.changed(); await sleep(300);
    check("a changed event refetches and re-renders", $("#crumbs") && document.title.startsWith("Renamed while open"), document.title);
    check("focus survives it", hash() === "#/node/" + first, hash());
    check("the selection survives it", cur() === "Renamed while open" && drawerTitle() === title(sel), [cur(), drawerTitle()]);
    // the selected node disappears: fall back, do not crash
    delete window.STATE_NOW.nodes[sel];
    window.STATE_NOW.nodes[first].children = window.STATE_NOW.nodes[first].children.filter((c) => c !== sel);
    window.es.listeners.changed(); await sleep(300);
    check("a vanished selection falls back without error", window.errors.length === 0 && $("#view").children.length > 0 && drawerTitle() === "Renamed while open", [window.errors, drawerTitle()]);
    // a broken graph shows what parsed, with the problem
    window.STATE_NOW.errors = [{ code: "parent-cycle", message: "rm.x -> rm.y -> rm.x", ids: [], paths: [] }];
    window.es.listeners.changed(); await sleep(300);
    check("errors raise a banner and the badge", $(".banner") && $(".banner").textContent.includes("error") && $("#badge").className === "badge");
    $("#tab-problems").click();
    check("the Problems tab lists the error", $("#side-body").textContent.includes("parent-cycle"));
    $("#tab-frontier").click();
    check("the Frontier tab lists the frontier", $("#side-body").textContent.includes("Frontier:"));
    // an unknown route
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
    assert ui_result["fails"] == [], ui_result["fails"][:12]
    assert ui_result["checks"] >= 65  # a count, so a script that stops early cannot pass
