# roadmap/

The Freyja v1 roadmap: a machine-checked graph of small, verifiable goals.

This is the cold-start document for anyone picking the roadmap up with no prior context (Joe, a Claude chat, Claude Code). Read it fully before authoring or changing anything here.

Written 2026-10-17, at the end of the tooling phase. Briefs 1 to 3 are built and accepted (brief 3 added short labels, the tag vocabulary and colour-by-tag; see memo16). Authoring the real roadmap began the same day: the committed files in `roadmap/nodes/` are the record of what exists, and `roadmap/STATUS.md` is the generated summary.

**Reading order for a fresh session:** this file, then `docs/OVERVIEW.md` for project context, `CONVENTIONS.md` sections 2, 3 and 9, `docs/STATE.md`, and the newest memo in `docs/memos/` (memo16 at the time of writing).

## 1. Purpose

The roadmap exists so that:

1. The near-term work is fleshed out in enough detail that the next item is obvious.
2. Every unit of work is hours to days in size and has a completion criterion a machine can evaluate.
3. Logs, memos and commit messages cite node ids, so progress is compared to the roadmap at fine scale rather than as a coarse multi-month goal.
4. When a blocker clears, GitHub opens an issue for each node that just became workable.

It is not a schedule: no dates, no percent-complete. The useful measures are the frontier (what is workable now), leaves closed per week, and how long active leaves have been open.

## 2. The model

Every node is one Markdown file. Two relations connect nodes:

- **Tree (`parent`):** "is part of." Exactly one root; every other node has exactly one parent. This is decomposition. Interior status rolls up from children.
- **Blocking (`blocked_by`):** "cannot start until." May cross branches; must be acyclic. A node also inherits the blockers of all its ancestors. Blocking on an interior node means blocking on all its leaves and stubs.

### Node kinds (determined by structure)

| Kind | Has children | Carries | Meaning |
|---|---|---|---|
| Interior | yes | no `done_when`, no estimate | Status is derived from its children. |
| Leaf | no | `done_when` and `estimate_days` | A unit of work, sized to finish in hours to about 3 days. |
| Stub | no | neither; `stub: true` | A placeholder that has not been decomposed yet. |

Expanding a stub means adding children (it becomes interior) or giving it `done_when` and an estimate (it becomes a leaf). Remove `stub: true` in the same commit.

### Titles are end states

Every title states a verifiable end state ("Elbow actuator selected and decision recorded"), never an area ("Elbow"). An area never completes.

### Naming

"Gate" already means a blocking check elsewhere in this repo, so a node's completion criterion is called **`done_when`**. A `done_when` can reference a check.

### Who sets what

Status is **derived on every evaluation and never stored in a node file**. Humans set only: the `done_when` criterion itself, `blocked_by`, `active`, and `signed_off`.

## 3. Status derivation

A blocker is cleared when its node is `done`.

| Kind | Rule, in order |
|---|---|
| Leaf | `done` if `done_when` passes; else `blocked` if any effective blocker is uncleared; else `active` if `active: true`; else `ready`. |
| Stub | `blocked` if any effective blocker is uncleared; else `expandable`. |
| Interior | `done` if every non-superseded child is done; else `blocked` if its own effective blockers are uncleared; else `in_progress` if any descendant is done or active; else `not_started`. |
| Retired | `superseded`: excluded from parent derivation and all counts. |

`stale` is reserved in the state schema and never emitted yet. A done node going stale when an upstream input changes is a planned v2 feature (inputs would be hashed in result records).

**Frontier** = every `ready` leaf plus every `expandable` stub.

A leaf whose criterion passes while a blocker is uncleared is `done` with a "done out of order" warning (also applied to interior nodes).

### `done_when` types

The library evaluates these from files already in the repo. It never runs a simulation, a test suite or a check; a sim writes a result record, and the criterion reads it.

