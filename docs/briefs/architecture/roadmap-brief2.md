# Roadmap brief 2 (for Claude Code): fixes, pins, and the viewer redesign

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then `docs/memos/memo14-roadmap-part-b.md`.

Brief 1 (`docs/briefs/architecture/roadmap-brief1.md`) built the roadmap library, CLI, generated files, notification workflow and viewer. Its rules stay in force wherever this brief does not change them.

This brief has three parts:

- Fix what Joe's use of the viewer and memo 14 exposed.
- Change how notifications are computed.
- Add pins, and redesign the viewer's sidebar and main view.

There is one checkpoint, at the end. Joe's visual check of the viewer is the acceptance test for T8 and T9.

## Out of scope

- Real roadmap content: `roadmap/nodes/` stays empty.
- Staleness detection.
- Any viewer write path except the pins file (T6).
- Setting `active` from the viewer or the CLI.
- The weekly report.
- Committing screenshots or any other binary, because the binary policy in `CONVENTIONS.md` section 10 is still open.

## Ground rules

`CONVENTIONS.md` section 9, the `CLAUDE.md` session rules and brief 1's ground rules all apply.

- **Dependencies.** No new ones. The vendored d3 and marked from brief 1 remain the only JavaScript.
- **Commits.** One commit per task, never combined, with the full suite run before every commit.
- **Defect reporting.** Any defect you observe in a path Joe uses (CLI, viewer, hook, workflow) is a finding and goes in the memo, even when it lies outside the task you are on. Memo 14 found that `code` cannot be launched on Windows, fixed only the test that hit it, and left the real launcher broken. Add this rule to `CONVENTIONS.md` section 9 in T1's commit.

## Part 1: fixes

**T1. Editor launcher.**

Memo 14, finding 5: on Windows, `code` is a `.cmd` shim, and `Popen` cannot start it by bare name. The result is `WinError 2` ("the system cannot find the file specified"), so "Open in editor" fails for Joe.

Required behaviour:

- Resolve the editor command to its full path with `shutil.which` before launching, and launch `.cmd` and `.bat` shims correctly on Windows. Arguments come from the library, never from a request; quote them safely anyway.
- Resolve the node path to an absolute path under `--root`.
- If the resolved editor fails to launch, fall back to `os.startfile`.
- If everything fails, `fy roadmap open` exits nonzero with the underlying error, and `/api/open` returns that error. The viewer shows it as a visible notice instead of failing silently.

Tests:

- A Windows-only test (skipped elsewhere) puts a fake `.cmd` shim on `PATH` in a temporary directory and asserts that it received the absolute node path.
- A test for each fallback step.

Report the root cause and the mechanism you chose.

**T2. Awaiting versus unknown evidence.**

The `criterion-unknown` warning from brief 1's T5b fires whenever a criterion's evidence is missing. In a real roadmap, the evidence for unfinished work usually does not exist yet, so the warning would bury the Problems tab. Split the old `unknown` result into two:

| Criterion type | `awaiting`: no warning | `unknown`: warns `criterion-unknown` |
|---|---|---|
| artifact | The file is absent and its parent directory exists. | The parent directory is missing. |
| metric | The record is absent and its parent directory exists. | The file exists but cannot be parsed; the pointer does not resolve in an existing file; or the parent directory is missing. |
| decision | The record is absent and its parent directory exists. | The record exists but its status cannot be parsed; or the parent directory is missing. |
| check | The check is listed in `docs/STATE.md` as "not run". | The check id is not listed in `docs/STATE.md` at all. |
| manual | Not applicable. | Never. |

Neither `awaiting` nor `unknown` counts as a pass.

Update the state schema according to the versioning rule in `CONVENTIONS.md`, which most likely means `roadmap-state/2`. Add "awaiting" to the roadmap terms in `CONVENTIONS.md` section 3.

Update the fixture generator so its intent file separates `awaiting_criteria` from `unknown_criteria`. The tests must require that the warnings name exactly the `unknown` ids.

