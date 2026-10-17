/*
 * Roadmap viewer (docs/briefs/architecture/roadmap-brief1.md T8, roadmap-brief2.md T7). One page, no build step, no framework: d3 v7 for the layouts and marked
 * for node bodies, both vendored beside this file. It reads /api/state, /api/node/<id>, /api/pins and /api/events; its write-shaped calls are
 * POST /api/open/<id> (asks the local editor to open a node file) and POST /api/unpin/<id> (the personal pins file).
 *
 * Part 1 is pure logic (index, outline, active leaves, keyboard navigation, query resolution, blocker chain, Markdown): it touches no DOM and is
 * exposed as window.RoadmapLogic so that tests/test_roadmap_viewer.py can run it in a headless browser. Part 2 is the interface.
 * Setting window.ROADMAP_TEST before this file loads skips Part 2.
 */
"use strict";
(function () {
  const T0 = performance.now();

  /* ------------------------------------------------------------------ Part 1: logic */

  const MAX_CANDIDATES = 10;
  const VROOT = "*"; // stands for "all roots" when the graph does not have exactly one (a broken graph must still show)
  const STATUS = {
    done: { label: "done", glyph: "✓" }, in_progress: { label: "in progress", glyph: "◐" }, active: { label: "active", glyph: "▶" },
    ready: { label: "ready", glyph: "○" }, expandable: { label: "expandable", glyph: "+" }, blocked: { label: "blocked", glyph: "✕" },
    not_started: { label: "not started", glyph: "·" }, unknown: { label: "unknown", glyph: "?" }, superseded: { label: "superseded", glyph: "–" },
    stale: { label: "stale", glyph: "!" },
  };
  const STATUS_ORDER = ["done", "in_progress", "active", "ready", "expandable", "blocked", "not_started", "unknown", "superseded"];

  function statusInfo(s) { return STATUS[s] || STATUS.unknown; }
  function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  /** The nodes the viewer shows: superseded ones only on request. Children keep id order; the tree is reachable from the roots only. */
  function buildIndex(state, showSuperseded) {
    const raw = (state && state.nodes) || {};
    const ids = Object.keys(raw).sort();
    const live = (id) => showSuperseded || raw[id].status !== "superseded";
    const nodes = Object.assign({}, raw);
    const children = {}, parent = {};
    for (const id of ids) children[id] = [];
    for (const id of ids) {
      const p = raw[id].parent;
      if (live(id) && p && raw[p] && live(p)) { children[p].push(id); parent[id] = p; }
    }
    const roots = ids.filter((id) => live(id) && !parent[id]);
    let rootId = null;
    if (roots.length === 1) rootId = roots[0];
    else if (roots.length > 1) {
      rootId = VROOT;
      nodes[VROOT] = { title: "All roots (the graph has " + roots.length + " roots)", status: "unknown", kind: "interior", reason: "no single root", parent: null,
        children: roots, blocked_by: [], effective_blockers: [], uncleared_blockers: [], dependents: [], estimate_days: null, tags: [], done_when: null, evaluation: null };
      children[VROOT] = roots.slice();
    }
    const leafCount = {}, progress = {}, depthOf = {};
    if (rootId !== null) (function walk(id, d) {
      depthOf[id] = d;
      const kids = children[id] || [];
      if (!kids.length) { leafCount[id] = 1; progress[id] = { done: nodes[id].status === "done" ? 1 : 0, total: 1 }; return; }
      let n = 0, done = 0;
      for (const k of kids) { walk(k, d + 1); n += leafCount[k]; done += progress[k].done; }
      leafCount[id] = n; progress[id] = { done, total: n };
    })(rootId, 0);
    return { nodes, ids, children, parent, roots, rootId, leafCount, progress, depthOf };
  }

  function ancestors(index, id) {
    const out = [];
    for (let p = index.parent[id], guard = 0; p && guard < 1000; p = index.parent[p], guard++) out.push(p);
    return out; // nearest first
  }

  /** Keyboard selection: Up parent, Down first child, Left/Right previous/next sibling (stopping at the ends). */
  function navigate(index, id, key) {
    if (!index.nodes[id]) return id;
    const kids = index.children[id] || [];
    if (key === "ArrowUp") return index.parent[id] || id;
    if (key === "ArrowDown") return kids[0] || id;
    if (key !== "ArrowLeft" && key !== "ArrowRight") return id;
    const sib = index.parent[id] ? index.children[index.parent[id]] : index.roots;
    const i = sib.indexOf(id);
    if (i < 0) return id;
    return sib[key === "ArrowLeft" ? Math.max(0, i - 1) : Math.min(sib.length - 1, i + 1)];
  }

  /** Every leaf with `active: true`: what is being worked on, derived from the repo (the same set the memos and Code see). */
  function activeLeaves(index) {
    return Object.keys(index.depthOf).filter((id) => !(index.children[id] || []).length && index.nodes[id].kind === "leaf" && index.nodes[id].active === true).sort();
  }

  /** Outline filter: the ids to show (matches of the text and of any chosen status, plus their ancestors) sorted, or null when no filter is set. */
  function outlineVisible(index, text, statuses) {
    const t = String(text || "").trim().toLowerCase();
    const st = new Set(statuses || []);
    if (!t && !st.size) return null;
    const vis = new Set();
    for (const id of Object.keys(index.depthOf)) {
      const n = index.nodes[id];
      if (t && !(id.toLowerCase().includes(t) || String(n.title).toLowerCase().includes(t))) continue;
      if (st.size && !st.has(n.status)) continue;
      for (let c = id; c && !vis.has(c); c = index.parent[c]) vis.add(c);
    }
    if (vis.size && index.rootId === VROOT) vis.add(VROOT);
    return Array.from(vis).sort();
  }

  /** The outline's rows in tree order (children by id). `o.open` is the set of expanded ids; under a filter everything that is shown is expanded. */
  function outlineRows(index, o) {
    const rows = [];
    if (index.rootId === null) return rows;
    const vis = outlineVisible(index, o.text, o.statuses), visSet = vis && new Set(vis);
    (function walk(id, depth) {
      if (visSet && !visSet.has(id)) return;
      const kids = index.children[id] || [];
      const shown = visSet ? kids.filter((k) => visSet.has(k)) : kids;
      const open = kids.length > 0 && (visSet ? shown.length > 0 : o.open.has(id));
      rows.push({ id, depth, hasKids: kids.length > 0, open });
      if (open) for (const k of shown) walk(k, depth + 1);
    })(index.rootId, 0);
    return rows;
  }

  /** The nested object d3.hierarchy reads: `depth` levels below the focus; `hidden` counts children cut off at the limit. */
  function subtree(index, id, depth, level) {
    const kids = index.children[id] || [];
    const open = level < depth;
    return { id, hidden: open ? 0 : kids.length, children: open ? kids.map((k) => subtree(index, k, depth, level + 1)) : [] };
  }

  function relativeDepth(index, id, focus) { // how far below `focus` the node sits, or -1
    let n = 0;
    for (let c = id; c; c = index.parent[c], n++) if (c === focus) return n;
    return -1;
  }

  /** difflib.SequenceMatcher.ratio() with a = candidate and b = query, no junk: what Python's get_close_matches ranks by. */
  function matchRatio(a, b) {
    const la = a.length, lb = b.length;
    if (la + lb === 0) return 1;
    const b2j = {};
    for (let j = 0; j < lb; j++) (b2j[b[j]] = b2j[b[j]] || []).push(j);
    function longest(alo, ahi, blo, bhi) {
      let besti = alo, bestj = blo, bestsize = 0, j2len = {};
      for (let i = alo; i < ahi; i++) {
        const next = {};
        for (const j of b2j[a[i]] || []) {
          if (j < blo) continue;
          if (j >= bhi) break;
          const k = (j2len[j - 1] || 0) + 1;
          next[j] = k;
          if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
        }
        j2len = next;
      }
      return [besti, bestj, bestsize];
    }
    let matches = 0;
    const queue = [[0, la, 0, lb]];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop();
      const [i, j, k] = longest(alo, ahi, blo, bhi);
      if (k) {
        matches += k;
        if (alo < i && blo < j) queue.push([alo, i, blo, j]);
        if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
      }
    }
    return (2.0 * matches) / (la + lb);
  }

  /** The CLI's query rules (tools/roadmap/query.py): the exact id; the id with `rm.` added; a unique case-insensitive substring of an id or title;
   * otherwise up to 10 candidates sorted by id (the matches, or the close ids when nothing matches). Returns {status, ids, total}. */
  function resolveQuery(nodes, q) {
    const ids = Object.keys(nodes).sort();
    q = String(q).trim();
    if (nodes[q]) return { status: "ok", ids: [q], total: 1 };
    if (nodes["rm." + q]) return { status: "ok", ids: ["rm." + q], total: 1 };
    const low = q.toLowerCase();
    const hits = ids.filter((i) => low && (i.toLowerCase().includes(low) || String(nodes[i].title).toLowerCase().includes(low)));
    if (hits.length === 1) return { status: "ok", ids: hits, total: 1 };
    if (hits.length) return { status: "ambiguous", ids: hits.slice(0, MAX_CANDIDATES), total: hits.length };
    const word = q.startsWith("rm.") ? q : "rm." + q;
    const scored = [];
    for (const x of ids) { const r = matchRatio(x, word); if (r >= 0.6) scored.push([r, x]); }
    scored.sort((p, c) => (c[0] - p[0]) || (c[1] < p[1] ? -1 : c[1] > p[1] ? 1 : 0)); // heapq.nlargest on (ratio, id) tuples
    return { status: "none", ids: scored.slice(0, MAX_CANDIDATES).map((p) => p[1]).sort(), total: scored.length };
  }

  /** The uncleared blockers of a node, and theirs in turn, as columns running left to right into the node. Capped; `truncated` says so. */
  function blockerChain(nodes, id, cap) {
    const include = new Set([id]), order = [id], edges = [];
    let truncated = false;
    for (let qi = 0; qi < order.length; qi++) {
      const n = order[qi];
      for (const b of (nodes[n] && nodes[n].uncleared_blockers) || []) {
        if (!nodes[b]) continue;
        if (!include.has(b)) {
          if (order.length >= cap) { truncated = true; continue; }
          include.add(b); order.push(b);
        }
        edges.push([b, n]);
      }
    }
    const level = {};
    for (const n of order) level[n] = 0;
    for (let pass = 0; pass < order.length; pass++) {
      let moved = false;
      for (const [b, n] of edges) if (level[b] < level[n] + 1) { level[b] = level[n] + 1; moved = true; }
      if (!moved) break;
    }
    const maxLevel = Math.max.apply(null, order.map((n) => level[n]));
    const cols = [];
    for (let c = 0; c <= maxLevel; c++) cols.push([]);
    for (const n of order.slice().sort()) cols[maxLevel - level[n]].push(n); // blockers furthest upstream sit leftmost
    return { cols, edges, truncated, count: order.length };
  }

  function criterionText(dw) {
    if (!dw) return "no criterion";
    const detail = { artifact: dw.path, decision: dw.record, check: dw.check, metric: dw.record + " " + dw.pointer + " " + dw.op + " " + dw.value }[dw.type];
    return detail ? dw.type + ": " + detail : dw.type;
  }

  function safeHref(href) { // http(s), mailto and in-page fragments only; nothing that could run or load from elsewhere
    const h = String(href || "").trim();
    return /^(https?:|mailto:)/i.test(h) || h.startsWith("#") ? h : null;
  }

  /** Markdown to HTML with raw HTML escaped, images reduced to their alt text and unsafe link targets dropped. */
  let mdInstance = null;
  function renderMarkdown(src) {
    if (!mdInstance) {
      mdInstance = new marked.Marked({ gfm: true, breaks: false });
      mdInstance.use({
        renderer: {
          html(text) { return esc(typeof text === "string" ? text : (text && text.text) || ""); },
          image(href, title, text) { return esc(typeof href === "object" && href ? href.text || "" : text || ""); },
          link(href, title, text) {
            const t = typeof href === "object" && href ? href : { href, title, text };
            const safe = safeHref(t.href);
            if (safe === null) return '<span title="' + esc(t.href || "") + '">' + t.text + "</span>";
            return '<a href="' + esc(safe) + '" rel="noopener noreferrer"' + (safe.startsWith("#") ? "" : ' target="_blank"') + ">" + t.text + "</a>";
          },
        },
      });
    }
    return mdInstance.parse(String(src || ""));
  }

  function routeParse(hash) {
    const m = /^#\/node\/(.+)$/.exec(hash || "");
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return null; }
  }
  function routeFormat(id) { return "#/node/" + encodeURIComponent(id); }

  window.RoadmapLogic = { VROOT, STATUS, STATUS_ORDER, statusInfo, esc, buildIndex, ancestors, navigate, subtree, relativeDepth, activeLeaves, outlineVisible, outlineRows, matchRatio, resolveQuery,
    blockerChain, criterionText, safeHref, renderMarkdown, routeParse, routeFormat };
  if (window.ROADMAP_TEST) return;

  /* ------------------------------------------------------------------ Part 2: interface */

  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const CARD_W = 190, CARD_H = 74, GAP_X = 22, GAP_Y = 54, PAD = 6;
  const TOKEN = (document.querySelector('meta[name="roadmap-token"]') || {}).content || "";

  const TABS = ["outline", "frontier", "problems"];
  const STATUS_CHIPS = ["ready", "active", "blocked", "expandable", "done"];

  const S = { state: null, index: null, focus: null, selected: null, tab: "outline", depth: 3, showSuperseded: false,
    connected: null, version: null, centre: false, nodeCache: new Map(), firstRenderMs: null, notice: null, candidates: [], candOn: -1, loadedOnce: false,
    open: new Set(), closed: new Set(), chips: new Set(), scrollOutline: true, pins: [], pinSet: new Set(), workCollapsed: false };

  function pref(key, value) { // per-viewer conveniences only; the page works without storage
    try {
      if (value === undefined) return localStorage.getItem("roadmap." + key);
      localStorage.setItem("roadmap." + key, String(value));
    } catch (e) { /* storage blocked */ }
    return null;
  }

  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat(Infinity)) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
    return e;
  }
  function add(parent, ...kids) { // Element.append(null) would write the word "null"
    for (const c of kids.flat(Infinity)) if (c !== null && c !== undefined && c !== false) parent.append(c.nodeType ? c : document.createTextNode(String(c)));
    return parent;
  }
  function sv(tag, attrs, ...kids) {
    const e = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v);
    for (const c of kids.flat(Infinity)) if (c) e.append(c.nodeType ? c : document.createTextNode(String(c)));
    return e;
  }

  const node = (id) => S.index.nodes[id];
  function swatch(status, stub) {
    const i = statusInfo(status);
    return h("span", { class: "sw s-" + status + (stub ? " stub" : ""), "aria-hidden": "true" }, i.glyph);
  }
  function statusPill(n) {
    const i = statusInfo(n.status);
    return h("span", { class: "pill s-" + n.status }, i.glyph + " " + i.label);
  }
  function est(n) { return n.estimate_days === null || n.estimate_days === undefined ? "" : (+n.estimate_days).toString() + " d"; }

  function toast(msg, isError) {
    const t = $("toast");
    t.textContent = msg;
    t.classList.toggle("err", !!isError);
    t.onclick = () => t.classList.remove("show");
    t.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove("show"), isError ? 12000 : 2600); // an error stays until read; a click dismisses it
  }

  /* ---- navigation */
  function go(id) {
    if (!S.index.nodes[id]) { toast("No node " + id); return; }
    const hash = routeFormat(id);
    if (location.hash === hash) applyFocus(id);
    else location.hash = hash; // the hashchange handler applies it, so back and forward use the same path
  }
  function applyFocus(id, notice) {
    S.focus = id;
    S.selected = id;
    S.notice = notice || null;
    S.centre = true; // the next render scrolls the new focus into view
    S.closed = new Set();
    S.scrollOutline = true;
    renderAll();
  }
  function select(id) {
    if (!S.index.nodes[id] || id === S.selected) return;
    S.selected = id;
    const rd = relativeDepth(S.index, id, S.focus);
    if (rd > S.depth) S.depth = rd; // a keyboard move below the cut-off pulls the cut-off down with it
    renderAll();
    const el = document.querySelector('#view .card[data-id="' + CSS.escape(id) + '"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  const isInterior = (id) => (S.index.children[id] || []).length > 0;
  const isPinned = (id) => S.pinSet.has(id);

  /* ---- pins */
  async function loadPins() {
    try {
      const r = await fetch("/api/pins", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
      setPins(j.pins);
    } catch (e) { toast("Could not load the pins: " + e.message, true); }
  }
  function setPins(list) { S.pins = (list || []).slice().sort(); S.pinSet = new Set(S.pins); }
  async function setPin(id, on) {
    try {
      const r = await fetch((on ? "/api/pin/" : "/api/unpin/") + encodeURIComponent(id), { method: "POST", headers: { "X-Roadmap-Token": TOKEN } });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
      setPins(j.pins);
      renderAll();
    } catch (e) { toast("Could not " + (on ? "pin " : "unpin ") + id + ": " + e.message, true); }
  }

  /* ---- editor and clipboard */
  async function openInEditor(id) {
    try {
      const r = await fetch("/api/open/" + encodeURIComponent(id), { method: "POST", headers: { "X-Roadmap-Token": TOKEN } });
      const j = await r.json();
      toast(r.ok ? "Opened " + j.opened : "Could not open: " + (j.error || r.status), !r.ok);
    } catch (e) { toast("Could not reach the server: " + e, true); }
  }
  async function copyId(id) {
    try { await navigator.clipboard.writeText(id); toast("Copied " + id); return; } catch (e) { /* fall through */ }
    const t = h("textarea", { "aria-hidden": "true", style: "position:fixed;left:-999px" }, id);
    document.body.append(t);
    t.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    t.remove();
    toast(ok ? "Copied " + id : "Copy failed; the id is " + id);
  }

  /* ---- node details (drawer and page) */
  async function nodeInfo(id) {
    if (S.nodeCache.has(id)) return S.nodeCache.get(id);
    const r = await fetch("/api/node/" + encodeURIComponent(id), { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const j = await r.json();
    S.nodeCache.set(id, j);
    return j;
  }

  function chip(id, extra) {
    const n = node(id);
    if (!n) return h("span", { class: "chip" }, h("span", { class: "ctext" }, id + " (missing)"));
    const unc = extra && extra.uncleared;
    return h("button", { class: "chip" + (unc ? " unc" : ""), title: n.title + " (" + statusInfo(n.status).label + ")", onclick: () => go(id) },
      swatch(n.status, n.kind === "stub"), h("span", { class: "ctext" }, n.title), h("span", { class: "muted mono" }, id));
  }
  function chipGroup(title, ids, uncleared) {
    if (!ids || !ids.length) return null;
    return h("div", {}, h("div", { class: "muted" }, title + " (" + ids.length + ")"), h("div", { class: "chips" }, ids.map((i) => chip(i, { uncleared: uncleared && uncleared.includes(i) }))));
  }

  function detailEl(id, page) {
    const n = node(id), idx = S.index;
    const root = h("div", { class: page ? "page" : "" });
    if (id === VROOT) return add(root, h("p", {}, n.title));
    const buttons = h("div", { class: "btns" },
      h("button", { onclick: () => openInEditor(id), title: "Open the node file in your editor (e)" }, "Open in editor"),
      h("button", { onclick: () => copyId(id) }, "Copy id"),
      page ? null : h("button", { onclick: () => go(id), title: "Make this the focus (Enter)" }, "Focus here"));
    root.append(
      h("div", { class: "statusline" }, statusPill(n), h("span", { class: "muted" }, n.kind + (n.kind === "stub" ? " (not yet decomposed)" : "")), est(n) ? h("span", {}, est(n)) : null),
      page ? h("h1", {}, n.title) : h("h3", { style: "margin:6px 0" }, n.title),
      h("div", { class: "mono muted" }, id), buttons,
      h("p", {}, n.reason || ""));
    const kv = h("dl", { class: "kv" });
    const row = (k, v) => { if (v !== null && v !== undefined && v !== "") kv.append(h("dt", {}, k), h("dd", {}, v)); };
    row("File", n.path);
    if (n.kind === "leaf" || n.done_when) {
      row("Done when", criterionText(n.done_when));
      const ev = n.evaluation;
      if (ev) {
        row("Evaluation", ev.result + ": " + ev.reason);
        if (ev.measured !== null && ev.measured !== undefined) row("Measured", String(ev.measured));
      }
    }
    row("Estimate", est(n));
    row("Tags", (n.tags || []).join(", "));
    if (n.active) row("Marked active", "yes");
    if (n.superseded_by) row("Superseded by", n.superseded_by);
    if (isInterior(id)) { const p = idx.progress[id]; row("Progress", p.done + " of " + p.total + " leaves and stubs done"); }
    root.append(kv);
    add(root, chipGroup("Blocked by (effective)", n.effective_blockers, n.uncleared_blockers), chipGroup("Blocks (dependents)", n.dependents),
      isInterior(id) ? chipGroup("Children", idx.children[id]) : null);
    const slot = h("div", { class: "md-slot" });
    root.append(slot);
    nodeInfo(id).then((info) => {
      if (!slot.isConnected) return;
      const refs = info.references || { files: [], commits: [] };
      add(slot,
        info.body && info.body.trim() ? Object.assign(h("div", { class: "md" }), { innerHTML: renderMarkdown(info.body) }) : null,
        h("h2", { class: "sec", style: "margin-left:0" }, "References (" + refs.files.length + " in files, " + refs.commits.length + " in commits)"),
        refs.files.length || refs.commits.length ? h("ul", { class: "refs" },
          refs.files.map((f) => h("li", {}, h("span", { class: "mono" }, f.path + ":" + f.line), "  ", f.text)),
          refs.commits.map((c) => h("li", {}, h("span", { class: "mono" }, c.hash), "  ", c.subject))) : h("p", { class: "muted" }, "None."));
    }).catch((e) => { if (slot.isConnected) slot.append(h("p", { class: "muted" }, "Could not load the body: " + e.message)); });
    return root;
  }

  /* ---- cards */
  function cardEl(id, left, top, w, hgt, hiddenKids) {
    const n = node(id), idx = S.index;
    const info = statusInfo(n.status);
    let meta;
    if (isInterior(id)) meta = [h("b", {}, info.glyph + " " + info.label), " · " + idx.progress[id].done + "/" + idx.progress[id].total + " done"];
    else meta = [h("b", {}, info.glyph + " " + info.label), n.kind === "stub" ? " · stub" : est(n) ? " · " + est(n) : ""];
    const c = h("div", { class: "card" + (n.kind === "stub" ? " stub" : "") + (n.status === "superseded" ? " superseded" : ""), role: "button", tabindex: "0", "data-id": id,
      "aria-label": n.title + ", " + info.label, style: "left:" + left + "px;top:" + top + "px;" + (w ? "width:" + w + "px;height:" + hgt + "px;" : "") + "border-left-color:var(--c-" + n.status + ")",
      onclick: () => select(id), ondblclick: () => go(id), onkeydown: (ev) => { if (ev.key === "Enter") { ev.preventDefault(); go(id); } } },
      h("div", { class: "ct" }, n.title), h("div", { class: "cm" }, meta), hiddenKids ? h("div", { class: "more", title: hiddenKids + " children below the depth limit" }, "⋯ " + hiddenKids) : null);
    return c;
  }

  /* ---- sidebar */
  function relatedSets() {
    const sel = S.selected && node(S.selected);
    return { blockers: new Set(sel ? sel.effective_blockers || [] : []), dependents: new Set(sel ? sel.dependents || [] : []) };
  }

  function renderWorking() {
    const box = $("working"), body = $("working-body");
    box.classList.toggle("collapsed", S.workCollapsed);
    $("working-toggle").setAttribute("aria-expanded", String(!S.workCollapsed));
    body.replaceChildren();
    const row = (id) => {
      const n = node(id);
      return h("div", { class: "wrow", "data-id": id, onclick: () => go(id) },
        h("button", { class: "wmain", title: n.title + " (" + statusInfo(n.status).label + ")" }, swatch(n.status, n.kind === "stub"), h("span", { class: "wt" }, n.title), h("span", { class: "wid mono" }, id)));
    };
    const active = activeLeaves(S.index);
    body.append(h("div", { class: "wgroup", id: "wg-active" }, h("h2", { class: "sec" }, "Active (" + active.length + ")"),
      active.length ? active.map(row) : h("p", { class: "muted wnone" }, "No leaf is marked active.")));
    body.append(h("div", { class: "wgroup", id: "wg-pinned" }, h("h2", { class: "sec" }, "Pinned (" + S.pins.length + ")"),
      S.pins.length ? S.pins.map((id) => {
        if (!S.state.nodes[id]) {
          return h("div", { class: "wrow dangling", "data-id": id }, h("span", { class: "wmain" }, h("span", { class: "sw s-unknown", "aria-hidden": "true" }, "?"), h("span", { class: "wt" }, "no longer in the roadmap"), h("span", { class: "wid mono" }, id)),
            h("button", { class: "unpin", onclick: () => setPin(id, false), title: "Remove this pin" }, "Unpin"));
        }
        const r = row(id);
        r.append(h("button", { class: "unpin", "aria-label": "Unpin " + node(id).title, title: "Unpin", onclick: (ev) => { ev.stopPropagation(); setPin(id, false); } }, "★"));
        return r;
      }) : h("p", { class: "muted wnone" }, "Nothing pinned. Press p on a node.")));
  }

  function effectiveOpen() { // the expanded outline rows: those opened by hand, plus the path to the focus, minus those closed by hand since the focus changed
    const open = new Set(S.open);
    for (let c = S.focus; c; c = S.index.parent[c]) open.add(c);
    for (const c of S.closed) open.delete(c);
    return open;
  }

  function renderOutline(body) {
    const idx = S.index;
    body.replaceChildren();
    if (idx.rootId === null) { body.append(h("p", { class: "pad muted" }, "No nodes. Add node files under roadmap/nodes/.")); return; }
    const text = $("search").value, statuses = Array.from(S.chips);
    const open = effectiveOpen();
    const rows = outlineRows(idx, { open, text, statuses });
    const onpath = new Set(); for (let c = S.focus; c; c = idx.parent[c]) onpath.add(c);
    body.append(h("div", { class: "chips-status", role: "group", "aria-label": "Filter by status" }, STATUS_CHIPS.map((s) =>
      h("button", { class: "fchip s-" + s, "data-status": s, "aria-pressed": String(S.chips.has(s)), onclick: () => { if (S.chips.has(s)) S.chips.delete(s); else S.chips.add(s); renderSidebar(); } }, statusInfo(s).glyph + " " + statusInfo(s).label))));
    if (!rows.length) body.append(h("p", { class: "pad muted" }, "Nothing matches."));
    const ul = h("ul", { class: "otree", role: "tree", "aria-label": "Roadmap outline" });
    for (const r of rows) {
      const n = node(r.id), p = idx.progress[r.id];
      const filtering = text.trim() || statuses.length;
      const li = h("li", { class: "orow" + (onpath.has(r.id) ? " onpath" : "") + (r.id === S.focus ? " focus" : "") + (r.id === S.selected ? " sel" : ""), "data-id": r.id, role: "treeitem",
        "aria-level": String(r.depth + 1), "aria-expanded": r.hasKids ? String(r.open) : null, "aria-selected": String(r.id === S.selected), style: "padding-left:" + (8 + 12 * r.depth) + "px" },
        r.hasKids && !filtering ? h("button", { class: "otoggle", "aria-label": (r.open ? "Collapse " : "Expand ") + n.title, onclick: (ev) => {
          ev.stopPropagation();
          if (r.open) { S.open.delete(r.id); S.closed.add(r.id); } else { S.open.add(r.id); S.closed.delete(r.id); }
          renderSidebar();
        } }, r.open ? "▾" : "▸") : h("span", { class: "ospacer" }),
        swatch(n.status, n.kind === "stub"),
        h("button", { class: "ot", title: n.title, onclick: () => go(r.id) }, n.title),
        r.hasKids ? h("span", { class: "frac", title: p.done + " of " + p.total + " leaves and stubs done" }, p.done + "/" + p.total) : null,
        isPinned(r.id) ? h("span", { class: "star-mark", title: "Pinned", "aria-label": "pinned" }, "★") : null);
      ul.append(li);
    }
    body.append(ul, legend());
    if (S.scrollOutline) {
      S.scrollOutline = false;
      const f = body.querySelector(".orow.focus");
      if (f && f.scrollIntoView) f.scrollIntoView({ block: "nearest" });
    }
  }

  function legend() {
    return h("div", { class: "legend", "aria-label": "Legend" },
      STATUS_ORDER.filter((s) => s !== "superseded" || S.showSuperseded).map((s) => h("span", {}, swatch(s), statusInfo(s).label)),
      h("span", {}, h("span", { class: "sw stub" }, ""), "hatched = stub"), h("span", {}, "◂ blocker of selection"), h("span", {}, "▸ depends on selection"));
  }

  function renderFrontier(body) {
    const idx = S.index, st = S.state;
    body.replaceChildren();
    const ids = (st.frontier || []).filter((i) => idx.nodes[i]);
    body.append(h("h2", { class: "sec" }, "Frontier: " + ids.length + " (" + ids.filter((i) => node(i).kind === "leaf").length + " ready leaves, " + ids.filter((i) => node(i).kind === "stub").length + " expandable stubs)"));
    if (!ids.length) { body.append(h("p", { class: "pad muted" }, "Nothing is ready or expandable.")); return; }
    body.append(h("ul", { class: "list" }, ids.map((i) => {
      const n = node(i);
      return h("li", {}, h("button", { onclick: () => go(i) },
        h("div", { class: "t" }, swatch(n.status, n.kind === "stub"), n.title),
        h("div", { class: "m" }, statusInfo(n.status).label + " · " + (n.kind === "stub" ? "stub, not yet decomposed" : criterionText(n.done_when) + (est(n) ? " · " + est(n) : ""))),
        h("div", { class: "m mono" }, i)));
    })));
  }

  function renderProblems(body) {
    const st = S.state, idx = S.index;
    body.replaceChildren();
    const group = (title, items, kind) => {
      body.append(h("h2", { class: "sec" }, title + ": " + items.length));
      if (!items.length) { body.append(h("p", { class: "pad muted", style: "padding-top:0" }, "None.")); return; }
      body.append(h("ul", { class: "list" }, items.map((p) => {
        const target = (p.ids || []).find((i) => idx.nodes[i]);
        return h("li", {}, h(target ? "button" : "div", target ? { onclick: () => go(target) } : { class: "pad" },
          h("div", { class: "t" }, (kind === "error" ? "✕ " : "! ") + p.code), h("div", { class: "m" }, p.message)));
      })));
    };
    group("Errors", st.errors || [], "error");
    group("Warnings", st.warnings || [], "warning");
  }

  function renderSidebar() {
    const body = $("side-body");
    const keep = body.scrollTop, scrolling = S.scrollOutline; // a focus change scrolls the outline to the focus row; otherwise the scroll stays
    renderWorking();
    for (const t of TABS) $("tab-" + t).setAttribute("aria-selected", String(S.tab === t));
    const nProb = (S.state.errors || []).length + (S.state.warnings || []).length;
    const badge = $("badge");
    badge.textContent = String(nProb);
    badge.className = "badge" + ((S.state.errors || []).length ? "" : " zero");
    badge.setAttribute("aria-label", (S.state.errors || []).length + " errors, " + (S.state.warnings || []).length + " warnings");
    ({ outline: renderOutline, frontier: renderFrontier, problems: renderProblems }[S.tab])(body);
    if (!scrolling) body.scrollTop = keep;
  }

  /* ---- main view */
  function renderCrumbs() {
    const idx = S.index, bar = $("crumbs");
    bar.replaceChildren();
    if (S.focus === null) return;
    const chain = [...ancestors(idx, S.focus)].reverse();
    chain.forEach((a) => bar.append(h("button", { onclick: () => go(a), title: statusInfo(node(a).status).label }, node(a).title), h("span", { class: "sep", "aria-hidden": "true" }, "›")));
    bar.append(h("span", { class: "cur", "aria-current": "page" }, node(S.focus).title));
    const tools = h("div", { class: "tools" });
    if (isInterior(S.focus)) {
      tools.append("Depth",
        h("button", { "aria-label": "Show one level fewer", onclick: () => { S.depth = Math.max(1, S.depth - 1); pref("depth", S.depth); renderAll(); } }, "−"),
        h("span", { "aria-live": "polite" }, String(S.depth)),
        h("button", { "aria-label": "Show one level more", onclick: () => { S.depth = Math.min(12, S.depth + 1); pref("depth", S.depth); renderAll(); } }, "+"));
    }
    const cb = h("input", { type: "checkbox", id: "supcb" });
    cb.checked = S.showSuperseded;
    cb.addEventListener("change", () => { S.showSuperseded = cb.checked; pref("superseded", cb.checked ? 1 : 0); S.index = buildIndex(S.state, S.showSuperseded); ensureValid(); renderAll(); });
    tools.append(h("label", {}, cb, " show superseded"));
    bar.append(tools);
  }

  function rectEdge(cx, cy, w, hh, tx, ty) { // where the line from the rectangle's centre towards (tx, ty) leaves the rectangle
    const dx = tx - cx, dy = ty - cy;
    if (!dx && !dy) return [cx, cy];
    const k = Math.min(dx ? (w / 2) / Math.abs(dx) : Infinity, dy ? (hh / 2) / Math.abs(dy) : Infinity);
    return [cx + dx * k, cy + dy * k];
  }

  function renderTreeView(view) {
    const idx = S.index;
    const root = d3.hierarchy(subtree(idx, S.focus, S.depth, 0), (d) => d.children);
    d3.tree().nodeSize([CARD_W + GAP_X, CARD_H + GAP_Y]).separation(() => 1)(root);
    let minX = Infinity, maxX = -Infinity, maxY = 0;
    root.each((d) => { minX = Math.min(minX, d.x); maxX = Math.max(maxX, d.x); maxY = Math.max(maxY, d.y); });
    const W = maxX - minX + CARD_W + 2 * PAD, H = maxY + CARD_H + 2 * PAD;
    const pos = {};
    root.each((d) => { pos[d.data.id] = { left: d.x - minX + PAD, top: d.y + PAD }; });
    const canvas = h("div", { class: "canvas", style: "width:" + W + "px;height:" + H + "px" });
    const svg = sv("svg", { class: "links", width: W, height: H },
      sv("defs", {}, ...["blocker", "dependent"].map((k) => sv("marker", { id: "arrow-" + k, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
        sv("path", { d: "M0,0 L10,5 L0,10 z", style: "fill:var(--edge-" + k + ")" })))));
    root.links().forEach((l) => {
      const a = pos[l.source.data.id], b = pos[l.target.data.id];
      const x1 = a.left + CARD_W / 2, y1 = a.top + CARD_H, x2 = b.left + CARD_W / 2, y2 = b.top, ym = (y1 + y2) / 2;
      svg.append(sv("path", { class: "link", d: "M" + x1 + "," + y1 + " C" + x1 + "," + ym + " " + x2 + "," + ym + " " + x2 + "," + y2 }));
    });
    canvas.append(svg);
    const rel = relatedSets();
    root.each((d) => {
      const id = d.data.id, p = pos[id];
      const c = cardEl(id, p.left, p.top, 0, 0, d.data.hidden);
      if (id === S.selected) c.classList.add("sel");
      if (rel.blockers.has(id)) c.classList.add("blocker");
      if (rel.dependents.has(id)) c.classList.add("dependent");
      canvas.append(c);
    });
    const sel = S.selected && pos[S.selected];
    if (sel) {
      const draw = (other, kind) => {
        const o = pos[other];
        if (!o || other === S.selected) return;
        const from = kind === "blocker" ? o : sel, to = kind === "blocker" ? sel : o; // the arrow runs from the blocker to the node it holds up
        const fc = [from.left + CARD_W / 2, from.top + CARD_H / 2], tc = [to.left + CARD_W / 2, to.top + CARD_H / 2];
        if (Math.abs(fc[1] - tc[1]) < CARD_H / 2) { // same row: the gap between neighbours is too small for an arrow, so loop under the cards
          const y = from.top + CARD_H + 4, drop = 30 + Math.min(40, Math.abs(tc[0] - fc[0]) / 14);
          svg.append(sv("path", { class: "edge " + kind, d: "M" + fc[0] + "," + y + " C" + fc[0] + "," + (y + drop) + " " + tc[0] + "," + (y + drop) + " " + tc[0] + "," + (to.top + CARD_H + 4), "marker-end": "url(#arrow-" + kind + ")" }),
            sv("text", { class: "edgelabel " + kind, x: (fc[0] + tc[0]) / 2, y: y + drop * 0.75 + 4, "text-anchor": "middle" }, kind === "blocker" ? "blocks selection" : "waits on selection"));
          return;
        }
        const a = rectEdge(fc[0], fc[1], CARD_W + 6, CARD_H + 6, tc[0], tc[1]), b = rectEdge(tc[0], tc[1], CARD_W + 10, CARD_H + 10, fc[0], fc[1]);
        const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        const nx = -(b[1] - a[1]) * 0.12, ny = (b[0] - a[0]) * 0.12; // a gentle bow so parallel edges do not overlap the tree links
        svg.append(sv("path", { class: "edge " + kind, d: "M" + a[0] + "," + a[1] + " Q" + (mx + nx) + "," + (my + ny) + " " + b[0] + "," + b[1], "marker-end": "url(#arrow-" + kind + ")" }),
          sv("text", { class: "edgelabel " + kind, x: mx + nx / 2, y: my + ny / 2, "text-anchor": "middle" }, kind === "blocker" ? "blocks selection" : "waits on selection"));
      };
      (node(S.selected).effective_blockers || []).forEach((b) => draw(b, "blocker"));
      (node(S.selected).dependents || []).forEach((d) => draw(d, "dependent"));
    }
    view.append(canvas);
    if (S.centre) { view.scrollLeft = Math.max(0, pos[S.focus].left + CARD_W / 2 + 18 - view.clientWidth / 2); view.scrollTop = 0; S.centre = false; }
  }

  function renderPage(view) {
    const id = S.focus, n = node(id);
    const page = detailEl(id, true);
    const unc = n.uncleared_blockers || [];
    if (unc.length) {
      const ch = blockerChain(S.state.nodes, id, 60);
      const w = 168, hh = 62, gx = 56, gy = 14;
      const maxRows = Math.max.apply(null, ch.cols.map((c) => c.length));
      const W = ch.cols.length * (w + gx) - gx + 2 * PAD, H = maxRows * (hh + gy) - gy + 2 * PAD;
      const box = h("div", { class: "canvas", style: "width:" + W + "px;height:" + H + "px;margin:0" });
      const pos = {};
      ch.cols.forEach((col, ci) => col.forEach((cid, ri) => { pos[cid] = { left: PAD + ci * (w + gx), top: PAD + ri * (hh + gy) + (maxRows - col.length) * (hh + gy) / 2 }; }));
      const svg = sv("svg", { class: "links", width: W, height: H }, sv("defs", {}, sv("marker", { id: "arrow-chain", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto" },
        sv("path", { d: "M0,0 L10,5 L0,10 z", style: "fill:var(--edge-blocker)" }))));
      ch.edges.forEach(([b, d]) => {
        if (!pos[b] || !pos[d]) return;
        const x1 = pos[b].left + w, y1 = pos[b].top + hh / 2, x2 = pos[d].left, y2 = pos[d].top + hh / 2, xm = (x1 + x2) / 2;
        svg.append(sv("path", { class: "edge blocker", d: "M" + x1 + "," + y1 + " C" + xm + "," + y1 + " " + xm + "," + y2 + " " + x2 + "," + y2, "marker-end": "url(#arrow-chain)" }));
      });
      box.append(svg);
      Object.keys(pos).forEach((cid) => { const c = cardEl(cid, pos[cid].left, pos[cid].top, w, hh, 0); if (cid === id) c.classList.add("sel"); box.append(c); });
      const slotEl = page.querySelector(".md-slot");
      [h("h2", { class: "sec", style: "margin-left:0" }, "Chain of uncleared blockers (" + ch.count + (ch.count === 1 ? " node" : " nodes") + ", upstream on the left)"),
        h("div", { class: "chain" }, box), ch.truncated ? h("p", { class: "muted" }, "The chain is cut at 60 nodes.") : null].filter(Boolean).forEach((e) => slotEl.before(e));
    }
    view.append(page);
    if (S.centre) { view.scrollLeft = 0; view.scrollTop = 0; S.centre = false; }
  }

  function renderView() {
    const view = $("view"), idx = S.index;
    view.replaceChildren();
    const errs = (S.state.errors || []).length;
    if (errs) view.append(h("div", { class: "banner" }, h("b", {}, errs + (errs === 1 ? " error" : " errors") + " in the roadmap. "),
      "What parsed is shown; statuses that cannot be derived read unknown. ", h("button", { onclick: () => { S.tab = "problems"; renderSidebar(); } }, "Show problems")));
    if (S.notice) view.append(h("div", { class: "banner" }, S.notice));
    if (S.focus === null) { view.append(h("p", { class: "pad muted" }, "No nodes yet. Node files go in roadmap/nodes/.")); return; }
    if (isInterior(S.focus)) renderTreeView(view);
    else renderPage(view);
  }

  function renderDrawer() {
    const d = $("drawer");
    const show = S.focus !== null && isInterior(S.focus) && S.selected !== null;
    d.hidden = !show;
    d.replaceChildren();
    if (show) d.append(detailEl(S.selected, false));
  }

  function renderStatusbar() {
    const sb = $("statusbar"), st = S.state;
    sb.replaceChildren();
    if (!st) return;
    const counts = st.counts || {};
    sb.append(h("span", {}, st.node_count + " nodes"));
    STATUS_ORDER.filter((s) => counts[s]).forEach((s) => sb.append(h("span", {}, swatch(s), counts[s] + " " + statusInfo(s).label)));
    sb.append(h("span", {}, "superseded " + (st.superseded_count || 0)), h("span", { class: "grow" }));
    sb.append(h("span", {}, "↑↓←→ move · Enter focus · e editor · / search · Esc"));
    if (S.bench) sb.append(h("span", {}, S.bench));
    sb.append(h("span", { title: "Time from navigation start to the first render of this page" }, S.firstRenderMs === null ? "" : "first render " + Math.round(S.firstRenderMs) + " ms"));
    sb.append(h("span", { title: "Live updates from /api/events" }, S.connected === null ? "" : S.connected ? "● live" : "○ reconnecting…"));
  }

  function renderAll() {
    renderSidebar();
    renderCrumbs();
    renderView();
    renderDrawer();
    renderStatusbar();
    document.title = (S.focus && node(S.focus) ? node(S.focus).title + " — " : "") + "Freyja roadmap";
  }

  /* ---- search */
  function renderCandidates() {
    const ul = $("cands");
    ul.replaceChildren();
    const q = $("search").value;
    if (!q.trim()) { S.candidates = []; return; }
    const r = resolveQuery(S.state.nodes, q);
    S.candidates = r.ids;
    if (S.candOn >= r.ids.length) S.candOn = r.ids.length - 1;
    if (!r.ids.length) { ul.append(h("li", { class: "none" }, "No match for " + q.trim())); return; }
    if (r.status === "none") ul.append(h("li", { class: "none" }, "No match; close ids:"));
    r.ids.forEach((id, i) => {
      const n = S.state.nodes[id];
      ul.append(h("li", { class: i === S.candOn ? "on" : "", role: "option" }, h("button", { onmousedown: (ev) => ev.preventDefault(), onclick: () => pick(id) },
        swatch(n.status, n.kind === "stub"), h("span", {}, n.title), h("span", { class: "muted mono" }, id))));
    });
    if (r.total > r.ids.length) ul.append(h("li", { class: "none" }, (r.total - r.ids.length) + " more; keep typing"));
  }
  function pick(id) { clearSearch(); go(id); }
  function clearSearch() { $("search").value = ""; S.candidates = []; S.candOn = -1; renderCandidates(); $("search").blur(); if (S.state) renderSidebar(); }

  /* ---- state and live updates */
  function ensureValid() {
    const idx = S.index;
    if (S.focus !== null && !idx.nodes[S.focus]) {
      S.focus = idx.rootId; // the focused node is gone (renamed or deleted): fall back to the root
    }
    if (S.focus === null) S.focus = idx.rootId;
    if (S.selected === null || !idx.nodes[S.selected]) S.selected = S.focus;
  }

  function applyState(state, first) {
    S.state = state;
    S.index = buildIndex(state, S.showSuperseded);
    S.nodeCache.clear();
    if (first) {
      const want = routeParse(location.hash);
      S.focus = want && S.index.nodes[want] ? want : S.index.rootId;
      S.selected = S.focus;
      S.centre = true;
      if (want && !S.index.nodes[want]) S.notice = "No node " + want + " in the roadmap; showing the root.";
    }
    ensureValid();
    const view = $("view"), side = $("side-body");
    const keep = [view.scrollTop, view.scrollLeft, side.scrollTop];
    renderAll();
    if (!first) { view.scrollTop = keep[0]; view.scrollLeft = keep[1]; side.scrollTop = keep[2]; }
  }

  async function fetchState() {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    S.version = r.headers.get("X-Roadmap-Version");
    return r.json();
  }
  let refreshTimer = null;
  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      try { await loadPins(); applyState(await fetchState(), false); } catch (e) { toast("Could not refresh: " + e.message); }
    }, 120);
  }
  function connectEvents() {
    if (!window.EventSource) return;
    const es = new EventSource("/api/events");
    es.addEventListener("changed", scheduleRefresh);
    es.onopen = () => { const again = S.connected === false; S.connected = true; renderStatusbar(); if (again) scheduleRefresh(); };
    es.onerror = () => { S.connected = false; renderStatusbar(); };
  }

  /* ---- keyboard, resize, tabs */
  function typing(t) { return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable); }
  document.addEventListener("keydown", (ev) => {
    if (!S.state || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const k = ev.key;
    if (typing(ev.target)) { // keys are ignored while typing, except in the search box
      if (ev.target.id !== "search") return;
      if (k === "Escape") { clearSearch(); ev.preventDefault(); }
      else if (k === "ArrowDown" || k === "ArrowUp") {
        if (!S.candidates.length) return;
        S.candOn = k === "ArrowDown" ? Math.min(S.candidates.length - 1, S.candOn + 1) : Math.max(0, S.candOn - 1);
        renderCandidates(); ev.preventDefault();
      } else if (k === "Enter") { const id = S.candidates[Math.max(0, S.candOn)]; if (id) pick(id); ev.preventDefault(); }
      return;
    }
    if (k === "ArrowUp" || k === "ArrowDown" || k === "ArrowLeft" || k === "ArrowRight") {
      if (ev.target && ev.target.closest && ev.target.closest("button, [role=tab]") && (k === "ArrowLeft" || k === "ArrowRight") && ev.target.matches("[role=tab]")) return;
      const to = navigate(S.index, S.selected, k);
      if (to !== S.selected) select(to);
      ev.preventDefault();
    } else if (k === "Enter") {
      if (ev.target && ev.target.closest && ev.target.closest("button, [role=button]")) return; // a focused control keeps its own Enter
      if (S.selected) go(S.selected);
    } else if (k === "e") { if (S.selected && S.selected !== VROOT) openInEditor(S.selected); }
    else if (k === "/") { ev.preventDefault(); $("search").focus(); $("search").select(); }
    else if (k === "Escape") { if ($("search").value || S.chips.size) { S.chips.clear(); clearSearch(); } }
  });

  document.querySelectorAll(".tabs [data-tab]").forEach((b) => b.addEventListener("click", () => { S.tab = b.dataset.tab; pref("tab", S.tab); renderSidebar(); }));
  $("working-toggle").addEventListener("click", () => { S.workCollapsed = !S.workCollapsed; pref("workcollapsed", S.workCollapsed ? 1 : 0); renderWorking(); });
  $("search").addEventListener("input", () => { S.candOn = 0; renderCandidates(); renderSidebar(); });
  $("search").addEventListener("blur", () => setTimeout(() => { if (document.activeElement !== $("search")) $("cands").replaceChildren(); }, 150));
  $("search").addEventListener("focus", renderCandidates);
  window.addEventListener("hashchange", () => {
    const id = routeParse(location.hash);
    if (!S.state) return;
    if (id && S.index.nodes[id]) applyFocus(id);
    else if (id) applyFocus(S.index.rootId, "No node " + id + " in the roadmap; showing the root.");
    else applyFocus(S.index.rootId);
  });

  (function sidebarResizer() {
    const bar = $("resizer"), app = $("app");
    const set = (px) => { const w = Math.max(220, Math.min(window.innerWidth * 0.7, px)); app.style.setProperty("--side-w", w + "px"); return w; };
    const saved = parseInt(pref("sidew") || "", 10);
    if (saved) set(saved);
    let drag = false;
    bar.addEventListener("pointerdown", (ev) => { drag = true; bar.classList.add("drag"); bar.setPointerCapture(ev.pointerId); });
    bar.addEventListener("pointermove", (ev) => { if (drag) set(ev.clientX); });
    const end = () => { if (!drag) return; drag = false; bar.classList.remove("drag"); pref("sidew", Math.round($("sidebar").getBoundingClientRect().width)); };
    bar.addEventListener("pointerup", end);
    bar.addEventListener("pointercancel", end);
    bar.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault(); ev.stopPropagation();
      const w = set($("sidebar").getBoundingClientRect().width + (ev.key === "ArrowRight" ? 24 : -24));
      pref("sidew", Math.round(w));
    });
  })();

  /* ---- start */
  (async function boot() {
    const q = new URLSearchParams(location.search);
    if (q.get("theme") === "light" || q.get("theme") === "dark") document.documentElement.dataset.theme = q.get("theme"); // for captures; otherwise the system setting decides
    S.depth = Math.max(1, Math.min(12, parseInt(q.get("depth") || pref("depth") || "3", 10) || 3));
    S.showSuperseded = pref("superseded") === "1";
    S.workCollapsed = pref("workcollapsed") === "1";
    S.tab = TABS.includes(pref("tab")) ? pref("tab") : "outline";
    try {
      const [state] = await Promise.all([fetchState(), loadPins()]);
      applyState(state, true);
      // capture parameters: they only seed the initial view state (selection, tab, search text, depth), so a screenshot can show it
      if (q.has("select") && S.index.nodes[q.get("select")]) S.selected = q.get("select");
      if (TABS.includes(q.get("tab"))) S.tab = q.get("tab");
      renderAll();
      if (q.get("q")) { $("search").value = q.get("q"); renderCandidates(); }
    } catch (e) {
      document.body.prepend(h("div", { class: "banner" }, "Could not load /api/state: " + e.message + ". Is `fy roadmap serve` still running?"));
      return;
    }
    requestAnimationFrame(() => {
      S.firstRenderMs = performance.now();
      document.documentElement.dataset.firstRenderMs = String(Math.round(S.firstRenderMs));
      document.documentElement.dataset.scriptRenderMs = String(Math.round(S.firstRenderMs - T0));
      document.documentElement.dataset.ready = "1";
      if (q.get("bench")) { // capture parameter: time 20 full re-renders (a selection change redraws everything) and show the average in the status bar
        const kids = S.index.children[S.focus] || [], t = performance.now();
        for (let i = 0; i < +q.get("bench"); i++) { S.selected = kids[i % Math.max(1, Math.min(2, kids.length))] || S.focus; renderAll(); }
        S.bench = "re-render " + ((performance.now() - t) / +q.get("bench")).toFixed(1) + " ms avg of " + q.get("bench");
      }
      renderStatusbar();
    });
    if (!new URLSearchParams(location.search).has("nolive")) connectEvents(); // ?nolive: no event stream (a headless capture never goes idle with one open)
  })();
})();