| Type | Fields | Passes when |
|---|---|---|
| `artifact` | `path`, optional `schema` | The file exists, is non-empty, and validates against the schema if one is given. |
| `decision` | `record` (a path under `decisions/`) | The record exists and its status is accepted. |
| `check` | `check` (id of a check under `checks/`) | The recorded result in `docs/STATE.md` is a pass. A WAIVED check is not a pass. |
| `metric` | `record` (JSON path), `pointer` (RFC 6901), `op` (`<`, `<=`, `>`, `>=`, `==`), `value`, `units` | The comparison holds. The measured value is reported either way. |
| `manual` | none | `signed_off: true`. Only Joe sets this. |

Each evaluation yields `pass`, `fail`, `awaiting` or `unknown`:

- `awaiting`: the evidence has not been produced yet (record absent but its directory exists; check "not run"). No warning. This is the normal state of unfinished work.
- `unknown`: the evidence looks broken (unparseable file, pointer that does not resolve, missing directory, unlisted check id). This raises a `criterion-unknown` warning.
- Neither counts as a pass.

## 4. The node file

`roadmap/nodes/<id>.md`: YAML front matter, then free Markdown that machines ignore (context, rationale, links to briefs, memos and decisions).

```markdown
---
schema: roadmap-node/2
id: rm.elbow-actuator-selected
title: Elbow actuator selected and decision recorded
parent: rm.upper-arm-v1-tested
blocked_by: [rm.upper-arm-loads-final]
estimate_days: 2
tags: [arm, actuation]
done_when:
  type: decision
  record: decisions/0012-elbow-actuator.md
active: false
---
Context and links. Free prose.
```

| Field | Rule |
|---|---|
| `schema` | Required. `roadmap-node/2` for new files; `roadmap-node/1` files still load. The generated state file is `roadmap-state/3`. Schemas are in `docs/schemas/`. |
| `id` | Required. Equals the filename stem. Form `rm.<slug>` (lowercase letters, digits, hyphens). Permanent. |
| `title` | Required. An end state. |
| `short` | Optional. At most 16 characters. Used for map sector labels, map node labels and breadcrumbs. |
| `parent` | Required. `null` only on the root. |
| `blocked_by` | List of ids. Default empty. |
| `stub` | Bool. Default false. |
| `estimate_days` | Required on leaves; forbidden on interior nodes and stubs. Warning above 3.0. |
| `tags` | List. Brief 3 adds a controlled vocabulary (see section 7). |
| `done_when` | Required on leaves; forbidden otherwise. |
| `active` | Bool, default false. Human-set; marks work in progress. |
| `signed_off` | Only meaningful with `done_when.type: manual`. Only Joe sets it. |
| `superseded_by` | An id. Marks a retired node. Nodes are never deleted. |

Unknown fields are a schema error. Schemas live in `docs/schemas/`.

### What fails validation (blocks the commit)

Schema violations; filename not matching id; zero or several roots; unresolved parents; parent cycles; unresolved `blocked_by`; a node blocked by itself, an ancestor or a descendant; blocked by a superseded node; blocking cycles; interior nodes with `stub`, `done_when` or `estimate_days`; childless non-stubs missing `done_when` or `estimate_days`; stubs carrying them; bad `superseded_by`.

**Authoring gotchas:**

- A childless node that is not marked `stub: true` must have `done_when` and `estimate_days`.
- A node with children must not be marked `stub: true`.
- Adding the first child to a stub means removing `stub: true` in the same commit.

Warnings (generation proceeds): estimate above the cap, done out of order, `active` on a done leaf, `signed_off` on a non-manual criterion, `criterion-unknown`.

## 5. Tooling

Run from the repo root as `python tools/fy roadmap <command>`. Every command takes `--root DIR` (default: repo root); data commands take `--json`.