**T3. Fixture shape.**

The current generator gives the root 2 children, one of which holds almost every leaf. That made the first wide layer look worse than a real roadmap will. The root should have 5 to 10 first-layer branches, seeded, of uneven size, with distinct titles. Keep depth 6 to 8, and keep every brief 1 coverage guarantee.

Add `--first-layer N` to override the branch count. The intended-status tests must still pass on seeds 0, 3 and 7.

**T4. Small items.**

- `fy state` lists briefs recursively under `docs/briefs/`. Since the folder split it lists only the top level.
- Query messages report the true match count, not the display cap.
- `CONVENTIONS.md` section 2 gains a `bench/` row for bench-run records (authored). It replaces the home they lost when the `fea/` and `tests/` row was split.

## Part 2: notification

**T5. Fresh frontiers.**

The workflow must stop trusting the committed `roadmap/state.json` for notifications. Memo 14, finding 7: a commit that bypassed the hook leaves that file stale, and the issues follow the stale file.

Instead, check out the before commit and the after commit into temporary git worktrees. Build both with the after commit's tool code, `--root` pointing at each worktree, and compute the issues from those two fresh states.

- A before commit with no `roadmap/nodes/` is a valid empty frontier. Opening one issue per new ready leaf and per new expandable stub on the first real push is the accepted behaviour.
- An all-zero or unknown before commit still opens nothing.
- If the committed `state.json` at the after commit differs from the fresh build, emit a `::warning::` annotation naming the differing node ids. This is a warning, not a failure, so a cross-platform byte difference can never turn every push red.

Tests run offline on a throwaway repository with real commits:

- one commit that bypassed the hook;
- one before commit with no roadmap;
- the all-zero case.

## Part 3: pins and the viewer

**T6. Pins.**

Pins are personal bookmarks to any node, for quick access. They are not roadmap state: nothing derives from them, and they are never committed.

**Storage.** `roadmap/.pins.json` under the root holds a sorted JSON list of ids. Add it to `.gitignore`. Writes are deterministic. Code never edits a real clone's pins file; tests use temporary roots.

**CLI.**

| Command | Does |
|---|---|
| `fy roadmap pin <query>` | Adds the node to the pins. |
| `fy roadmap unpin <query>` | Removes the node from the pins. |
| `fy roadmap pins [--json]` | Lists pins with their current status. Ids no longer in the graph are listed as dangling, never silently dropped. |

**Server.**

| Endpoint | Does |
|---|---|
| `GET /api/pins` | Returns the pins. |
| `POST /api/pin/<id>` | Pins the node. |
| `POST /api/unpin/<id>` | Unpins the node. |

The POSTs follow brief 1's token and `Origin` rules and accept only ids in the loaded graph. The server writes no file other than this one.

Add pins to `CONVENTIONS.md` section 2 as gitignored, per-clone and personal.

Tests: CLI and API, including dangling ids and rejected foreign requests.

**T7. Sidebar.**

Remove the icicle and the sidebar maximise control. The sidebar keeps the search box and holds two things.

**Working panel.** A collapsible panel at the top, always visible above the tabs, with two groups:

- **Active.** Every leaf with `active: true`, derived from the repo. This is what is being worked on, and the same set memos and Code see.
- **Pinned.** The pins, in pin order sorted by id.

Each row shows status glyph, title and id. Clicking a row focuses that node.

**Tabs.** Outline, Frontier and Problems, in that order.

- **Outline.** A collapsible indented tree with one row per non-superseded node. Each row shows a status glyph, the title truncated to the sidebar width (full title on hover), and a done/total fraction on interior rows. Each level indents about 12 px.
  - Everything starts collapsed except the path from the root to the current focus. That path expands automatically, scrolls into view and stays highlighted as focus changes.
  - Search filters the outline to matching nodes plus their ancestors.
  - Status filter chips (ready, active, blocked, expandable, done) narrow it further.
  - Pinned rows show a star.
