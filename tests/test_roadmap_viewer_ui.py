"""
Roadmap T8 (brief 1 T8, brief 2 T7 and T8): the viewer's interface, in a headless Chromium-family browser. The real index.html and
app.js are loaded from files, with fetch and EventSource stubbed by a script placed before app.js, and a scripted session then drives the
page (keyboard, clicks, wheel and pointer events, history, search, pins, live updates) and checks the DOM. The expected answers come from
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
  const cur = () => ($("#crumbs .cur") || { getAttribute: () => undefined }).getAttribute("title"); // the crumb shows 28 characters; the full title is the hover text
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
    check("the first fit and automatic depth were computed against the view's final width (the drawer already showing)", Number($("#view").dataset.fitwidth) === $("#view").clientWidth && $("#view").clientWidth > 0, [$("#view").dataset.fitwidth, $("#view").clientWidth]);
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

    // =================================================================== focus mode
    const view = $("#view");
    check("focus mode has no scrollbar: the view pans and zooms", view.classList.contains("tree-mode") && getComputedStyle(view).overflow === "hidden" && stage() !== null && tf() !== null);
    check("the default depth fits the view's width, and says it is automatic", depthShown() === L.autoDepth(IDX, D.root, view.clientWidth) && view.dataset.auto === "1" && $("#depthval").textContent === String(depthShown()), [depthShown(), view.clientWidth]);
    const shown0 = D.shown.find((c) => c.focus === D.root && c.depth === depthShown());
    check("the root's cards are exactly the expected nodes", shown0 && JSON.stringify($$("#view .card:not(.more-card)").map((c) => c.dataset.id).sort()) === JSON.stringify(shown0.ids), [depthShown(), $$("#view .card").length]);
    check("every card carries a status label", $$("#view .card:not(.more-card)").every((c) => /(done|in progress|active|ready|expandable|blocked|not started|unknown|superseded)/.test(c.textContent)));
    check("interior cards have a progress bar for done/total, leaves do not", $$("#view .card:not(.more-card)").every((c) => { const id = c.dataset.id, bar = c.querySelector(".bar i"); if (!isInterior(id)) return bar === null; const [d, t] = prog(id); return bar && Math.abs(parseFloat(bar.style.width) - 100 * d / t) < 0.2; }));
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
    // Enter refocuses; routing; history
    key("ArrowDown"); key("Enter"); await sleep(60);
    check("Enter refocuses (hash and breadcrumb)", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    click($$("#crumbs button").find((b) => b.getAttribute("title") === title(D.root))); await sleep(60);
    check("a breadcrumb click refocuses", hash() === "#/node/" + D.root && cur() === title(D.root), [hash(), cur()]);
    history.back(); await sleep(80);
    check("back returns to the previous focus", hash() === "#/node/" + first && cur() === title(first), [hash(), cur()]);
    history.forward(); await sleep(80);
    check("forward goes on", hash() === "#/node/" + D.root, hash());
    // compact layout and child order
    await goTo(D.mixed);
    const mixedKids = D.ordered[D.mixed];
    const colIds = mixedKids.filter((k) => !isInterior(k)), rowKids = mixedKids.filter(isInterior);
    const card = (id) => $("#view .card[data-id='" + id + "']");
    check("childless children stack in one column, in child order", colIds.length >= 2 && colIds.every((k) => card(k) && xy(card(k)).x === xy(card(colIds[0])).x) && colIds.every((k, i) => i === 0 || xy(card(k)).y > xy(card(colIds[i - 1])).y), colIds.length);
    check("interior children spread along one row, in child order, right of the column", rowKids.length >= 1 && rowKids.every((k) => xy(card(k)).y === xy(card(rowKids[0])).y && xy(card(k)).x > xy(card(colIds[0])).x) && rowKids.every((k, i) => i === 0 || xy(card(k)).x > xy(card(rowKids[i - 1])).x));
    check("the focus card sits above its children", xy(card(D.mixed)).y < xy(card(colIds[0])).y && xy(card(D.mixed)).y < xy(card(rowKids[0])).y);
    // overflow
    await goTo(D.wide);
    const wideKids = D.ordered[D.wide];
    let more = $("#view .more-card");
    check("a node with more than 8 children shows the first 8 and a +k more card", more && more.textContent.includes("+" + (wideKids.length - 8) + " more") && wideKids.slice(0, 8).every((k) => card(k)) && wideKids.slice(8).every((k) => !card(k)), more && more.textContent);
    click(more); await sleep(30);
    check("the +k more card expands in place", wideKids.every((k) => card(k)) && ($("#view .more-card") === null || /fewer/.test($("#view .more-card").textContent)));
    await goTo(D.root); await goTo(D.wide);
    check("a new focus collapses it again", !card(wideKids[8]) && $("#view .more-card") !== null);
    // automatic depth, recomputed on resize; the +/- controls override it until the focus changes
    const candidates = Object.keys(D.children).filter(isInterior);
    const wideW = view.clientWidth;
    $("#app").style.setProperty("--side-w", "700px");
    const narrowW = view.clientWidth;
    $("#app").style.setProperty("--side-w", "320px");
    const probe = candidates.find((f) => L.autoDepth(IDX, f, wideW) > L.autoDepth(IDX, f, narrowW));
    check("the fixture has a node whose automatic depth depends on the width", probe !== undefined, [wideW, narrowW]);
    await goTo(probe);
    const d0 = depthShown();
    check("automatic depth at the normal width", d0 === L.autoDepth(IDX, probe, view.clientWidth) && view.dataset.auto === "1", [d0, view.clientWidth]);
    $("#app").style.setProperty("--side-w", "700px"); window.dispatchEvent(new Event("resize")); await sleep(120);
    check("narrowing the view lowers the depth by itself", depthShown() === L.autoDepth(IDX, probe, view.clientWidth) && depthShown() < d0, [depthShown(), d0]);
    $("#app").style.setProperty("--side-w", "320px"); window.dispatchEvent(new Event("resize")); await sleep(120);
    check("widening it raises the depth again", depthShown() === d0, [depthShown(), d0]);
    tool("Show one level fewer").click();
    check("the depth controls override the automatic depth", depthShown() === Math.max(1, d0 - 1) && view.dataset.auto === "0", [depthShown(), d0]);
    $("#app").style.setProperty("--side-w", "700px"); window.dispatchEvent(new Event("resize")); await sleep(120);
    check("an override survives a resize", depthShown() === Math.max(1, d0 - 1), depthShown());
    $("#app").style.setProperty("--side-w", "320px"); window.dispatchEvent(new Event("resize")); await sleep(120);
    tool("Show one level more").click(); tool("Show one level more").click();
    const n3 = $$("#view .card").length;
    check("more levels draw more cards", depthShown() === Math.min(12, d0 + 1) && n3 >= 1, depthShown());
    await goTo(D.root); await goTo(probe);
    check("a new focus returns to the automatic depth", depthShown() === d0 && view.dataset.auto === "1", [depthShown(), d0]);
    // pan, zoom, fit
    await goTo(D.root);
    const t0 = tf(), r0 = view.getBoundingClientRect(), cx = r0.left + 300, cy = r0.top + 200;
    wheel(view, -300, cx, cy);
    const t1 = tf();
    check("the mouse wheel zooms in", t1[0] > t0[0], [t0, t1]);
    check("zooming keeps the point under the cursor in place", Math.abs((cx - r0.left - t1[1]) / t1[0] - (cx - r0.left - t0[1]) / t0[0]) < 0.5 && Math.abs((cy - r0.top - t1[2]) / t1[0] - (cy - r0.top - t0[2]) / t0[0]) < 0.5);
    wheel(view, 600, cx, cy);
    check("and out", tf()[0] < t1[0]);
    ptr(view, "pointerdown", cx, cy); ptr(view, "pointermove", cx + 60, cy + 30); ptr(view, "pointermove", cx + 90, cy + 40); ptr(view, "pointerup", cx + 90, cy + 40);
    const t2 = tf();
    check("dragging pans the stage by the drag distance", Math.abs(t2[1] - t0[1] - 90) < 1.5 && Math.abs(t2[2] - t0[2] - 40) < 1.5 || t2[0] !== t0[0], [t0, t2]);
    key("f");
    check("f fits the view again", JSON.stringify(tf().map((x) => Math.round(x))) === JSON.stringify(t0.map((x) => Math.round(x))), [tf(), t0]);
    wheel(view, -600, cx, cy);
    click($("#fitbtn"));
    check("the Fit button does the same", JSON.stringify(tf().map((x) => Math.round(x))) === JSON.stringify(t0.map((x) => Math.round(x))));
    key("f");
    const x0 = tf()[1];
    ptr(view, "pointerdown", cx, cy); ptr(view, "pointermove", cx + 80, cy); ptr(view, "pointerup", cx + 80, cy);
    check("a drag moves the stage by exactly the drag distance", Math.abs(tf()[1] - x0 - 80) < 1.5, [tf()[1], x0]);
    const selBefore = drawerTitle(), cEl = card(first), cc = centre(cEl);
    ptr(cEl, "pointerdown", cc[0], cc[1]); ptr(cEl, "pointermove", cc[0] + 30, cc[1]); ptr(cEl, "pointerup", cc[0] + 30, cc[1]); click(cEl);
    check("a drag that starts on a card pans and does not select it", drawerTitle() === selBefore && tf()[1] !== x0 + 80, [drawerTitle(), selBefore]);
    key("f");
    // breadcrumb
    await goTo(D.deep);
    const crumbBtns = () => $$("#crumbs > button");
    const full = chain(D.deep);
    check("a deep breadcrumb shows root, …, grandparent, parent, node", $(".crumb-gap") !== null && crumbBtns().filter((b) => !b.classList.contains("crumb-gap")).map((b) => b.getAttribute("title")).join("|") === [full[0], full[full.length - 3], full[full.length - 2]].map(title).join("|") && $("#crumbs .cur").textContent.length <= 28, crumbBtns().map((b) => b.textContent));
    check("titles in the breadcrumb are cut at about 28 characters, the full title on hover", crumbBtns().every((b) => b.textContent.length <= 28) && crumbBtns().filter((b) => !b.classList.contains("crumb-gap")).every((b) => b.getAttribute("title").startsWith(b.textContent.replace(/…$/, ""))));
    click($(".crumb-gap"));
    check("clicking … expands the full path", $(".crumb-gap") === null && crumbBtns().length === full.length - 1, crumbBtns().length);
    await goTo(D.root);

    // =================================================================== pins
    const target = first;
    const starOf = (id) => $("#view .card[data-id='" + id + "'] .star");
    window.calls.length = 0;
    click(starOf(target)); await sleep(60);
    const pinCall = window.calls.find((c) => c[0] === "/api/pin/" + encodeURIComponent(target));
    check("the star on a card pins the node: POST with the token", pinCall && pinCall[1] === "POST" && pinCall[2]["X-Roadmap-Token"] === "tok", pinCall);
    check("the card shows it, and the working panel lists it", starOf(target).classList.contains("on") && starOf(target).getAttribute("aria-pressed") === "true" && $$("#wg-pinned .wrow").map((r) => r.dataset.id).join() === target);
    check("the outline row carries a star", rowOf(target) && rowOf(target).querySelector(".star-mark") !== null);
    click($("#view .card[data-id='" + target + "']"));
    check("the drawer has a star toggle, on for a pinned node", $("#drawer .star").classList.contains("on"));
    window.calls.length = 0;
    key("p"); await sleep(60);
    check("p unpins the selection", window.calls.some((c) => c[0] === "/api/unpin/" + encodeURIComponent(target)) && !starOf(target).classList.contains("on") && $$("#wg-pinned .wrow").length === 0 && window.PINS.length === 0);
    key("p"); await sleep(60);
    check("and pins it again", starOf(target).classList.contains("on") && window.PINS.join() === target);
    const second = D.nav[target].ArrowRight !== target ? D.nav[target].ArrowRight : D.nav[target].ArrowLeft;
    click(starOf(second)); await sleep(60);
    check("pins are listed in id order", $$("#wg-pinned .wrow").map((r) => r.dataset.id).join() === [target, second].sort().join(), $$("#wg-pinned .wrow").map((r) => r.dataset.id));
    window.PIN_FAILS = true;
    click(starOf(second)); await sleep(60);
    check("a failed pin call shows its error as a visible notice and changes nothing", $("#toast").classList.contains("show") && $("#toast").classList.contains("err") && $("#toast").textContent.includes("disk full") && starOf(second).classList.contains("on"), $("#toast").textContent);
    window.PIN_FAILS = false;
    window.PINS.push("rm.gone"); window.es.listeners.changed(); await sleep(300);
    const dang = $("#wg-pinned .wrow[data-id='rm.gone']");
    check("a pin whose node is gone is listed as dangling, not dropped", dang && /no longer/.test(dang.textContent) && dang.querySelector("button.unpin") !== null, dang && dang.textContent);
    window.calls.length = 0;
    dang.querySelector("button.unpin").click(); await sleep(60);
    check("and can be removed", window.calls.some((c) => c[0] === "/api/unpin/rm.gone") && !$("#wg-pinned .wrow[data-id='rm.gone']"));
    click(starOf(second)); await sleep(60); // unpin the second; the first stays pinned for the map checks

    // =================================================================== the single-node page
    window.BODIES[D.big_chain] = "Notes <img src=x onerror=window.pwned=1> **bold** [bad](javascript:window.pwned=1)";
    await goTo(D.big_chain);
    check("a leaf opens the single-node page, not a scrolling tree", $(".page h1") && $(".page h1").textContent === title(D.big_chain) && $("#drawer").hidden === true && view.classList.contains("page-mode") && getComputedStyle(view).overflowY === "auto");
    check("the page shows the criterion and its evaluation", $(".page").textContent.includes("Done when") && $(".page").textContent.includes("Evaluation"));
    const chainCards = $$(".chain .card").length;
    check("the chain of uncleared blockers is drawn", chainCards >= 2 && chainCards <= 60 && $(".chain svg path.edge") !== null, chainCards);
    check("the chain ends in the node itself", $$(".chain .card").some((c) => c.dataset.id === D.big_chain && c.classList.contains("sel")));
    check("markdown is rendered with raw html escaped", $(".md") && $(".md").innerHTML.includes("&lt;img") && $(".md strong") && !$(".md img") && !$(".md a[href^='javascript']") && window.pwned === undefined, $(".md") && $(".md").innerHTML);
    check("the page has Open in editor, Copy id and a pin star", $$(".page .btns button").map((b) => b.textContent.replace(/^[★☆] /, "")).join("|") === "Open in editor|Copy id|Pin" && $(".page .btns .star") !== null);
    window.calls.length = 0;
    click($(".page .btns .star")); await sleep(60);
    check("the page's star pins this node", window.calls.some((c) => c[0] === "/api/pin/" + encodeURIComponent(D.big_chain)) && $(".page .btns .star").classList.contains("on"));
    click($(".page .btns .star")); await sleep(60);
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
    key("m", $("#search")); key("p", $("#search")); key("f", $("#search"));
    check("keys are ignored while typing in an input", window.PINS.join() === target && $("#fitbtn") !== null);
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
    assert ui_result["checks"] >= 100  # a count, so a script that stops early cannot pass