| Command | Does |
|---|---|
| `validate` | Prints errors and warnings; exits nonzero on errors. |
| `build` | Validates, then writes `roadmap/state.json` and `roadmap/STATUS.md`. |
| `show <query>` | Breadcrumb, fields, status with reason, criterion evaluation, children, uncleared blockers, dependents, references. |
| `frontier` | The workable list, with criteria and estimates. |
| `refs <query>` | Where the id is cited (logs, memos, notebook, commit messages). |
| `open <query>` | Opens the node file in an editor (`FREYJA_EDITOR`, then `VISUAL`/`EDITOR`, then `code`, then the OS opener). |
| `serve [--port 8765] [--focus QUERY]` | The local viewer (section 6). |
| `pin`, `unpin`, `pins` | Personal bookmarks. |
| `fixture --size N --out DIR [--first-layer N]` | Writes a seeded synthetic roadmap for testing the tooling and viewer. |
| `install-hooks` | Points this clone's `core.hooksPath` at `.githooks/`. Run once per clone. |

`<query>` resolves as: exact id, then `rm.` plus the query, then a unique case-insensitive substring of an id or title, else up to 10 candidates.

**Generated files** (`roadmap/state.json`, `roadmap/STATUS.md`) are written only by tooling. The pre-commit hook rebuilds and stages them into the same commit, so no bot commits ever land on main, and it blocks any commit that would leave the roadmap invalid. Their banners carry the inputs hash only. Never hand-edit them.

**Notifications:** `.github/workflows/roadmap.yml` runs on push to the default branch. It validates, builds fresh states at the before and after commits (it does not trust the committed `state.json`), and opens one issue per newly ready leaf and per newly expandable stub (label `roadmap`, skipped if an open issue for that id exists). A committed `state.json` that differs from a fresh build raises a warning annotation, not a failure. Expect a burst of issues on the first push of real nodes; that is accepted.

## 6. The viewer

`python tools/fy roadmap serve` opens a local web app on `127.0.0.1:8765` (a second serve on the same port fails). It is read-only toward the roadmap: the only file it writes is `roadmap/.pins.json` (gitignored, per-clone, personal). It refreshes live when node files or the evidence files they read change.

**Sidebar.** Search box (also `tag:<namespace>:<value>` and `tag:<free-tag>`; a bare `tag:region` matches nothing). A Working panel with **Active** (every leaf with `active: true`) and **Pinned**. Tabs: **Outline** (collapsible indented tree; collapsed except the path to the current focus; status filter chips; done/total fractions; star on pinned rows), **Frontier**, **Problems**.

**Main view, focus mode.** Cards for the focused node and its descendants, with a progress bar on interior cards. A node's childless children stack in a vertical column; only interior children spread horizontally. Children are ordered active, ready, expandable, blocked, in_progress, not_started, done. More than 8 children collapse into a "+k more" card. Default depth fits the window; +/- overrides it. Drag pans, wheel zooms, `f` fits. The breadcrumb collapses the middle beyond four ancestors. A right-hand drawer shows the selected node (Open in editor, Copy id, Pin, Focus here). Leaves and stubs get a full single-node page: criterion and evaluation, rendered body, blocker chain, dependents, references.

**Main view, map mode (`m`).** The whole tree as a radial layout, root at the centre, one ring per depth, one faint coloured sector per first-layer branch labelled with its title (its `short` after brief 3). Markers use shape plus colour for status; interior nodes are rings filled to their done fraction; pinned nodes carry a star; the current focus is marked "you are here". Hovering a node highlights its path to the root and draws its blockers and dependents as dashed lines (blocking edges are drawn only on hover, never all at once). Toolbar: top-down layout toggle, frontier-only toggle (dims everything that is not ready or expandable), Fit, and after brief 3 a "Colour by" control (Status, Region, Phase) with a clickable legend. Clicking a node leaves the map and focuses it.

**Keys:** arrows move (up parent, down first child, left/right siblings), Enter refocuses, `e` opens in editor, `p` pins or unpins, `m` toggles the map, `f` fits, `/` searches, Esc leaves the map or clears search. Routing is `#/node/<id>`, so back and forward work.

## 7. How v1 is structured

### The root (agreed)

