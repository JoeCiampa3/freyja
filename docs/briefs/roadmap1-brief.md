# Stage 3a brief (for Claude Code): roadmap graph, tooling and viewer

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives. This brief builds the project roadmap as a machine-checked graph of small, verifiable goals. It has six parts: a strict decomposition tree with blocking edges laid over it; one authored Markdown file per node; a library that validates the graph and derives every node's status; `fy roadmap` commands; generated status files with a GitHub notification when a node becomes workable; and a local viewer app.

No real roadmap content is written in this brief. Everything is built and tested against synthetic fixtures. Joe's root and first-layer goals go in afterwards, as stub nodes, once the validator exists.

Part A (T1 to T5) builds the contract, the library, the CLI and the generated files, and ends at Checkpoint A. Part B (T6 to T8) builds the notification and the viewer, and ends at Checkpoint B.

## Out of scope

- **Roadmap content.** `roadmap/nodes/` stays empty except for what a test creates in a temporary directory.
- **The existing `roadmap/roadmap.yaml`.** Do not read its contents, migrate it, edit it or delete it. Report in the memo which code, if any, reads it; Joe decides its retirement.
- **Staleness detection** (a done node invalidated by a changed upstream input). The status name is reserved but never computed.
- **Any write path from the viewer to the repo.**
- **The weekly report.**
- **CAD/FEA integration.**

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full.

**Python dependencies.** No new ones. Use `pyyaml` and `jsonschema`, which earlier stages brought in. Confirm both are present before T1; if either is missing, stop and ask.

**Vendored JavaScript.** Pre-approved for T8 only: d3 v7 and marked. Each is vendored as a single pinned minified file under the viewer's static directory, with its exact version and licence recorded beside it. Nothing loads from a CDN at runtime. No npm, no build step, no JS framework.

**Server.** Standard library only: `http.server`, threading, and polling for file changes.

**Determinism.** Everything generated is deterministic: sorted keys and ids, repo-relative paths, LF line endings, no timestamps, and a banner on every generated file.

**Conflicts.** Where this brief and `CONVENTIONS.md` disagree on anything not listed under Amendments, `CONVENTIONS.md` wins and you report the conflict.

## Concepts

The roadmap is a set of nodes.

**The tree.** Every node except the root has exactly one parent. The parent relation is a strict tree and means "is part of."

**Blocking edges.** Separately from the tree, a node may list nodes it is blocked by. These edges may cross branches, and they form a directed acyclic graph laid over the tree.

**Titles.** Every node title is phrased as a verifiable end state ("Elbow actuator selected and decision recorded"), never as an area ("Elbow").

**Node kinds.** Kind is determined by structure:

- An **interior** node has children. It carries no completion criterion, and its status is derived from its children.
- A **leaf** is childless and carries a completion criterion (`done_when`) and an estimate. It is sized to finish in hours to a few days.
- A **stub** is a childless placeholder that has not been decomposed yet (`stub: true`). It carries neither criterion nor estimate. Expanding a stub means either adding children (it becomes interior) or giving it a criterion and an estimate (it becomes a leaf), then removing `stub: true`.

**Naming.** "Gate" already means a blocking check in this repo. A roadmap node's completion criterion is therefore called `done_when`, never "gate." A `done_when` can reference a check, which is how the two concepts connect.

**Who sets what.** Status is derived by the library on every evaluation and is never stored in a node file. Only a human decides `active`, `signed_off` and the criterion itself.

## Amendments to CONVENTIONS (apply in T1, in the same commit as the schemas)

1. **Section 2, the `roadmap/` row.** It now holds `nodes/<id>.md` (authored, one file per node) plus `STATUS.md` and `state.json` (generated). Kind: mixed. `roadmap.yaml` stays listed as it is, pending Joe's decision.
2. **Section 2, new rows.** Add the roadmap library location (chosen in T2) and `.githooks/` (authored).
3. **Section 3, roadmap node IDs.** Proposed form: `rm.<slug>`, where the slug uses lowercase letters, digits and hyphens. If section 3 defines ID kinds in a way this conflicts with, follow section 3 and report. Node IDs obey the permanence rule: a retired node is never deleted; it carries `superseded_by`.
4. **Section 9, new rules for Code.**
   - Code never sets `signed_off`.
   - Code never edits the `done_when` of a node that is `active` or that the current brief has Code working on.
   - Code creates or edits nodes only when a brief says so.
   - `done_when` thresholds are authored by Joe or in a brief before the work starts.
