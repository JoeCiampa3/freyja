/*
 * Roadmap viewer (docs/briefs/architecture/roadmap-brief1.md T8, roadmap-brief2.md T6 to T9). One page, no build step, no framework: d3 v7 for
 * the map's layouts and marked for node bodies, both vendored beside this file. It reads /api/state, /api/node/<id>, /api/pins and
 * /api/events; its write-shaped calls are POST /api/open/<id> (asks the local editor to open a node file) and POST /api/pin/<id> and
 * /api/unpin/<id> (the personal pins file).
 *
 * Part 1 is pure logic (index, child order, outline, breadcrumb, focus layout, automatic depth, map layout, keyboard navigation, query
 * resolution, blocker chain, Markdown): it touches no DOM and is exposed as window.RoadmapLogic so that tests/test_roadmap_viewer.py can
 * run it in a headless browser. Part 2 is the interface. Setting window.ROADMAP_TEST before this file loads skips Part 2.
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
  const CHILD_ORDER = ["active", "ready", "expandable", "blocked", "in_progress", "not_started", "done"]; // what to look at first
  const CRUMB_MAX = 28; // characters of a title in the breadcrumb; the full title is the hover text
  const MAX_DEPTH = 12;
  const LAYOUT = { cardW: 190, cardH: 76, leafH: 56, gapX: 22, gapY: 44, gapLeaf: 8, pad: 12, maxKids: 8 };
  const MAP_MIN_GAP = 14; // px between neighbours on one level of the map, at zoom 1
  const LABEL_PX = 12; // the height a title needs; titles appear when neighbours are this far apart on screen
  const MAP_RING = 7; // radius of an interior node's ring, px, constant on screen

  function statusInfo(s) { return STATUS[s] || STATUS.unknown; }
  function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  /** The short label where the node has one (roadmap-node/2), else the title: for places too small for a title. Tooltips and the drawer keep the title. */
  function shortOf(n) { return n && typeof n.short === "string" && n.short ? n.short : n ? String(n.title) : ""; }
  function truncateTitle(t, n) { t = String(t); return t.length <= n ? t : t.slice(0, n - 1) + "…"; }

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

  function relativeDepth(index, id, focus) { // how far below `focus` the node sits, or -1
    let n = 0;
    for (let c = id; c; c = index.parent[c], n++) if (c === focus) return n;
    return -1;
  }

  /** The children of a node in the order to look at them: active, ready, expandable, blocked, in progress, not started, done; ties by id. */
  function childRank(status) { const i = CHILD_ORDER.indexOf(status); return i < 0 ? CHILD_ORDER.length : i; }
  function orderedChildren(index, id) {
    return (index.children[id] || []).slice().sort((a, b) => childRank(index.nodes[a].status) - childRank(index.nodes[b].status) || (a < b ? -1 : a > b ? 1 : 0));
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

  /** The breadcrumb: beyond four ancestors it reads root › … › grandparent › parent › node until the … is clicked (`expanded`). */
  function crumbParts(index, focus, expanded) {
    const anc = ancestors(index, focus).reverse(); // root .. parent
    const part = (id, kind) => { const n = index.nodes[id]; return { kind, id, label: kind === "node" && n.short ? n.short : truncateTitle(n.title, CRUMB_MAX), full: n.title }; }; // the current node keeps its title
    let shown = anc.map((id) => part(id, "node"));
    if (!expanded && anc.length > 4) shown = [part(anc[0], "node"), { kind: "gap" }, part(anc[anc.length - 2], "node"), part(anc[anc.length - 1], "node")];
    return [...shown, part(focus, "cur")];
  }

  function usefulDepth(index, id) { // levels below `id`
    let m = 0;
    (function f(x, d) { if (d > m) m = d; for (const k of index.children[x] || []) f(k, d + 1); })(id, 0);
    return m;
  }

  /**
   * The compact layout of a node and `depth` levels below it, in canvas pixels. Under each node its childless children stack in one column
   * (left) and its interior children spread along one row (right of the column), both in child order; a node with more than 8 children shows
   * the first 8 and a "+k more" card at the foot of the column, which expands in place (`o.more` holds the ids expanded, and the card then
   * reads "show fewer"). Returns {items, links, width, height}. An item is {key, id, kind: card|more|fewer, x, y, w, h, hidden, parent,
   * column}; a link is {from, to, pts} (orthogonal, from the parent's bottom centre to the child's top or left edge).
   */
  function focusLayout(index, focus, o) {
    const Y = LAYOUT, depth = o.depth, more = o.more || new Set();
    const items = [], links = [];
    const childless = (id) => !(index.children[id] || []).length;
    function measure(id, level) {
      const kids = orderedChildren(index, id);
      if (!kids.length) return { id, w: Y.cardW, h: Y.leafH, cut: 0, leaf: true };
      if (level >= depth) return { id, w: Y.cardW, h: Y.cardH, cut: kids.length, leaf: false };
      const expanded = more.has(id), over = kids.length > Y.maxKids;
      const shown = over && !expanded ? kids.slice(0, Y.maxKids) : kids;
      const leaves = shown.filter(childless), inter = shown.filter((k) => !childless(k)).map((k) => measure(k, level + 1));
      const tail = over ? { count: kids.length - Y.maxKids, expanded } : null;
      const colN = leaves.length + (tail ? 1 : 0);
      const colH = colN ? colN * Y.leafH + (colN - 1) * Y.gapLeaf : 0, colW = colN ? Y.cardW : 0;
      const rowW = colW + (colN && inter.length ? Y.gapX : 0) + inter.reduce((s, b) => s + b.w, 0) + Math.max(0, inter.length - 1) * Y.gapX;
      const rowH = Math.max(colH, ...inter.map((b) => b.h), 0);
      return { id, w: Math.max(Y.cardW, rowW), h: Y.cardH + Y.gapY + rowH, leaf: false, cut: 0, leaves, inter, tail, colN, rowW, rowH };
    }
    function place(b, x0, y0, parent, column) {
      const x = x0 + (b.w - Y.cardW) / 2;
      const it = { key: b.id, id: b.id, kind: "card", x, y: y0, w: Y.cardW, h: b.leaf ? Y.leafH : Y.cardH, hidden: b.cut, parent, column };
      items.push(it);
      if (b.leaves === undefined) return it;
      const rowX = x0 + (b.w - b.rowW) / 2, rowY = y0 + Y.cardH + Y.gapY, px = x + Y.cardW / 2, py = y0 + Y.cardH, busY = rowY - Y.gapY / 2;
      let cx = rowX;
      if (b.colN) {
        const spineX = cx - 8;
        let cy = rowY;
        const col = b.leaves.map((id) => ({ id, kind: "card" }));
        if (b.tail) col.push({ kind: b.tail.expanded ? "fewer" : "more" });
        for (const c of col) {
          const child = c.kind === "card"
            ? { key: c.id, id: c.id, kind: "card", x: cx, y: cy, w: Y.cardW, h: Y.leafH, hidden: 0, parent: b.id, column: true }
            : { key: "more:" + b.id, id: null, of: b.id, kind: c.kind, count: b.tail.count, x: cx, y: cy, w: Y.cardW, h: Y.leafH, hidden: 0, parent: b.id, column: true };
          items.push(child);
          links.push({ from: b.id, to: child.key, pts: [[px, py], [px, busY], [spineX, busY], [spineX, cy + Y.leafH / 2], [cx, cy + Y.leafH / 2]] });
          cy += Y.leafH + Y.gapLeaf;
        }
        cx += Y.cardW + Y.gapX;
      }
      for (const sb of b.inter) {
        const child = place(sb, cx, rowY, b.id, false);
        const tx = child.x + Y.cardW / 2;
        links.push({ from: b.id, to: child.key, pts: [[px, py], [px, busY], [tx, busY], [tx, rowY]] });
        cx += sb.w + Y.gapX;
      }
      return it;
    }
    const block = measure(focus, 0);
    place(block, Y.pad, Y.pad, null, false);
    return { items, links, width: block.w + 2 * Y.pad, height: block.h + 2 * Y.pad };
  }

  /** The largest depth (1 to 12) whose layout is no wider than `width`, and 1 when none is. Collapsed "+k more" cards are assumed. */
  function autoDepth(index, focus, width) {
    const top = Math.min(MAX_DEPTH, usefulDepth(index, focus));
    let best = 1;
    for (let d = 1; d <= top; d++) { if (focusLayout(index, focus, { depth: d }).width <= width) best = d; else break; }
    return best;
  }

  /* ---- the map: radial or top-down tidy tree of the whole roadmap */
  const MARKER_SHAPE = { done: "square", ready: "circle", active: "triangle", blocked: "diamond", expandable: "cross", unknown: "hex", stale: "hex",
    in_progress: "ring", not_started: "ring", superseded: "dot" };
  function markerShape(status) { return MARKER_SHAPE[status] || "hex"; }
  /** SVG path of a marker shape centred on the origin, `r` the half extent. */
  function shapePath(name, r) {
    const f = (v) => +v.toFixed(2), s = r;
    switch (name) {
      case "square": return `M${-s},${-s}H${s}V${s}H${-s}Z`;
      case "triangle": return `M0,${-s * 1.15}L${f(s * 1.05)},${f(s * 0.8)}H${f(-s * 1.05)}Z`;
      case "diamond": return `M0,${-s * 1.3}L${f(s * 1.3)},0L0,${f(s * 1.3)}L${f(-s * 1.3)},0Z`;
      case "cross": { const t = s * 0.38; return `M${-t},${-s}H${t}V${-t}H${s}V${t}H${t}V${s}H${-t}V${t}H${-s}V${-t}H${-t}Z`; }
      case "hex": return `M${-s},0L${f(-s / 2)},${f(-s * 0.87)}H${f(s / 2)}L${s},0L${f(s / 2)},${f(s * 0.87)}H${f(-s / 2)}Z`;
      case "dot": return `M${-s / 2},0A${s / 2},${s / 2} 0 1,1 ${s / 2},0A${s / 2},${s / 2} 0 1,1 ${-s / 2},0Z`;
      default: return `M${-s},0A${s},${s} 0 1,1 ${s},0A${s},${s} 0 1,1 ${-s},0Z`; // circle, ring
    }
  }
  /** The filled part of an interior node's ring: a wedge from 12 o'clock clockwise for `frac` (0 to 1) of the turn; "" for none, a disc for all. */
  function ringWedge(frac, r) {
    if (!(frac > 0)) return "";
    if (frac >= 1) return `M0,${-r}A${r},${r} 0 1,1 0,${r}A${r},${r} 0 1,1 0,${-r}Z`;
    const a = frac * 2 * Math.PI, x = +(r * Math.sin(a)).toFixed(3), y = +(-r * Math.cos(a)).toFixed(3);
    return `M0,0L0,${-r}A${r},${r} 0 ${frac > 0.5 ? 1 : 0},1 ${x},${y}Z`;
  }

  /**
   * Layout of the whole tree for the map. mode "radial": the root at the centre, depth as rings (radius = depth x step, a d3 tidy tree
   * mapped to angle, so a ring means a depth); mode "top": the root at the top, a level per row. Neighbours on a level are never closer
   * than MAP_MIN_GAP. Returns {nodes: [{id, depth, x, y, r, angle}], links: [{source, target}], sectors, step, minGap, bounds, mode}; a sector is
   * a faint background for a first-layer branch ({id, title, a0, a1} radial, {id, title, x0, x1} top-down).
   */
  function mapLayout(index, mode) {
    const nest = (id) => ({ id, children: (index.children[id] || []).map(nest) });
    const rootId = index.rootId, heads = index.children[rootId] || [];
    // Each first-layer branch is its own tidy tree in a range of its own: laid out as one tree, a deep branch can reach under its neighbour's
    // shallow nodes, and then a background sector per branch could not contain exactly that branch's nodes.
    const subs = heads.map((hd) => d3.hierarchy(nest(hd), (d) => d.children));
    const rows = []; // {id, depth, u} with u the position along the level axis (angle units / px)
    const links = heads.map((hd) => ({ source: rootId, target: hd }));
    let step, offset = 0;
    const GAP = mode === "radial" ? 1 : MAP_MIN_GAP; // empty room between two branches, in the units of u
    const sep = (a, b) => (a.parent === b.parent ? 1 : 2) / Math.max(1, a.depth + 1); // a.depth + 1 is the depth in the whole tree
    const spans = subs.map((sub) => {
      if (mode === "radial") d3.tree().nodeSize([1, 1]).separation(sep)(sub); else d3.tree().nodeSize([MAP_MIN_GAP, 1]).separation(() => 1)(sub);
      let lo = Infinity, hi = -Infinity;
      sub.each((d) => { if (d.x < lo) lo = d.x; if (d.x > hi) hi = d.x; });
      return [lo, hi];
    });
    subs.forEach((sub, i) => {
      sub.each((d) => rows.push({ id: d.data.id, depth: d.depth + 1, u: offset + d.x - spans[i][0] }));
      for (const l of sub.links()) links.push({ source: l.source.data.id, target: l.target.data.id });
      offset += spans[i][1] - spans[i][0] + GAP;
    });
    const total = Math.max(offset, 1); // for the radial layout the last gap closes the circle
    let nodes;
    if (mode === "radial") {
      for (const r of rows) r.angle = r.u / total * 2 * Math.PI;
      const at = (unit) => (r) => [unit * r.depth * Math.sin(r.angle), -unit * r.depth * Math.cos(r.angle)];
      const unit0 = 100, g0 = minGapOf(rows, at(unit0), (r) => r.angle, true);
      step = Math.max(70, unit0 * Math.max(1, Number.isFinite(g0) ? MAP_MIN_GAP * 1.0000001 / g0 : 1)); // room between rings for a title, and between neighbours for a marker
      nodes = [{ id: rootId, depth: 0, angle: 0, r: 0, x: 0, y: 0 }, ...rows.map((r) => ({ id: r.id, depth: r.depth, angle: r.angle, r: r.depth * step,
        x: r.depth * step * Math.sin(r.angle), y: -r.depth * step * Math.cos(r.angle) }))];
    } else {
      step = 90;
      const mid = rows.length ? (Math.min(...rows.filter((r) => r.depth === 1).map((r) => r.u)) + Math.max(...rows.filter((r) => r.depth === 1).map((r) => r.u))) / 2 : 0;
      nodes = [{ id: rootId, depth: 0, x: mid, y: 0 }, ...rows.map((r) => ({ id: r.id, depth: r.depth, x: r.u, y: r.depth * step }))];
    }
    const by = {}; for (const n of nodes) by[n.id] = n;
    const minGap = minGapOf(nodes, (n) => [n.x, n.y], mode === "radial" ? (n) => n.angle : (n) => n.x, mode === "radial");
    // each branch's extent along the level axis: disjoint by construction
    const extent = heads.map((hd) => {
      let lo = Infinity, hi = -Infinity;
      (function f(id) { const v = mode === "radial" ? by[id].angle : by[id].x; if (v < lo) lo = v; if (v > hi) hi = v; for (const k of index.children[id] || []) f(k); })(hd);
      return [lo, hi];
    });
    const sectors = heads.map((hd, i) => ({ id: hd, title: index.nodes[hd].title, label: shortOf(index.nodes[hd]) }));
    if (mode === "radial") {
      const T = 2 * Math.PI;
      heads.forEach((hd, i) => {
        const prevHi = i ? extent[i - 1][1] : extent[heads.length - 1][1] - T, nextLo = i < heads.length - 1 ? extent[i + 1][0] : extent[0][0] + T;
        sectors[i].a0 = (prevHi + extent[i][0]) / 2; sectors[i].a1 = (extent[i][1] + nextLo) / 2;
      });
    } else {
      heads.forEach((hd, i) => {
        sectors[i].x0 = i ? (extent[i - 1][1] + extent[i][0]) / 2 : extent[i][0] - MAP_MIN_GAP / 2;
        sectors[i].x1 = i < heads.length - 1 ? (extent[i][1] + extent[i + 1][0]) / 2 : extent[i][1] + MAP_MIN_GAP / 2;
      });
    }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of nodes) { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); }
    const maxDepth = Math.max.apply(null, nodes.map((n) => n.depth));
    const reach = mode === "radial" ? (maxDepth + 0.6) * step : 0; // sectors and their labels reach beyond the outermost ring
    if (mode === "radial") { const r2 = reach + 0.4 * step; x0 = -r2; x1 = r2; y0 = -r2; y1 = r2; } // the rim titles sit just outside the sectors else { y0 -= 40; y1 += 40; x0 -= MAP_MIN_GAP; x1 += MAP_MIN_GAP; }
    return { mode, nodes, links, sectors, step, minGap, bounds: { x0, y0, x1, y1 }, maxDepth, reach };
  }
  /** The smallest distance between neighbours on one level (sorted by `key`; for a ring the last wraps round to the first). */
  function minGapOf(items, pos, key, wrap) {
    const levels = {};
    for (const it of items) (levels[it.depth] = levels[it.depth] || []).push(it);
    let gap = Infinity;
    for (const list of Object.values(levels)) {
      list.sort((a, b) => key(a) - key(b));
      const n = list.length;
      for (let i = 0; i + 1 < n; i++) { const a = pos(list[i]), b = pos(list[i + 1]); gap = Math.min(gap, Math.hypot(a[0] - b[0], a[1] - b[1])); }
      if (wrap && n > 2) { const a = pos(list[n - 1]), b = pos(list[0]); gap = Math.min(gap, Math.hypot(a[0] - b[0], a[1] - b[1])); }
    }
    return gap;
  }
  /** The zoom at which neighbours on a level are far enough apart on screen for their titles not to overlap. */
  function labelZoom(layout) { return Number.isFinite(layout.minGap) ? LABEL_PX / layout.minGap : 0; }

  /** Difflib.SequenceMatcher.ratio() with a = candidate and b = query, no junk: what Python's get_close_matches ranks by. */
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

  window.RoadmapLogic = { VROOT, STATUS, shortOf, STATUS_ORDER, CHILD_ORDER, LAYOUT, MAX_DEPTH, MAP_MIN_GAP, LABEL_PX, statusInfo, esc, truncateTitle, buildIndex, ancestors,
    navigate, relativeDepth, orderedChildren, activeLeaves, outlineVisible, outlineRows, crumbParts, usefulDepth, focusLayout, autoDepth, markerShape, shapePath,
    ringWedge, mapLayout, labelZoom, matchRatio, resolveQuery, blockerChain, criterionText, safeHref, renderMarkdown, routeParse, routeFormat };
  if (window.ROADMAP_TEST) return;

  /* ------------------------------------------------------------------ Part 2: interface */

  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const TOKEN = (document.querySelector('meta[name="roadmap-token"]') || {}).content || "";
  const TABS = ["outline", "frontier", "problems"];
  const STATUS_CHIPS = ["ready", "active", "blocked", "expandable", "done"];

  const S = { state: null, index: null, focus: null, selected: null, tab: "outline", showSuperseded: false, connected: null, version: null, nodeCache: new Map(),
    firstRenderMs: null, notice: null, candidates: [], candOn: -1,
    depthOverride: null, more: new Set(), crumbsOpen: false, fv: { k: 1, x: 0, y: 0 }, fitPending: true, layout: null, shownDepth: 1,
    open: new Set(), closed: new Set(), chips: new Set(), scrollOutline: true, pins: [], pinSet: new Set(), workCollapsed: false,
    map: false, mapMode: "radial", mapFrontier: false, mv: { k: 1, x: 0, y: 0 }, stamp: 0, mapBuilt: null, mapState: null };

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
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  const node = (id) => S.index.nodes[id];
  const isInterior = (id) => (S.index.children[id] || []).length > 0;
  const isPinned = (id) => S.pinSet.has(id);
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

  /* ---- pan and zoom, shared by the focus view and the map */
  function viewport(el, o) {
    let drag = null;
    const vp = { moved: false };
    el.addEventListener("wheel", (ev) => {
      if (!o.enabled()) return;
      ev.preventDefault();
      const r = el.getBoundingClientRect(), t = o.get();
      const k = clamp(t.k * Math.exp(-ev.deltaY * 0.0015), o.minK(), o.maxK());
      const px = ev.clientX - r.left, py = ev.clientY - r.top;
      o.set({ k, x: px - (px - t.x) * (k / t.k), y: py - (py - t.y) * (k / t.k) });
    }, { passive: false });
    el.addEventListener("pointerdown", (ev) => {
      if (!o.enabled() || ev.button !== 0 || (ev.target.closest && ev.target.closest("button, input, a"))) return;
      drag = { x: ev.clientX, y: ev.clientY, t: o.get(), moved: false, id: ev.pointerId };
    });
    el.addEventListener("pointermove", (ev) => {
      if (!drag) return;
      const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 4) return;
      if (!drag.moved) { drag.moved = true; try { el.setPointerCapture(drag.id); } catch (e) { /* no such pointer */ } el.classList.add("panning"); }
      o.set({ k: drag.t.k, x: drag.t.x + dx, y: drag.t.y + dy });
    });
    const end = () => {
      if (!drag) return;
      if (drag.moved) { vp.moved = true; setTimeout(() => { vp.moved = false; }, 0); } // the click that follows a drag is not a click
      drag = null;
      el.classList.remove("panning");
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    return vp;
  }

  /* ---- navigation */
  function go(id) {
    if (!S.index.nodes[id]) { toast("No node " + id); return; }
    S.map = false;
    document.body.classList.remove("map");
    const hash = routeFormat(id);
    if (location.hash === hash) applyFocus(id);
    else location.hash = hash; // the hashchange handler applies it, so back and forward use the same path
  }
  function applyFocus(id, notice) {
    S.focus = id;
    S.selected = id;
    S.notice = notice || null;
    S.depthOverride = null; // the +/- controls last until the focus changes
    S.more = new Set();
    S.crumbsOpen = false;
    S.closed = new Set();
    S.fitPending = true;
    S.scrollOutline = true;
    if (S.map) { S.map = false; document.body.classList.remove("map"); }
    renderAll();
  }
  function select(id) {
    if (!S.index.nodes[id] || id === S.selected) return;
    S.selected = id;
    if (!S.map) {
      const rd = relativeDepth(S.index, id, S.focus);
      if (rd > S.shownDepth) S.depthOverride = Math.min(MAX_DEPTH, rd); // a keyboard move below the cut-off pulls the cut-off down with it
    }
    renderAll();
    if (S.map) ensureMapVisible(id); else ensureCardVisible(id);
  }

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
  function togglePin(id) { if (id && id !== VROOT) setPin(id, !isPinned(id)); }
  function starButton(id, label) {
    const on = isPinned(id);
    return h("button", { class: "star" + (on ? " on" : ""), "aria-pressed": String(on), "aria-label": (on ? "Unpin " : "Pin ") + node(id).title, title: (on ? "Unpin" : "Pin") + " (p)",
      onclick: (ev) => { ev.stopPropagation(); togglePin(id); } }, (on ? "★" : "☆") + (label ? " " + (on ? "Unpin" : "Pin") : ""));
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
      starButton(id, true),
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
      isInterior(id) ? chipGroup("Children", orderedChildren(idx, id)) : null);
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
  function cardEl(item, o) {
    const id = item.id, n = node(id), idx = S.index;
    const info = statusInfo(n.status), interior = isInterior(id);
    let meta;
    if (interior) meta = [h("b", {}, info.glyph + " " + info.label), " · " + idx.progress[id].done + "/" + idx.progress[id].total + " done"];
    else meta = [h("b", {}, info.glyph + " " + info.label), n.kind === "stub" ? " · stub" : est(n) ? " · " + est(n) : ""];
    const p = interior ? idx.progress[id] : null;
    const pct = p && p.total ? 100 * p.done / p.total : 0;
    return h("div", { class: "card" + (n.kind === "stub" ? " stub" : "") + (n.status === "superseded" ? " superseded" : "") + (item.column ? " leafcard" : ""), role: "button", tabindex: "0", "data-id": id,
      "aria-label": n.title + ", " + info.label, style: "left:" + item.x + "px;top:" + item.y + "px;width:" + item.w + "px;height:" + item.h + "px;border-left-color:var(--c-" + n.status + ")",
      onclick: () => { if (S.vp && S.vp.moved) return; select(id); }, ondblclick: () => go(id), onkeydown: (ev) => { if (ev.key === "Enter") { ev.preventDefault(); go(id); } } },
      h("div", { class: "ct" }, n.title), h("div", { class: "cm" }, meta),
      interior ? h("div", { class: "bar", "aria-hidden": "true" }, h("i", { style: "width:" + pct.toFixed(1) + "%" })) : null,
      item.hidden ? h("div", { class: "more", title: item.hidden + " children below the depth limit" }, "⋯ " + item.hidden) : null,
      o && o.noStar ? null : starButton(id));
  }
  function moreCardEl(item) {
    const expanded = item.kind === "fewer";
    return h("div", { class: "card more-card", role: "button", tabindex: "0", "data-more": item.of, "aria-label": expanded ? "Show fewer children" : item.count + " more children",
      style: "left:" + item.x + "px;top:" + item.y + "px;width:" + item.w + "px;height:" + item.h + "px",
      onclick: () => { if (S.vp && S.vp.moved) return; if (expanded) S.more.delete(item.of); else S.more.add(item.of); renderView(); },
      onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); ev.target.click(); } } },
      h("div", { class: "ct" }, expanded ? "Show fewer" : "+" + item.count + " more"), h("div", { class: "cm" }, expanded ? "collapse to the first 8" : "show the rest here"));
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

  /* ---- main view: crumbs */
  function renderCrumbs() {
    const idx = S.index, bar = $("crumbs");
    bar.replaceChildren();
    if (S.focus === null) return;
    const sep = () => h("span", { class: "sep", "aria-hidden": "true" }, "›");
    for (const p of crumbParts(idx, S.focus, S.crumbsOpen)) {
      if (p.kind === "gap") bar.append(h("button", { class: "crumb-gap", title: "Show the whole path", "aria-label": "Show the whole path", onclick: () => { S.crumbsOpen = true; renderCrumbs(); } }, "…"), sep());
      else if (p.kind === "node") bar.append(h("button", { title: p.full, onclick: () => go(p.id) }, p.label), sep());
      else bar.append(h("span", { class: "cur", "aria-current": "page", title: p.full }, p.label));
    }
    const tools = h("div", { class: "tools" });
    if (isInterior(S.focus)) {
      tools.append("Depth",
        h("button", { "aria-label": "Show one level fewer", onclick: () => { S.depthOverride = Math.max(1, S.shownDepth - 1); S.fitPending = true; renderAll(); } }, "−"),
        h("span", { id: "depthval", "aria-live": "polite", title: S.depthOverride === null ? "chosen to fit the width of this view" : "set by hand until the focus changes" }, String(S.shownDepth)),
        h("button", { "aria-label": "Show one level more", onclick: () => { S.depthOverride = Math.min(MAX_DEPTH, S.shownDepth + 1); S.fitPending = true; renderAll(); } }, "+"),
        h("button", { id: "fitbtn", title: "Fit the view (f)", onclick: () => fitView() }, "Fit"));
    }
    tools.append(h("button", { id: "mapbtn", title: "Map of the whole roadmap (m)", onclick: () => setMap(!S.map) }, "Map"));
    const cb = h("input", { type: "checkbox", id: "supcb" });
    cb.checked = S.showSuperseded;
    cb.addEventListener("change", () => { S.showSuperseded = cb.checked; pref("superseded", cb.checked ? 1 : 0); S.index = buildIndex(S.state, S.showSuperseded); S.stamp++; ensureValid(); S.fitPending = true; renderAll(); });
    tools.append(h("label", {}, cb, " show superseded"));
    bar.append(tools);
  }

  /* ---- main view: the focus tree, panned and zoomed */
  function rectEdge(cx, cy, w, hh, tx, ty) { // where the line from the rectangle's centre towards (tx, ty) leaves the rectangle
    const dx = tx - cx, dy = ty - cy;
    if (!dx && !dy) return [cx, cy];
    const k = Math.min(dx ? (w / 2) / Math.abs(dx) : Infinity, dy ? (hh / 2) / Math.abs(dy) : Infinity);
    return [cx + dx * k, cy + dy * k];
  }
  const stageEl = () => document.querySelector("#view .stage");
  function applyFv() {
    const s = stageEl();
    if (!s) return;
    const t = S.fv;
    s.style.transform = "translate(" + t.x.toFixed(2) + "px," + t.y.toFixed(2) + "px) scale(" + t.k.toFixed(4) + ")";
    s.dataset.k = t.k.toFixed(4); s.dataset.tx = t.x.toFixed(2); s.dataset.ty = t.y.toFixed(2);
  }
  function fitView() {
    if (S.map) { mapFit(); return; }
    const view = $("view"), lay = S.layout;
    if (!lay || !stageEl()) return;
    const w = view.clientWidth || 1;
    const k = clamp(Math.min(1, w / lay.width), 0.25, 1);
    view.dataset.fitwidth = String(Math.round(w)); // what this fit was computed against
    S.fv = { k, x: Math.max(0, (w - lay.width * k) / 2), y: 0 };
    applyFv();
  }
  function ensureCardVisible(id) {
    const lay = S.layout, view = $("view"), it = lay && lay.items.find((i) => i.kind === "card" && i.id === id);
    if (!it || !stageEl()) return;
    const t = S.fv, m = 16, W = view.clientWidth, H = view.clientHeight;
    const l = t.x + it.x * t.k, r = t.x + (it.x + it.w) * t.k, tp = t.y + it.y * t.k, b = t.y + (it.y + it.h) * t.k;
    let dx = 0, dy = 0;
    if (l < m) dx = m - l; else if (r > W - m) dx = W - m - r;
    if (tp < m) dy = m - tp; else if (b > H - m) dy = H - m - b;
    if (dx || dy) { S.fv = { k: t.k, x: t.x + dx, y: t.y + dy }; applyFv(); }
  }

  function effectiveDepth() {
    if (S.depthOverride !== null) return clamp(S.depthOverride, 1, MAX_DEPTH);
    return autoDepth(S.index, S.focus, $("view").clientWidth || 800);
  }

  function renderTreeView(view) {
    view.className = "tree-mode";
    const idx = S.index;
    const depth = effectiveDepth();
    if (depth !== S.shownDepth) S.fitPending = true;
    S.shownDepth = depth;
    view.dataset.depth = String(depth);
    view.dataset.auto = S.depthOverride === null ? "1" : "0";
    const lay = focusLayout(idx, S.focus, { depth, more: S.more });
    S.layout = lay;
    const pos = {};
    for (const it of lay.items) if (it.kind === "card") pos[it.id] = it;
    const stage = h("div", { class: "stage", style: "width:" + lay.width + "px;height:" + lay.height + "px" });
    const svg = sv("svg", { class: "links", width: lay.width, height: lay.height },
      sv("defs", {}, ...["blocker", "dependent"].map((k) => sv("marker", { id: "arrow-" + k, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" },
        sv("path", { d: "M0,0 L10,5 L0,10 z", style: "fill:var(--edge-" + k + ")" })))));
    for (const l of lay.links) svg.append(sv("path", { class: "link", d: "M" + l.pts.map((p) => p[0] + "," + p[1]).join(" L") }));
    stage.append(svg);
    const rel = relatedSets();
    for (const it of lay.items) {
      if (it.kind !== "card") { stage.append(moreCardEl(it)); continue; }
      const c = cardEl(it);
      if (it.id === S.selected) c.classList.add("sel");
      if (rel.blockers.has(it.id)) c.classList.add("blocker");
      if (rel.dependents.has(it.id)) c.classList.add("dependent");
      stage.append(c);
    }
    const sel = S.selected && pos[S.selected];
    if (sel) {
      const draw = (other, kind) => {
        const o = pos[other];
        if (!o || other === S.selected) return;
        const from = kind === "blocker" ? o : sel, to = kind === "blocker" ? sel : o; // the arrow runs from the blocker to the node it holds up
        const fc = [from.x + from.w / 2, from.y + from.h / 2], tc = [to.x + to.w / 2, to.y + to.h / 2];
        const label = kind === "blocker" ? "blocks selection" : "waits on selection";
        if (Math.abs(fc[1] - tc[1]) < Math.max(from.h, to.h) / 2) { // same row: the gap between neighbours is too small for an arrow, so loop under the cards
          const y = from.y + from.h + 4, drop = 30 + Math.min(40, Math.abs(tc[0] - fc[0]) / 14);
          svg.append(sv("path", { class: "edge " + kind, d: "M" + fc[0] + "," + y + " C" + fc[0] + "," + (y + drop) + " " + tc[0] + "," + (y + drop) + " " + tc[0] + "," + (to.y + to.h + 4), "marker-end": "url(#arrow-" + kind + ")" }),
            sv("text", { class: "edgelabel " + kind, x: (fc[0] + tc[0]) / 2, y: y + drop * 0.75 + 4, "text-anchor": "middle" }, label));
          return;
        }
        const a = rectEdge(fc[0], fc[1], from.w + 6, from.h + 6, tc[0], tc[1]), b = rectEdge(tc[0], tc[1], to.w + 10, to.h + 10, fc[0], fc[1]);
        const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        const nx = -(b[1] - a[1]) * 0.12, ny = (b[0] - a[0]) * 0.12; // a gentle bow so parallel edges do not overlap the tree links
        svg.append(sv("path", { class: "edge " + kind, d: "M" + a[0] + "," + a[1] + " Q" + (mx + nx) + "," + (my + ny) + " " + b[0] + "," + b[1], "marker-end": "url(#arrow-" + kind + ")" }),
          sv("text", { class: "edgelabel " + kind, x: mx + nx / 2, y: my + ny / 2, "text-anchor": "middle" }, label));
      };
      (node(S.selected).effective_blockers || []).forEach((b) => draw(b, "blocker"));
      (node(S.selected).dependents || []).forEach((d) => draw(d, "dependent"));
    }
    view.append(stage);
    if (S.fitPending) { S.fitPending = false; fitView(); } else applyFv();
  }

  function renderPage(view) {
    view.className = "page-mode";
    delete view.dataset.depth; delete view.dataset.auto;
    S.layout = null;
    const id = S.focus, n = node(id);
    const page = detailEl(id, true);
    const unc = n.uncleared_blockers || [];
    const PAD = 6;
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
      Object.keys(pos).forEach((cid) => { const c = cardEl({ id: cid, x: pos[cid].left, y: pos[cid].top, w, h: hh, hidden: 0 }, { noStar: true }); if (cid === id) c.classList.add("sel"); box.append(c); });
      const slotEl = page.querySelector(".md-slot");
      [h("h2", { class: "sec", style: "margin-left:0" }, "Chain of uncleared blockers (" + ch.count + (ch.count === 1 ? " node" : " nodes") + ", upstream on the left)"),
        h("div", { class: "chain" }, box), ch.truncated ? h("p", { class: "muted" }, "The chain is cut at 60 nodes.") : null].filter(Boolean).forEach((e) => slotEl.before(e));
    }
    view.append(page);
    view.scrollLeft = 0; view.scrollTop = 0;
  }

  function renderView() {
    const view = $("view");
    view.replaceChildren();
    const errs = (S.state.errors || []).length;
    const banners = [];
    if (errs) banners.push(h("div", { class: "banner" }, h("b", {}, errs + (errs === 1 ? " error" : " errors") + " in the roadmap. "),
      "What parsed is shown; statuses that cannot be derived read unknown. ", h("button", { onclick: () => { S.tab = "problems"; renderSidebar(); } }, "Show problems")));
    if (S.notice) banners.push(h("div", { class: "banner" }, S.notice));
    $("banners").replaceChildren(...banners);
    if (S.focus === null) { view.className = "page-mode"; view.append(h("p", { class: "pad muted" }, "No nodes yet. Node files go in roadmap/nodes/.")); return; }
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
    sb.append(h("span", {}, "↑↓←→ move · Enter focus · e editor · p pin · m map · f fit · / search · Esc"));
    if (S.bench) sb.append(h("span", {}, S.bench));
    sb.append(h("span", { title: "Time from navigation start to the first render of this page" }, S.firstRenderMs === null ? "" : "first render " + Math.round(S.firstRenderMs) + " ms"));
    sb.append(h("span", { title: "Live updates from /api/events" }, S.connected === null ? "" : S.connected ? "● live" : "○ reconnecting…"));
  }

  function renderAll() {
    document.body.classList.toggle("map", S.map);
    $("map").hidden = !S.map;
    renderSidebar();
    renderDrawer(); // before the view: it takes width, and the view's automatic depth and fit are computed from its width
    renderView(); // before the breadcrumb: the depth it shows is decided while the view is laid out
    renderCrumbs();
    renderStatusbar();
    if (S.map) renderMap();
    document.title = (S.focus && node(S.focus) ? node(S.focus).title + " — " : "") + "Freyja roadmap";
  }

  /* ---- the map */
  const SECTOR_TINTS = ["var(--sector-a)", "var(--sector-b)", "var(--sector-c)"];
  function setMap(on) {
    if (on === S.map) return;
    S.map = on;
    document.body.classList.toggle("map", on);
    if (on) { const t = performance.now(); renderMap(true); S.mapOpenMs = performance.now() - t; document.documentElement.dataset.mapOpenMs = S.mapOpenMs.toFixed(1); }
    else $("map").hidden = true;
    renderStatusbar();
  }
  function mapDims() { const box = $("map"); return [box.clientWidth || 1000, (box.clientHeight || 700) - $("map").querySelector(".maptools").offsetHeight]; }
  function mapKeyOf() { return [S.stamp, S.mapMode, S.showSuperseded ? 1 : 0].join("|"); }
  function mapFit() {
    const M = S.mapState && S.mapState.lay;
    if (!M) return;
    const [W, H] = mapDims(), b = M.bounds, bw = b.x1 - b.x0, bh = b.y1 - b.y0;
    $("map").dataset.fitdims = Math.round(W) + "x" + Math.round(H); // what this fit was computed against
    const k = clamp(Math.min(W / bw, H / bh) * 0.94, 0.02, 3);
    setMapT({ k, x: W / 2 - (b.x0 + bw / 2) * k, y: H / 2 - (b.y0 + bh / 2) * k });
    S.mapState.fitK = k;
  }
  function mapCentreOn(id) {
    const ms = S.mapState, n = ms.byId[id];
    if (!n) return;
    const [W, H] = mapDims();
    const k = clamp(Math.min(1, Math.max(ms.fitK * 2.5, 0.5)), ms.fitK, 8);
    setMapT({ k, x: W / 2 - n.x * k, y: H / 2 - n.y * k });
  }
  function ensureMapVisible(id) {
    const ms = S.mapState, n = ms && ms.byId[id];
    if (!n) return;
    const [W, H] = mapDims(), t = S.mv, sx = t.x + n.x * t.k, sy = t.y + n.y * t.k;
    if (sx < 30 || sx > W - 30 || sy < 30 || sy > H - 30) setMapT({ k: t.k, x: t.x + (W / 2 - sx), y: t.y + (H / 2 - sy) });
  }
  function setMapT(t) {
    const ms = S.mapState;
    const prevK = S.mv.k;
    S.mv = t;
    const world = $("mapworld");
    world.setAttribute("transform", "translate(" + t.x.toFixed(2) + "," + t.y.toFixed(2) + ") scale(" + t.k.toFixed(5) + ")");
    world.dataset.k = t.k.toFixed(5); world.dataset.tx = t.x.toFixed(2); world.dataset.ty = t.y.toFixed(2);
    if (!ms) return;
    if (t.k !== prevK || ms.dirtyScale) { ms.dirtyScale = false; mapRescale(); }
  }
  /** Markers, labels and annotations keep a constant size on screen: each is drawn at its place and scaled by 1/zoom about it. */
  function mapRescale() {
    const ms = S.mapState, k = S.mv.k, inv = 1 / k;
    const showLabels = k >= ms.labelZoom;
    $("map").dataset.labelzoom = ms.labelZoom.toFixed(4);
    for (const g of ms.markers) g.el.setAttribute("transform", "translate(" + g.x + "," + g.y + ") scale(" + inv.toFixed(5) + ")");
    for (const l of ms.labels) {
      l.el.classList.toggle("show", showLabels);
      if (!showLabels) continue;
      l.el.setAttribute("transform", l.t + " scale(" + inv.toFixed(5) + ")");
      const room = Math.floor((ms.lay.step * k - 22) / 6.2), n = clamp(room, 4, 40);
      if (l.chars !== n) { l.chars = n; l.el.textContent = truncateTitle(l.full, n); }
    }
    for (const s of ms.secLabels) { // a sector's title must fit inside the sector, so neighbours' titles never overlap: shorten it to the room it has, or hide it
      s.el.setAttribute("transform", s.t + " scale(" + inv.toFixed(5) + ")");
      const room = Math.floor(s.w * k / 6.6);
      s.el.classList.toggle("hide", room < 5);
      if (room >= 5 && s.chars !== room) { s.chars = room; s.el.textContent = truncateTitle(s.full, Math.min(40, room)); }
    }
    if (ms.here) ms.here.el.setAttribute("transform", "translate(" + ms.here.x + "," + ms.here.y + ") scale(" + inv.toFixed(5) + ")");
  }

  function buildMap() {
    const idx = S.index, M = mapLayout(idx, S.mapMode);
    const byId = {}; for (const n of M.nodes) byId[n.id] = n;
    const world = sv("g", { id: "mapworld" });
    const gSec = sv("g", { class: "sectors" }), gLink = sv("g", { class: "mlinks" }), gOver = sv("g", { class: "over" }), gMk = sv("g", { class: "markers" }), gLbl = sv("g", { class: "labels" }), gSecLbl = sv("g", { class: "seclabels" });
    const ms = { lay: M, byId, markers: [], labels: [], secLabels: [], linkEls: {}, mkEls: {}, over: gOver, labelZoom: labelZoom(M), here: null, fitK: 1, dirtyScale: true };
    // sectors: a faint background and a title for each first-layer branch
    M.sectors.forEach((q, i) => {
      const tint = SECTOR_TINTS[i % SECTOR_TINTS.length];
      let t;
      if (M.mode === "radial") {
        const R = M.reach, mid = (q.a0 + q.a1) / 2;
        gSec.append(sv("path", { class: "sector", "data-id": q.id, d: d3.arc()({ innerRadius: 0, outerRadius: R, startAngle: q.a0, endAngle: q.a1 }), style: "fill:" + tint }, sv("title", {}, q.title))); // the full title stays on hover
        const lr = R + 6, lx = lr * Math.sin(mid), ly = -lr * Math.cos(mid), deg = ((mid * 180 / Math.PI) % 360 + 360) % 360;
        const flip = deg > 90 && deg < 270; // along the tangent, and never upside down
        t = "translate(" + lx.toFixed(1) + "," + ly.toFixed(1) + ") rotate(" + (flip ? deg - 180 : deg).toFixed(1) + ")";
        gSecLbl.append(sv("text", { class: "sector-label", "data-id": q.id, "text-anchor": "middle", transform: t }, truncateTitle(q.label, 40)));
      } else {
        const y0 = M.bounds.y0, y1 = M.bounds.y1;
        gSec.append(sv("rect", { class: "sector", "data-id": q.id, x: q.x0, y: y0, width: q.x1 - q.x0, height: y1 - y0, style: "fill:" + tint }, sv("title", {}, q.title)));
        t = "translate(" + ((q.x0 + q.x1) / 2).toFixed(1) + "," + (y0 + 14).toFixed(1) + ")";
        gSecLbl.append(sv("text", { class: "sector-label", "data-id": q.id, "text-anchor": "middle", transform: t }, truncateTitle(q.label, 40)));
      }
      ms.secLabels.push({ el: gSecLbl.lastChild, t, full: q.label, w: M.mode === "radial" ? (M.reach + 6) * (q.a1 - q.a0) : q.x1 - q.x0, chars: -1 });
    });
    // links
    for (const l of M.links) {
      const a = byId[l.source], b = byId[l.target];
      const d = M.mode === "radial" ? d3.linkRadial().angle((n) => n.angle).radius((n) => n.r)({ source: a, target: b }) : d3.linkVertical().x((n) => n.x).y((n) => n.y)({ source: a, target: b });
      const p = sv("path", { class: "mlink", "data-to": l.target, d });
      ms.linkEls[l.target] = p;
      gLink.append(p);
    }
    // markers: a shape per status for leaves and stubs, a ring filled to the done fraction for interior nodes
    const frontier = new Set(S.state.frontier || []);
    for (const n of M.nodes) {
      const nd = idx.nodes[n.id], interior = (idx.children[n.id] || []).length > 0;
      const kind = interior ? "interior" : nd.kind === "stub" ? "stub" : "leaf";
      const shape = interior ? "ring" : markerShape(nd.status);
      const g = sv("g", { class: "mk" + (frontier.has(n.id) ? " frontier" : ""), "data-id": n.id, "data-kind": kind, "data-shape": shape, "data-depth": n.depth, "data-status": nd.status,
        "data-r": M.mode === "radial" ? n.r.toFixed(3) : null, "data-y": M.mode === "radial" ? null : n.y.toFixed(3), role: "img", "aria-label": nd.title + ", " + statusInfo(nd.status).label });
      g.append(sv("circle", { class: "hit", r: 10 }));
      if (interior) {
        const p = idx.progress[n.id], frac = p.total ? p.done / p.total : 0;
        g.append(sv("circle", { class: "ring" + (nd.status === "blocked" ? " blockedring" : ""), r: MAP_RING, "data-frac": frac.toFixed(4), style: "stroke:var(--c-" + nd.status + ")" }));
        const wedge = ringWedge(frac, MAP_RING - 1);
        if (wedge) g.append(sv("path", { class: "wedge", d: wedge }));
      } else {
        g.append(sv("path", { class: "shape" + (nd.kind === "stub" ? " stubshape" : ""), d: shapePath(shape, 5.5), style: "fill:var(--c-" + nd.status + ")" }));
      }
      ms.markers.push({ el: g, x: n.x.toFixed(2), y: n.y.toFixed(2) });
      ms.mkEls[n.id] = g;
      gMk.append(g);
      // the title, drawn along the ray (radial) or downwards (top-down) once the zoom lets neighbours' titles clear each other
      let t;
      if (M.mode === "radial") {
        const deg = n.angle * 180 / Math.PI, flip = deg > 180;
        t = "translate(" + n.x.toFixed(2) + "," + n.y.toFixed(2) + ") rotate(" + ((flip ? deg + 90 : deg - 90)).toFixed(1) + ")";
        const tx = sv("text", { class: "lbl", "data-id": n.id, "text-anchor": flip ? "end" : "start", x: flip ? -11 : 11, y: 4 }, "");
        ms.labels.push({ el: tx, t, full: shortOf(nd), chars: -1 });
        gLbl.append(tx);
      } else {
        t = "translate(" + n.x.toFixed(2) + "," + n.y.toFixed(2) + ") rotate(90)";
        const tx = sv("text", { class: "lbl", "data-id": n.id, x: 11, y: 4 }, "");
        ms.labels.push({ el: tx, t, full: shortOf(nd), chars: -1 });
        gLbl.append(tx);
      }
      ms.labels[ms.labels.length - 1].el.setAttribute("transform", t);
    }
    const here = sv("g", { class: "here" }, sv("circle", { r: 15, class: "hererings" }), sv("text", { class: "heretext", y: -22, "text-anchor": "middle" }, "you are here"));
    ms.here = { el: here, x: "0", y: "0" };
    world.append(gSec, gLink, gOver, gMk, gLbl, gSecLbl, here);
    return { ms, world };
  }

  function updateMapPins() {
    const ms = S.mapState;
    if (!ms) return;
    for (const [id, g] of Object.entries(ms.mkEls)) {
      const has = g.querySelector(".pinstar"), want = isPinned(id);
      if (want && !has) g.append(sv("path", { class: "pinstar", d: shapePathStar(5), transform: "translate(8,-8)" }));
      else if (!want && has) has.remove();
    }
  }
  function shapePathStar(r) {
    const pts = [];
    for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.42 : r; pts.push((rr * Math.cos(a)).toFixed(2) + "," + (rr * Math.sin(a)).toFixed(2)); }
    return "M" + pts.join("L") + "Z";
  }
  function updateMapSelection() {
    const ms = S.mapState;
    if (!ms) return;
    for (const g of ms.markers) g.el.classList.toggle("sel", g.el.dataset.id === S.selected);
    const f = ms.byId[S.focus];
    if (f) { ms.here.x = f.x.toFixed(2); ms.here.y = f.y.toFixed(2); ms.here.el.setAttribute("transform", "translate(" + ms.here.x + "," + ms.here.y + ") scale(" + (1 / S.mv.k).toFixed(5) + ")"); }
  }

  function renderMap(opening) {
    const box = $("map"), svg = $("mapsvg");
    box.hidden = !S.map;
    if (!S.map) return;
    const key = mapKeyOf();
    let built = false;
    if (!S.mapBuilt || S.mapBuilt !== key) {
      const { ms, world } = buildMap();
      S.mapState = ms; S.mapBuilt = key;
      svg.replaceChildren(world);
      built = true;
      box.dataset.step = ms.lay.step.toFixed(3);
    }
    box.dataset.mode = S.mapMode;
    $("map-layout").textContent = S.mapMode === "radial" ? "Top-down" : "Radial";
    $("map-frontier").setAttribute("aria-pressed", String(S.mapFrontier));
    svg.classList.toggle("frontier-only", S.mapFrontier);
    updateMapPins(); // pins, the selection and the focus mark are cheap, so they follow every render; the layout is rebuilt only when it changes
    if (opening || built) {
      mapFit();
      if (S.focus !== S.index.rootId) mapCentreOn(S.focus);
    }
    updateMapSelection();
  }

  function hoverOn(id, ev) {
    const ms = S.mapState, idx = S.index, n = idx.nodes[id];
    hoverOff();
    const p = idx.progress[id], interior = isInterior(id);
    const tip = $("tip");
    tip.replaceChildren(h("b", {}, n.title), h("div", { class: "mono" }, id), h("div", {}, statusInfo(n.status).label + (n.kind === "stub" ? " (stub)" : "") + (interior ? " · " + p.done + "/" + p.total + " done" : "")));
    tip.style.display = "block";
    tip.style.left = Math.min(window.innerWidth - 380, (ev.clientX || 0) + 14) + "px";
    tip.style.top = Math.min(window.innerHeight - 60, (ev.clientY || 0) + 16) + "px";
    for (let c = id; c && idx.parent[c]; c = idx.parent[c]) if (ms.linkEls[c]) ms.linkEls[c].classList.add("onpath");
    const A = ms.byId[id];
    const connect = (other, kind) => {
      const B = ms.byId[other];
      if (!B || other === id) return;
      const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2, cx = S.mapMode === "radial" ? mx * 0.55 : mx, cy = S.mapMode === "radial" ? my * 0.55 : my + 40;
      ms.over.append(sv("path", { class: "hoverlink " + kind, d: "M" + A.x + "," + A.y + " Q" + cx + "," + cy + " " + B.x + "," + B.y, "stroke-dasharray": kind === "blocker" ? "7 4" : "2 4" }));
    };
    (n.effective_blockers || []).forEach((b) => connect(b, "blocker"));
    (n.dependents || []).forEach((d) => connect(d, "dependent"));
  }
  function hoverOff() {
    const ms = S.mapState;
    $("tip").style.display = "none";
    if (!ms) return;
    ms.over.replaceChildren();
    for (const p of document.querySelectorAll("#mapsvg path.mlink.onpath")) p.classList.remove("onpath");
  }

  (function wireMap() {
    const svg = $("mapsvg");
    S.mvp = viewport(svg, {
      enabled: () => S.map && !!S.mapState,
      get: () => S.mv, set: setMapT,
      minK: () => (S.mapState ? S.mapState.fitK * 0.5 : 0.01), maxK: () => 8,
    });
    svg.addEventListener("pointerover", (ev) => { const g = ev.target.closest && ev.target.closest("g.mk"); if (g && !(S.mvp && S.mvp.moved)) hoverOn(g.dataset.id, ev); });
    svg.addEventListener("pointermove", (ev) => { const g = ev.target.closest && ev.target.closest("g.mk"); if (g) { $("tip").style.left = Math.min(window.innerWidth - 380, ev.clientX + 14) + "px"; $("tip").style.top = Math.min(window.innerHeight - 60, ev.clientY + 16) + "px"; } });
    svg.addEventListener("pointerout", (ev) => {
      const g = ev.target.closest && ev.target.closest("g.mk");
      if (!g) return;
      const to = ev.relatedTarget;
      if (to && to.closest && to.closest("g.mk") === g) return;
      hoverOff();
    });
    svg.addEventListener("click", (ev) => {
      if (S.mvp && S.mvp.moved) return;
      const g = ev.target.closest && ev.target.closest("g.mk");
      if (g) go(g.dataset.id);
    });
    $("map-close").addEventListener("click", () => setMap(false));
    $("map-fit").addEventListener("click", () => mapFit());
    $("map-layout").addEventListener("click", () => { S.mapMode = S.mapMode === "radial" ? "top" : "radial"; pref("maplayout", S.mapMode); renderMap(true); });
    $("map-frontier").addEventListener("click", () => { S.mapFrontier = !S.mapFrontier; renderMap(); });
  })();

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
    if (S.focus !== null && !idx.nodes[S.focus]) S.focus = idx.rootId; // the focused node is gone (renamed or deleted): fall back to the root
    if (S.focus === null) S.focus = idx.rootId;
    if (S.selected === null || !idx.nodes[S.selected]) S.selected = S.focus;
  }

  function applyState(state, first) {
    S.state = state;
    S.index = buildIndex(state, S.showSuperseded);
    S.nodeCache.clear();
    S.stamp++;
    if (first) {
      const want = routeParse(location.hash);
      S.focus = want && S.index.nodes[want] ? want : S.index.rootId;
      S.selected = S.focus;
      S.fitPending = true;
      if (want && !S.index.nodes[want]) S.notice = "No node " + want + " in the roadmap; showing the root.";
    }
    ensureValid();
    const side = $("side-body"), keepSide = side.scrollTop;
    renderAll();
    if (!first) side.scrollTop = keepSide;
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
    else if (k === "p") { if (S.selected) togglePin(S.selected); }
    else if (k === "f") fitView();
    else if (k === "/") { ev.preventDefault(); $("search").focus(); $("search").select(); }
    else if (k === "m") setMap(!S.map);
    else if (k === "Escape") { if (S.map) setMap(false); else if ($("search").value || S.chips.size) { S.chips.clear(); clearSearch(); } }
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

  S.vp = viewport($("view"), {
    enabled: () => $("view").classList.contains("tree-mode") && !S.map && !!stageEl(),
    get: () => S.fv, set: (t) => { S.fv = t; applyFv(); },
    minK: () => 0.12, maxK: () => 3,
  });

  /** The view's width changed (window or sidebar): with an automatic depth, a different depth may now fit. */
  function onViewResize() {
    if (!S.state || S.map || S.focus === null || !isInterior(S.focus)) return;
    if (S.depthOverride === null && effectiveDepth() !== S.shownDepth) { S.fitPending = true; renderView(); renderCrumbs(); }
  }
  let resizeTimer = 0;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (S.map) { mapFit(); if (S.focus !== S.index.rootId) mapCentreOn(S.focus); } else onViewResize(); }, 30); });

  (function sidebarResizer() {
    const bar = $("resizer"), app = $("app");
    const set = (px) => { const w = Math.max(220, Math.min(window.innerWidth * 0.7, px)); app.style.setProperty("--side-w", w + "px"); return w; };
    const saved = parseInt(pref("sidew") || "", 10);
    if (saved) set(saved);
    let drag = false;
    bar.addEventListener("pointerdown", (ev) => { drag = true; bar.classList.add("drag"); bar.setPointerCapture(ev.pointerId); });
    bar.addEventListener("pointermove", (ev) => { if (drag) set(ev.clientX); });
    const end = () => { if (!drag) return; drag = false; bar.classList.remove("drag"); pref("sidew", Math.round($("sidebar").getBoundingClientRect().width)); onViewResize(); };
    bar.addEventListener("pointerup", end);
    bar.addEventListener("pointercancel", end);
    bar.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault(); ev.stopPropagation();
      const w = set($("sidebar").getBoundingClientRect().width + (ev.key === "ArrowRight" ? 24 : -24));
      pref("sidew", Math.round(w)); onViewResize();
    });
  })();

  /* ---- start */
  (async function boot() {
    const q = new URLSearchParams(location.search);
    if (q.get("theme") === "light" || q.get("theme") === "dark") document.documentElement.dataset.theme = q.get("theme"); // for captures; otherwise the system setting decides
    S.showSuperseded = pref("superseded") === "1";
    S.workCollapsed = pref("workcollapsed") === "1";
    S.mapMode = q.get("layout") === "top" || (!q.get("layout") && pref("maplayout") === "top") ? "top" : "radial";
    S.tab = TABS.includes(pref("tab")) ? pref("tab") : "outline";
    try {
      const [state] = await Promise.all([fetchState(), loadPins()]);
      applyState(state, true);
      // capture parameters: they only seed the initial view (selection, tab, search text, depth, map), so a screenshot can show it
      if (q.has("select") && S.index.nodes[q.get("select")]) S.selected = q.get("select");
      if (TABS.includes(q.get("tab"))) S.tab = q.get("tab");
      if (q.get("depth")) S.depthOverride = clamp(parseInt(q.get("depth"), 10) || 3, 1, MAX_DEPTH);
      if (q.get("frontier") === "1") S.mapFrontier = true;
      if (q.get("q")) { $("search").value = q.get("q"); renderCandidates(); }
      if (q.get("map") === "1") { S.map = true; document.body.classList.add("map"); }
      const t = performance.now();
      renderAll();
      if (S.map) { S.mapOpenMs = performance.now() - t; document.documentElement.dataset.mapOpenMs = S.mapOpenMs.toFixed(1); }
      if (S.map && parseFloat(q.get("mapk")) > 0) { // capture parameter: open the map zoomed to this factor, centred on the focus
        const n = S.mapState.byId[S.focus], k = parseFloat(q.get("mapk")), [W, H] = mapDims();
        setMapT({ k, x: W / 2 - n.x * k, y: H / 2 - n.y * k });
      }
    } catch (e) {
      document.body.prepend(h("div", { class: "banner" }, "Could not load /api/state: " + e.message + ". Is `fy roadmap serve` still running?"));
      return;
    }
    requestAnimationFrame(() => {
      S.firstRenderMs = performance.now();
      document.documentElement.dataset.firstRenderMs = String(Math.round(S.firstRenderMs));
      document.documentElement.dataset.scriptRenderMs = String(Math.round(S.firstRenderMs - T0));
      document.documentElement.dataset.ready = "1";
      if (q.get("bench")) { // capture parameter: time N full re-renders (a selection change redraws everything) and show the average in the status bar
        const kids = S.index.children[S.focus] || [], t = performance.now();
        for (let i = 0; i < +q.get("bench"); i++) { S.selected = kids[i % Math.max(1, Math.min(2, kids.length))] || S.focus; renderAll(); }
        S.bench = "re-render " + ((performance.now() - t) / +q.get("bench")).toFixed(1) + " ms avg of " + q.get("bench");
      }
      renderStatusbar();
    });
    if (!q.has("nolive")) connectEvents(); // ?nolive: no event stream (a headless capture never goes idle with one open)
  })();
})();