```markdown
---
schema: roadmap-node/2
id: rm.freyja-v1
title: Freyja v1 stands, balances and walks 10 m indoors untethered at 0.5 m/s
short: Freyja v1
parent: null
---
Mission: a biomimetic synthetic lifeform, built over decades; v1 is the first
version that stands, balances and walks on its own.

Acceptance: the final leaf of Trials, run against a protocol decision record
written before the attempt. Power and compute are onboard.

Scope rule: work belongs in v1 only if the acceptance test needs it.
Hardware rule: every v1 interface is final (mass, power, harness, mounts), so
v2 gains such as speed or spine-assisted gait are control work, not redesign.
Modules the acceptance test does not need may be mass- and interface-correct
dummies. Spine actuation in gait may move to v1.5 if it costs too much.
```

Candidate acceptance test (numbers to be fixed in a protocol decision record before any attempt, so the criterion cannot be tuned to what the robot happens to manage): released from a support stand already standing; holds quiet stance unsupported at least 60 s; recovers from a moderate push without falling (stepping allowed); walks 10 m straight on flat indoor floor at an average of at least 0.5 m/s following an operator velocity command, no fall; slack safety harness allowed, load-bearing support not; onboard battery and onboard compute (Jetson-class) for the whole trial. Getting up from the floor and higher speed are v2.

**Versioning:** the root is v1, not the lifetime goal. Later versions get their own roadmap, with the previous version as a low-level leaf. Ids carry the version (`rm.freyja-v1`, `rm.v1-...`) so v2 ids never collide. Changing which node is root later is one `parent` edit.

### The eight sectors (first layer; working drafts)

Each is a node titled as an end state with a short label. The tree carries one axis, systems (organ-system names). Body region and phase are carried as tags instead, so the map can be recoloured by them.

| Short | Id | End-state title |
|---|---|---|
| Skeletal | `rm.v1-skeletal` | v1 skeleton fabricated in final form, every link and joint verified against its load envelope. |
| Muscular | `rm.v1-muscular` | Every v1 actuator and transmission, spine included, installed and bench-qualified to its envelope. |
| Nervous | `rm.v1-nervous` | Every v1 sensor, harness and joint controller installed and passing its bench checks. |
| Metabolic | `rm.v1-metabolic` | Onboard battery, power distribution and cooling sustain the acceptance trial with margin. |
| Mind | `rm.v1-mind` | Onboard control stack (state estimation, balance, gait) runs on the Jetson and passes the acceptance protocol in simulation. |
| Ariadne | `rm.v1-ariadne` | Every v1 part traces from the anthropometry sheet through simulated loads to a validated CAD model. |
| Workshop | `rm.v1-workshop` | Every v1 part can be made in-house or sourced, with each in-house process qualified. |
| Trials | `rm.v1-trials` | Integration ladder complete: joint, limb, lower-body and whole-body trials pass, ending in the acceptance protocol. |

Why this axis: every sector is a completable end state; most blocking edges stay inside a sector, so a dashed edge crossing sectors on hover means something real; the sectors are stable for years. **Trials** is the right side of the systems-engineering V: its milestones are blocked by outputs from every other sector, so dense cross-sector edges into Trials are intended. **Mind** ends at "passes in simulation on the target compute"; the sim-to-real step belongs to Trials.

A phase-based first layer (sim, design, fab, bench) was rejected because no phase ever completes and every subsystem passes through every phase. A discipline-based layer was rejected because a working joint is mechanical, electrical and firmware at once. A body-segment layer was rejected as primary because actuators, cables, power, electronics and control belong to no single segment.

### Tags

Namespaced tags (`namespace:value`) are checked against `roadmap/tags.yaml`; an unknown namespace or value is an error naming the node and tag. Free tags (no colon) pass unchecked. A node should carry at most one value per namespace (two is a warning). Superseded nodes are tag-checked too. Initial namespaces: `region` (head, neck, torso, spine, pelvis, arm, hand, leg, foot, whole-body) and `phase` (spec, sim, design, fab, bench, integrate). A part designed once and mirrored carries the bilateral value; a free tag such as `left` or `right`, which is never checked, marks the rare asymmetric item. Joe owns the values.