- **Frontier** and **Problems** are unchanged from brief 1.

**T8. Main view: focus mode.**

**Compact layout.** Under each node, its childless children stack in a vertical column. Only interior children spread horizontally.

**Child order.** active, ready, expandable, blocked, in_progress, not_started, done; ties broken by id.

**Overflow.** A node with more than 8 children shows the first 8, then a "+k more" card that expands in place.

**Depth.** The default depth is the largest that fits the main view's width, recomputed on resize. The +/- controls override it until the focus changes.

**Navigation.** Drag pans and the mouse wheel zooms, replacing the horizontal scrollbar. A fit button and the `f` key reset the view.

**Breadcrumb.** Beyond four ancestors, show root › … › grandparent › parent › node. Clicking the "…" expands the full path. Titles truncate at about 28 characters, with the full title on hover.

**Cards.** Interior cards gain a progress bar for done/total.

**Pins.** A star toggle appears on cards, in the drawer and on the single-node page. The `p` key pins or unpins the selection.

**Errors.** Failures of open and pin calls show as visible notices.

**T9. Main view: map mode.**

The `m` key and a Map button toggle the main view between focus mode and a full-screen map of the whole tree. Esc also leaves the map. Clicking a node in the map leaves the map and focuses that node.

**Layout.** Radial by default, with depth as rings from the root at the centre (a radial d3 tree, not a cluster, so a ring means a depth). A control toggles a top-down layout.

**Navigation.** Wheel zoom and drag pan, a fit button, and `f`. Marker sizes stay constant on screen. Titles appear beside nodes once zoom passes a threshold at which they no longer overlap.

**Encoding.** Status is never conveyed by colour alone:

- Every leaf and stub status has its own marker shape as well as its colour.
- Interior nodes are rings filled to their done fraction.
- Each first-layer branch gets a faint background sector, labelled with the branch title.
- Pinned nodes carry a star.
- The current focus is marked "you are here" and centred when the map opens.

**Hover.** A tooltip shows title, id, status and fraction. The path from the hovered node to the root is highlighted, and the node's blockers and dependents are drawn as dashed connectors. No blocking edge is drawn otherwise.

**Frontier toggle.** Dims every node that is neither ready nor expandable.

**Performance.** Measure on a 600-file fixture with the T3 shape:

- the first render of focus mode stays under 1 s;
- opening the map takes under 0.5 s;
- pan, zoom and hover show no visible lag.

Report measured times. If SVG cannot meet these, use canvas for the map and say why.

**Keyboard, complete:**

| Key | Action |
|---|---|
| Up / Down / Left / Right | As in brief 1. |
| Enter | Refocus on the selection. |
| `e` | Open the selection in the editor. |
| `p` | Pin or unpin the selection. |
| `m` | Toggle map mode. |
| `f` | Fit the view. |
| `/` | Jump to search. |
| Esc | Leave map mode, or clear search. |

Keys are ignored while typing in an input. Extend the existing viewer tests to cover the new behaviour: outline expansion along the focus path, the overflow card, auto-depth, pin round trips, map toggling and the keyboard map.

## Checkpoint

Write the memo per `CLAUDE.md` rule 6. Include:

- the T1 root cause and fix;
- the counts of `awaiting` and `unknown` on the fixtures;
- the T5 test cases;
- the measured performance figures;
- every finding from the defect-reporting rule;
- the exact commands for Joe to try the viewer on a 300-node fixture with the new shape;
- a short list of what to look at: the outline, the map, a wide node, a depth-8 breadcrumb, pins, and Open in editor;
- the screenshot capture command, without committing any image.

Run `fy state` and stop.

## Prerequisites for Joe

- Update the "Current architecture brief" line in `CLAUDE.md` to this file.
- Push the existing commits and check the first Actions run before this session. If it failed, put the error in the prompt.