5. **Terms.** Define node, leaf, stub, `done_when` and frontier as this brief does, wherever `CONVENTIONS.md` defines terms. The glossary in `docs/OVERVIEW.md` is not yours to edit; list the new terms in the memo instead.

## The node file

`roadmap/nodes/<id>.md` contains YAML front matter followed by free Markdown that machines ignore (context, rationale, links to briefs, memos and decisions).

```markdown
---
schema: roadmap-node/1
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

### Fields

| Field | Rule |
|---|---|
| `schema` | Required: `roadmap-node/1`. |
| `id` | Required. Equals the filename stem. |
| `title` | Required. |
| `parent` | Required. Null only on the root. |
| `blocked_by` | List of ids. Default empty. |
| `stub` | Bool. Default false. |
| `estimate_days` | Number. Required on leaves; forbidden on interior nodes and stubs. |
| `tags` | List of strings. |
| `done_when` | Required on leaves; forbidden otherwise. |
| `active` | Bool. Default false. Human-set; marks work in progress. |
| `signed_off` | Bool. Meaningful only with `done_when.type: manual`. Only Joe sets it. |
| `superseded_by` | An id. Marks a retired node. |

Unknown fields are a schema error.

### `done_when` types

Every type is evaluated from files already in the repo. The library never runs a simulation, a test suite or a check.

- **`artifact`.** Fields: `path`, plus an optional `schema` (a JSON Schema under `docs/schemas/`). Passes when the file exists, is non-empty and, if a schema is given, validates against it.
- **`decision`.** Field: `record`, a path under `decisions/`. Passes when the record exists and its status is accepted, in whatever format `CONVENTIONS.md` defines for decision records. If that format has no status field, report it and treat existence as a pass.
- **`check`.** Field: `check`, the id of a check under `checks/`. Passes when the repo's recorded result for that check is a pass. Find where check results are recorded (`docs/STATE.md` lists them). If no machine-readable record exists, evaluate as `unknown` and report it.
- **`metric`.** Fields:
  - `record`: path to a JSON file.
  - `pointer`: an RFC 6901 JSON Pointer.
  - `op`: one of `<`, `<=`, `>`, `>=`, `==`.
  - `value`: a number.
  - `units`: a string, documentation only.

  Passes when the comparison holds. The measured value is reported either way.
- **`manual`.** Passes when `signed_off: true`.

Each leaf's evaluation yields `pass`, `fail` or `unknown` (record missing or unreadable), plus a one-line reason and, for metrics, the measured value.

## Status derivation

**Effective blockers.** A node's effective blockers are its own `blocked_by` plus the `blocked_by` of every ancestor. A blocker is cleared when the blocker node's status is `done`.

**Leaf.** Evaluate in this order:

1. `done` if `done_when` passes.
2. Otherwise `blocked` if any effective blocker is uncleared.
3. Otherwise `active` if `active: true`.
4. Otherwise `ready`.

A leaf whose criterion passes while a blocker is still uncleared is `done`, with a "done out of order" warning.

**Stub.** `blocked` if any effective blocker is uncleared; otherwise `expandable`.

**Interior.** Evaluate in this order:

1. `done` if every non-superseded child is `done`.
2. Otherwise `blocked` if any of its own effective blockers is uncleared.
3. Otherwise `in_progress` if any descendant is `done` or `active`.
4. Otherwise `not_started`.

**Superseded node.** `superseded`. It is excluded from its parent's derivation and from every count.

**Reserved.** `stale` is reserved in the state schema and is never emitted in this brief.

**Frontier.** Every `ready` leaf plus every `expandable` stub, sorted by id.

**Reasons.** Every derived status carries a reason. For `blocked`, the reason lists the uncleared blockers by id.

## Validation

### Errors

On any error, validation fails and nothing is generated.

- Schema violation.
- Filename stem differs from the id.
- An id that does not match the ID rule.
- Zero roots, or more than one.
- A parent that does not resolve.
- A cycle in the parent relation.
- A `blocked_by` id that does not resolve.
- A node blocked by itself, by an ancestor or by a descendant.
- A node blocked by a superseded node.
- A cycle in the blocking graph. Build the graph over leaves and stubs: expand each interior blocker to its non-superseded leaf and stub descendants, and apply blocker inheritance from ancestors. Then detect cycles, and name the ids in one cycle.
- A node with children that has `stub: true`, `done_when` or `estimate_days`.
- A childless non-stub missing `done_when` or `estimate_days`.
- A stub with `done_when` or `estimate_days`.
- A `superseded_by` that does not resolve, or that points to a superseded node.
- A superseded node with non-superseded children.

### Warnings

On warnings, generation proceeds and the warnings are listed in the outputs.

- `estimate_days` above the cap. The cap is 3.0, defined once as a named constant.
- Done out of order.
- `active: true` on a done leaf.
- `signed_off` on a criterion that is not `manual`.

### Messages

Every message names the offending ids and file paths. An empty `roadmap/nodes/` is valid and reports "no nodes," not an error.

## Root directory argument

Every command and library entry point takes a root directory, shaped like the repo, that contains `roadmap/nodes/`, and optionally `decisions/`, `log/`, `docs/memos/`, `notebook/` and record files. The default is the repo root. `done_when` paths resolve against this root, which lets fixtures carry their own records and decisions. Git-based reference search runs only when the root is a git repository.

## Part A tasks

**T1. Schemas and conventions.** Write `docs/schemas/roadmap-node-1.json` (the front matter) and `docs/schemas/roadmap-state-1.json` (the generated state file), and apply the amendments in the same commit. Tests: the node schema accepts the example above and rejects one example of each schema-level error.

**T2. Library.** Domain logic lives outside `tools/fy/`, which holds wrappers only. Choose the location in line with section 2 (default `tools/roadmap/`) and state it in the commit message. Pytest tests and fixtures go wherever the existing suite lives, not in `tests/`, which holds bench-run records.

The library loads nodes from the root argument, validates them, evaluates `done_when`, derives status, and computes the frontier, children, dependents and references. Dependents of a node are the nodes whose effective blockers include it. References are occurrences of an id as a whole token, bounded by characters outside `[a-z0-9_.-]`. Search `log/`, `docs/memos/` and `notebook/`, reporting file and line, and commit messages via `git log --fixed-strings --grep`, reporting short hash and subject.

**T2a. Fixtures.** Write a deterministic, seeded generator, `fy roadmap fixture --size N --out DIR`. It writes a repo-shaped root containing a valid synthetic roadmap with:

- depth up to 8, with uneven branching;
- every status represented;
- cross-branch blockers, stubs and superseded nodes;
- its own `decisions/`, metric records and log files.

The generator records the status it intended for each node in a sidecar file. Generated fixtures are not committed; tests generate them into a temporary directory. Separately, commit one small hand-authored invalid fixture per error class above, each containing exactly that one error.

**T3. Derivation and evaluation.** Implement the rules above. Tests:

- On a 300-node fixture, every derived status matches the generator's intended status. The generator builds records and blockers to produce each status, independently of the derivation code.
- Targeted hand-built cases cover every derivation rule, including blocker inheritance from ancestors and interior nodes used as blockers.
- Each invalid fixture yields exactly its one error, naming the right ids.

**T4. CLI.** Thin `fy roadmap` wrappers:

| Command | Does |
|---|---|
| `validate` | Prints errors and warnings. Exits nonzero on errors. |
| `build` | Validates, then writes `roadmap/state.json` and `roadmap/STATUS.md`. Writes nothing on errors. |
| `show <query>` | Prints the breadcrumb (root to node), the fields, status with reason, `done_when` with its evaluation, children with status, uncleared blockers, dependents and references. |
| `frontier` | Lists the frontier with each leaf's criterion and estimate. |
| `refs <query>` | Lists references to the node. |
| `open <query>` | Opens the node file in an editor (resolution order below). |
| `fixture --size N --out DIR` | Generates a fixture (T2a). |

All commands take `--root DIR`; all data commands take `--json`.

`<query>` resolves in this order:

1. The exact id.
2. The id with an `rm.` prefix added.
3. A unique case-insensitive substring of an id or title.
4. Otherwise, print up to 10 candidates sorted by id and exit nonzero.

`open` resolves the editor in this order:

1. The `FREYJA_EDITOR` environment variable, a command containing `{path}`.
2. `VISUAL`, then `EDITOR`.
3. `code -g`, if `code` is on the PATH.
4. `os.startfile`.

**T5. Generated files, hook and STATE.**

`state.json` holds every node with its kind, status, reason, criterion evaluation, children, effective blockers and dependents, plus the frontier, counts, errors and warnings. It carries schema `roadmap-state/1` and a `"_generated"` banner key.

`STATUS.md` carries a banner and contains:

- counts by status;
- problems;
- the frontier;
- active leaves;
- a Mermaid flowchart of the frontier plus one hop of blockers and dependents, capped at 40 nodes. Above the cap, omit the diagram and say why.

`.githooks/pre-commit` is tracked; set its executable bit in the index with `git update-index --chmod=+x`. It runs `fy roadmap build` with the repo `.venv` when present, blocks the commit on errors, and stages exactly `roadmap/state.json` and `roadmap/STATUS.md`, by path.

`fy roadmap install-hooks` sets `core.hooksPath` to `.githooks`. First it checks for existing hooks or an existing `hooksPath`, and if it finds either, it stops with a message instead.

Add one roadmap line to the `fy state` output: node count, frontier size and error count.

Tests:

- Two builds produce byte-identical output.
- The hook behaves correctly on a temporary repository, if that is feasible offline; if not, state why.

**Checkpoint A.** Write the memo per `CLAUDE.md` rule 6. Include:

- `fy roadmap validate` output on each invalid fixture;
- `show` output for one deep leaf, one interior node and one stub in a 300-node fixture;
- a summary of `frontier`: counts and a few ids;
- load-plus-derivation times at 300 and 600 nodes;
- reference search results on the fixture;
- the library location you chose;
- what reads `roadmap/roadmap.yaml`;
- any conflict with `CONVENTIONS.md`.

Stop.

## Part B tasks

**T6. Notification.** Write `.github/workflows/roadmap.yml`, triggered on push to the default branch. It sets up Python and runs `fy roadmap validate`, failing the workflow on errors; this catches commits that bypassed the hook.

It then compares the frontier in `roadmap/state.json` at the before and after commits of the pushed range, and opens one issue per newly ready leaf and one per newly expandable stub.

- Titles: `Ready: <title> (<id>)` or `Expandable: <title> (<id>)`.
- Label: `roadmap`.
- Body: the criterion, the estimate, the blockers that just cleared, and a link to the node file.
- Skip a node if an open issue whose title contains its id already exists.
- Open nothing when there is no before state, or when the before commit is all zeros.

Use `permissions: issues: write` and `gh issue create` with `GITHUB_TOKEN`. The diff is a library function with offline tests. The workflow is a thin wrapper with a `--dry-run` mode that prints the issues instead of creating them. If `.github/` already exists, conform to what is there.

**T7. Server.** `fy roadmap serve [--port 8765] [--root DIR] [--focus QUERY]` runs on the standard library's `ThreadingHTTPServer`, bound to 127.0.0.1 only. It opens the browser at its URL (adding `#/node/<id>` when `--focus` is given) and prints the URL.