### Decisions (confirmed by Joe, 2026-10-17 to 18)

- **Upper-body hardware in v1.** As proposed: actuated shoulders and elbows for arm swing; hands as mass dummies on final interfaces; the head as a mount with harness routing but no vision.
- **Cognitive architecture** stays outside this tree and runs as its own track with its own roadmap later.
- **Torso.** v1 has one 3-DOF joint at the lumbosacral joint, unlocked and actuated in gait; thoracic and cervical are rigid. v2 aims at a more human gait with more spinal joints. If lumbosacral actuation becomes a sidetrack (`rm.v1-lsj-concept` refutes the abdomen fit), its branch is re-parented to a later version.
- **Near-term branches**, decomposed to leaf level first: Ariadne (nearest), Muscular, Skeletal, Workshop.
- **Sizing scope.** Under the hardware rule, actuators and structure are sized for the full design task set (walking at 1.4 to 1.6 m/s, sit-to-stand, stair ascent and descent), although the acceptance test needs only slow walking. Read the scope rule as: work belongs in v1 if the acceptance test needs it or a final interface needs it. The root's scope rule was reworded to match in batch 4.
- **Frozen decisions.** None (Joe, 2026-10-18). No decision records existed when authoring began, apart from adr-0001 (toe joint, proposed). Earlier work, such as the hip modules and the knee concept, is input, not commitment: each decision enters as a leaf whose `done_when` is its record, and is settled when that record is accepted.
- **Sector titles** remain working drafts.

### Authoring conventions (batches 1 to 5)