| Endpoint | Returns or does |
|---|---|
| `GET /` and static assets | The viewer. |
| `GET /api/state` | The `state.json` content, computed live. |
| `GET /api/node/<id>` | The node's body Markdown, references and file path. |
| `GET /api/events` | Server-sent events. The server polls node files, plus every file a `done_when` references, about once a second, and emits `changed` when any mtime or size changes. |
| `POST /api/open/<id>` | Opens the node file using the T4 editor resolution. |

When validation fails, `/api/state` still returns whatever parsed, together with the errors; statuses that cannot be derived come back as `unknown`. A broken edit must show up as problems, never as a blank page.

Security:

- A random token is generated per launch, embedded in the served page, and required as a header on every POST.
- Requests whose `Origin` is not this server are rejected.
- `/api/open` accepts only ids present in the loaded graph and resolves the file path through the library, never from the request.

Tests: run the API handlers in-process. If loopback sockets in tests conflict with the no-network rule, call the handlers directly.

**T8. Viewer.** One `index.html` and one `app.js`, plus the two vendored files, all served by T7.

### Sidebar

The left sidebar is resizable, about 320 px wide by default. It has a search box at the top, using the CLI query rules with a live candidate list, and three tabs:

- **Tree.** The whole tree as a horizontal icicle.
  - Depth runs along x, with the root at the left; siblings stack along y.
  - Each band's height is proportional to its count of non-superseded leaf and stub descendants, with a minimum height so interior bands stay clickable.
  - Bands are filled by status; stubs are hatched.
  - The current focus subtree is outlined, and the selected node, its blockers and its dependents are marked.
  - Hovering shows title and status.
- **Frontier.** The frontier list, with each criterion and estimate.
- **Problems.** Errors and warnings, with a count badge on the tab.

A maximise control (also the `m` key) expands the sidebar to the full window for a readable whole-tree view, with click-to-zoom into a subtree and a way back up. Selecting a node there sets the focus and restores the normal layout.

### Main view

The main view is driven by the focus node. A breadcrumb of its ancestors sits at the top, each one clickable.

**Interior focus.** A top-down node-link tree (d3 tidy tree) rooted at the focus, three levels deep by default, with controls to change the depth. Each node is a card showing title, status label and estimate. Clicking a card selects it, and a detail drawer on the right shows the selected node. Double-clicking or pressing Enter refocuses on it.

Blocking edges are drawn only for the selected node, as dashed connectors to whichever of its blockers and dependents are visible in the tree. Blockers and dependents outside the view appear as chips in the drawer, and clicking a chip refocuses on that node.

**Leaf or stub focus.** A single-node page fills the main view, showing:

- title, status and reason;
- the criterion and its evaluation, including the measured value for metrics;
- estimate and tags;
- the rendered Markdown body, with raw HTML escaped;
- the chain of uncleared blockers, laid out left to right;
- dependents and references.

The drawer and the single-node page both carry "Open in editor" and "Copy id" controls.