- **Sector boundary.** Ariadne holds the pipeline and the trace: the characterization file and requirement records that go into a part, the validation record that comes out, and the benchmark that checks predictions against the built part. The physical sectors hold design, build and component qualification; Trials starts at the joint rung. The segment is the unit of design: Skeletal holds a segment's structure (links, frames, connectors, bearings, the mounts its actuators bolt to, and any housing that is also the link); Muscular holds actuator modules with their own housings; Nervous holds drivers, encoders and harness; Workshop holds in-house processes and their qualification, metrology and sourcing. Sectors are joined by blocking edges, never by the tree.
- **Loop first.** Detailed design of any part other than the upper arm is blocked by `rm.v1-upper-arm-validated`, so the pipeline is proven on one part before the rest go through it. Fabrication of any other part is also blocked by `rm.v1-upper-arm-benchmark`, so no other part is cut before the loop's predictions have been checked against a built one. Both edges go on the node that does the work: a stub that mixes design and fabrication gets them on the right child when it is expanded.
- **Segment wiring.** Each segment is wired as the upper arm is: its design leaf waits on the segment's characterization and requirement records in Ariadne, and Ariadne's validation of the segment waits on the design leaf. Never block a physical-sector node on `rm.v1-other-part-traces` as a whole: its validation children are blocked by design leaves, which closes a cycle.
- **Process qualification.** No functional part is made with a process before that process is qualified against a protocol recorded before its first test. Each fabrication node carries the qualification of the process it uses (`rm.v1-dmc2-qualified` for machined parts), wired when the node is created or its stub is expanded. Rigs and fixtures are exempt.
- **Ids** are `rm.v1-<slug>` with no sector prefix, since re-parenting is a one-line edit and the id is permanent.
- **Decision records** get numbers in node-creation order; the next free number is one above the highest `decisions/NNNN` referenced in `roadmap/nodes/`. Edit a leaf's `done_when` path if records are written in a different order.
- **Manual criteria** are used where the evaluator cannot read the evidence: git tags, sheet edits, study work with no record format, bench measurements until a bench record format exists, and CAD work until Stage 3 defines part sidecars. Joe signs them off.
- **Tags.** Region values are bilateral (`arm`, `hand`, `leg`, `foot`), so a part designed once and mirrored carries one. Free tags `stage2` and `stage3` mark Ariadne stage work.
- **Batches.** Each batch is reviewed as two tables (interior nodes and stubs; leaves) plus a table of edits to existing files, before any file is written. It is then delivered as a flat zip named `roadmap-batchN-<sector>.zip` that includes the sector file rewritten without `stub: true`. Every batch is checked against the validator's structural rules before delivery; `fy roadmap validate` is the real test. A batch that edits files from an earlier batch is extracted only after the earlier batch is committed, and a batch committed in parts is staged in dependency order (section 4).
- **Titles carry the question, not the answer.** A title, id or decision-record filename names what is being decided ("Hip actuation architecture recorded"), never the chosen solution; the answer lives in the record (one home per quantity). Solution-specific subtrees are blocked by the decision that chose them. When a decision is reversed, its record becomes `superseded-by` the new one, the leaf pointing at it evaluates `fail` and reopens, everything blocked by it blocks again, and the solution subtree is retired with `superseded_by`. Done nodes downstream do not reopen; that is the reserved `stale` status, not yet built.
- **Rules and the mill.** Design waits on `rm.v1-provisional-design-rules`; fabrication waits on `rm.v1-design-rules` (the rules confirmed against the qualified mill) and `rm.v1-dmc2-qualified`. The confirmed record amends the provisional one and never supersedes it. Every bench-qualified actuator waits on `rm.v1-actuator-bench` and `rm.v1-dmc2-qualified`, and every one except the elbow, which belongs to the benchmark part, on `rm.v1-upper-arm-validated`.
- **Zips and the apply script.** Every batch or patch is delivered as `roadmap-NN-<name>.zip` (NN one above the last delivered), holding top-level `rm.*.md` files, a one-line `_commit.txt` and, when the README changes, `_readme-additions.md` with whole bullets for this subsection. `apply-roadmap-zips.ps1` applies pending zips from Downloads in number order, one validated commit each, tagged `[roadmap-zip NN]` so a second run skips them.
- **Actuators lead.** The lower-limb actuators under selection set the electrical architecture, not the reverse. The power and comms architecture records wait on the hip and knee architecture records, and no actuator-selection leaf waits on them; a selection is checked against the architecture when it is made, and a joint that wants a different voltage gets local conversion.
- **Amend or supersede.** A record that later work only refines (the sensor set, the power budget, the provisional design rules) is amended, so its leaf stays passed. A record whose change invalidates what was built on it (the hip architecture, the bus voltage) is superseded, which reopens its leaf and blocks everything that waits on it.
- **Trial course.** Acceptance is an out-and-back along a ceiling rail with a turn at the far end, not a single straight 10 m, because the available run is shorter; the protocol record (0033) fixes the leg lengths and how the walked distance is counted against the root. That record supersedes the candidate acceptance test in section 7.
- **Stage 3 split.** Stage 3a builds the system model (`thread/`: records, stamps, generated dossiers) under `rm.v1-ariadne-system-model`; Stage 3b builds the CAD bridge that writes into it, so `rm.v1-bridge-tooling` waits on `rm.v1-thread-store` and the 3b brief on `rm.v1-thread-core`. The system model is Ariadne-track work: it is the product's data, not repo tooling.
- **Region tags.** Bilateral work (designed once, mirrored) carries `arm`, `hand`, `leg` or `foot`. A joint takes the region where its actuators sit, else its distal segment: the hip is `pelvis` (its modules sit there), the knee `leg`, the ankle and toe `foot`, the elbow and shoulder `arm`. Body-wide methods, architecture records, the sim and control stack and the whole-body trials carry `whole-body`. The Workshop, test fixtures and repo tooling (roadmap, thread, bridge) carry no region tag.
- **Falls.** Simulation ranks falls but cannot give their magnitudes, so fall load cases rest on independent sources. `rm.v1-fall-intent` decides first whether v1 is designed to touch the ground at all; the rest of `rm.v1-ariadne-fall-loads`, `rm.v1-thread-sources` and `rm.v1-drop-test` exist only if it says yes.
- **Falls.** Simulation ranks falls but cannot give their magnitudes, so fall load cases rest on independent sources. `rm.v1-fall-intent` sets the protocol (nothing but the feet touch the floor in v1 trials) and the rule that each segment carries its fall case or reserves the mass and volume for it; `rm.v1-fall-design-basis` sets the cases, factors and reservations once the literature bracket (`rm.v1-fall-sources`) exists.