### Keyboard and routing

| Key | Action |
|---|---|
| Up | Select the parent. |
| Down | Select the first child. |
| Left / Right | Select the previous / next sibling. |
| Enter | Refocus on the selection. |
| `e` | Open the selection in the editor. |
| `/` | Jump to search. |
| `m` | Maximise the sidebar. |
| Esc | Leave maximised mode. |

Routing uses `#/node/<id>`, and browser back and forward move through focus history. On a `changed` event, the viewer refetches and re-renders, preserving focus, selection and maximised state.

### Presentation

- Status is never conveyed by colour alone: every status has a text label or glyph.
- The palette is colour-blind safe.
- Light and dark themes follow `prefers-color-scheme`.
- Superseded nodes are hidden by default, with a toggle to show them.

### Performance

On a 600-node fixture, first render takes under one second and interactions show no visible lag. Report whatever times you can measure.

**Checkpoint B.** Write the memo: what was built; the measured times; screenshots, if you can produce them without a new dependency (otherwise say so); and the exact commands for Joe to try the viewer, `fy roadmap fixture --size 300 --out <dir>` followed by `fy roadmap serve --root <dir>`. Joe's visual check of the viewer is the acceptance test for T8. Stop.

## Prerequisites for Joe

- Commit this brief; committing it approves the amendments.
- Confirm that GitHub Actions is enabled on the repo and that you are watching it, so roadmap issues reach your inbox.
- After Part A, run `fy roadmap install-hooks` in every clone you commit from.