## 8. How nodes are decomposed

- **Rolling-wave.** Near-term branches go to leaf level; far branches stay as stubs and are expanded when they approach the frontier (for example, when all but one of a stub's blockers are done). A fine breakdown of work whose inputs are not yet known is fiction.
- **A leaf is ready to write when** you can state its `done_when` and it fits about 3 days (cap 3.0). If you cannot write the criterion, the node is not a leaf: split it, or add a decision-spike leaf whose `done_when` is a decision record.
- **If a leaf runs past its estimate, split it** when you notice rather than leaving it active.
- **Thresholds are authored before the work.** Metric thresholds and test assertions are written by Joe, or in a brief, before work starts, never by whoever does the work. Otherwise the criterion is circular.
- **Blocking edges** express real dependencies, including across sectors. Do not use the tree to express a dependency.
- **IDs are permanent.** Re-parenting is a one-line edit; retiring a node means `superseded_by`, never deletion. Logs and commits cite ids (`closes: rm.some-leaf`), which makes log-to-roadmap comparison a grep.
- **Estimates** are in days; keep leaves at 3.0 or under.

## 9. Authoring workflow

1. Draft a small batch (3 to 6 nodes) as a compact table: id, short, title, parent, blocked_by, estimate, done_when, tags. Joe reviews and asks for edits.
2. On approval, write the node files into `roadmap/nodes/`, one file per node, front matter exactly as in section 4. The delivery is either direct file writes (if the session has the folder) or a downloadable bundle Joe unzips into `roadmap/nodes/`.
3. Joe runs `python tools/fy roadmap validate`, then commits. The pre-commit hook validates again and stages the generated files.
4. Repeat. First batch: the root plus the eight sector nodes. Sectors with no children yet must be `stub: true`.

## 10. Rules for Claude Code

- Code creates or edits nodes only when a brief says so.
- Code never sets `signed_off`.
- Code never edits the `done_when` of a node that is `active` or that the current brief has it working on.
- Code never edits generated files by hand.
- Any defect Code observes in a path Joe uses is reported in the memo, even when outside the task.

## 11. Design decisions already made

- One flat file per node (not nested folders): the viewer is the human interface, so nesting only cost deep paths and `git mv` churn.
- Status is derived, never stored in node files, so tooling never edits files that humans and Code also edit.
- `done_when` reads result records and never runs sims, keeping the updater fast and the evidence auditable.
- Generated files are rebuilt by a pre-commit hook into the same commit; no bot commits.
- The viewer is strictly read-only toward the roadmap; drag-and-drop reparenting was declined because a second editor can disagree with the source of truth.
- No new Python dependencies; vendored d3 and marked are the only JavaScript.

## 12. Where things live

| Path | What |
|---|---|
| `roadmap/nodes/` | Authored node files. |
| `roadmap/tags.yaml` | Authored tag vocabulary. |
| `roadmap/state.json`, `roadmap/STATUS.md` | Generated. |
| `roadmap/.pins.json` | Gitignored personal pins. |
| `docs/schemas/` | Node and state JSON schemas. |
| `.githooks/pre-commit`, `.github/workflows/roadmap.yml` | The hook and the notification workflow. |
| `tools/fy` | CLI entry. The library location is recorded in memo13. |
| `docs/briefs/architecture/roadmap-brief1.md` to `brief3.md` | The tooling briefs. |
| `docs/memos/memo13` to `memo16` | Checkpoint reports from each tooling brief. |
| `CONVENTIONS.md`, `docs/STATE.md`, `CLAUDE.md` | Repo rules, current state, session rules. |
