STATE: base d2b32624f7ab | brief architecture sha256:13dc7c519e50, ariadne sha256:missing | snapshot sha256:e5cc96ceed7e | tests 961/962 | dirty no

**Decision summary (roadmap brief 1, T5b and Part B, Checkpoint B).** T5b (a to g), the notification workflow (T6), the viewer server (T7) and the viewer (T8) are built and committed in ten commits. Nothing is pushed, so the workflow has never run on GitHub. `roadmap/nodes/` is still empty.
- **Result.** `fy roadmap serve --root <dir>` opens a local viewer. At 600 files (570 live nodes) the first render takes 147 to 186 ms from navigation start, against the brief's 1 s limit; a full re-render takes 14 to 25 ms. The server is primed before the browser opens and answers `/api/state` from a cache in 15 to 21 ms (385 KB).
- **Cache.** Cold compute at 600 nodes was 2.43 s in the first process after the files were written and 0.54 s afterwards, plus 0.60 s to serialise with the inputs hash, so it did threaten the budget. The cache is keyed on file mtimes and sizes; without it every request pays that.
- **Tests.** 864 before this session, 962 now: 961 pass, 1 fails. The failure also fails on HEAD without my changes: `CLAUDE.md` line 7 names `docs/briefs/stage2e-brief.md`, which commit 29fbfc6 moved to `docs/briefs/ariadne/`. I may not edit `CLAUDE.md`. `fy state` reads that brief as `missing` until you fix the path.
- **Reference values.** Brief limit for first render 1 s (measured 0.15 to 0.19 s). Cold compute 2.43 s, warm 0.54 s (memo 13 reported 0.55 s warm). Estimate cap 3.0 d (unchanged).
- **Decisions for you.** (1) Edit `CLAUDE.md` line 7 to `docs/briefs/ariadne/stage2e-brief.md`; this turns the suite green. Recommend: yes. (2) Push, then watch the first Actions run; with an empty roadmap it must open nothing. Recommend: yes. (3) Add a staleness guard to the workflow (fail when `roadmap/state.json` differs from a fresh build); today a commit that bypassed the hook is notified from stale files. Recommend: yes, as a small follow-up brief. (4) The first push that adds real nodes will open one issue per new ready leaf and per new stub; the brief says so, and I built it that way. Recommend: accept. (5) `CONVENTIONS` section 2 now has no home for bench-run records (the old `fea/`, `tests/` row named them). Recommend: give them a directory, `bench/`.
- **What would change this.** Your visual check is the acceptance test for T8: broad nodes draw very wide trees at depth 3 (horizontal scroll), and a depth-8 breadcrumb wraps to three lines; if either is unacceptable the fixes are a narrower default depth or a collapsed breadcrumb. A first-render time over 1 s on your machine would point at the server compute (cache) or at your browser.

# Roadmap brief 1, T5b and Part B: items a to g, notification, server, viewer

Brief: `docs/briefs/architecture/roadmap-brief1.md` (sha256 prefix `13dc7c519e50`, checked before work). Commits since `29fbfc6`: `18eccb2` (T5b a), `91425a4` (b), `31de3c1` (c), `8e8fe17` (d), `6c98a7e` (e), `f9dc745` (f), `75ba7c1` (g), `933365d` (T6), `be28eed` (T7), `d2b3262` (T8). `CLAUDE.md` was not edited.

## Findings

1. **`CLAUDE.md` names a brief path that does not exist.** Line 7, "Current Ariadne brief", says `docs/briefs/stage2e-brief.md`; commit 29fbfc6 moved the file to `docs/briefs/ariadne/stage2e-brief.md`. Effects, measured: `test_claude_md_names_the_current_brief_of_each_track_and_each_exists` fails (it also failed on HEAD before my first change, checked with `git stash`); `fy state` prints `ariadne sha256:missing`. Before T5b(b) the state tool could not find the line at all (it looked for `Current brief:`), so STATE already said `missing`. I did not edit the file, as instructed.
2. **Pre-flight.** The session's initial git snapshot listed `CLAUDE.md` modified, the nine briefs deleted and `docs/briefs/ariadne/` untracked. By the time I ran `git status` the tree was clean at `29fbfc6`, which is that restructure committed ("dirty yes" at memo 13 was this). Nothing besides memo 13 was affected, so I went on. `git config core.hooksPath` printed `.githooks`: the hook is installed in this clone and ran on each of my commits (it rewrote `roadmap/state.json` and `roadmap/STATUS.md` once, at T5b(a), because the banner changed).
3. **Cold compute was a real risk.** Fresh Python processes, 600 files, fixture seed 3: first process after the fixture was written 0.18 s import + 2.43 s compute + 0.69 s state JSON = 3.30 s; the next five fresh processes 0.18 + 0.54 + 0.60 = 1.31 s each (spread 1.31 to 1.34 s). Profile: `safe_path` calls `resolve()` per path and `inputs_hash` runs it for every node and record (0.59 s of the serialise step; about 0.2 s of compute). I did not change `safe_path` (its escape protection is the point); the server avoids the cost instead (finding 4).
4. **Server design that follows from it.** The server computes once before it opens the browser, then recomputes only when a watched file's mtime or size changes (the node files, plus every file a `done_when` reads, resolved once per snapshot so polling only `stat`s). The live state skips the inputs hash. Measured on the 600-file fixture over a real loopback socket (manual run, not in the suite): process start to primed and listening 1.02 s; `/api/state` 21, 15, 15 ms for 385,236 bytes; a record edit reached an SSE client as `changed` in 1.26 s (one poll interval plus the recompute); foreign `Origin`, foreign `Host` and a POST without the token each returned 403.
5. **Real bugs the new tests caught in my own code, before commit.** `App` fell back to the real editor opener when handed an empty list (falsy), so two failing runs reached `editor.open_file`; on this machine it raised `WinError 2` (`code` is a `.cmd`, which `Popen` cannot start), so nothing opened, but it could have opened files. `buildIndex` threw on an empty roadmap. The "unknown id" notice was cleared by the render it was meant to survive. A narrow-screen CSS rule hid the whole sidebar, search included. With a 12 px minimum band, 93 of the sidebar's bands had no room for their status glyph; the minimum is now 14 px and a test requires a glyph on every band (it fails at 12).
6. **Status without colour, where it is thin.** Every card, list row, pill and band carries a glyph and a label (bands: glyph plus a truncated title). At 14 px in the 320 px sidebar a deep leaf band shows the glyph and one or two characters of its title; the full text is the hover tip and the `aria-label`, and the maximised view (18 px bands, 90 px columns) and the Frontier tab show it whole. I judge this meets the brief's "text label or glyph"; you may disagree for the sidebar.
7. **Stale-state hazard in the workflow (not fixed, decision 3).** `roadmap.yml` validates the nodes but compares the committed `state.json` files. A commit that bypassed the hook leaves `state.json` stale and the issues follow the stale file. A guard (build, `git diff --exit-code roadmap/`) would catch it; it adds a cross-platform determinism risk (a false red on every push if Linux and Windows ever differ), so I left it as a decision.
8. **`docs/STATE.md` no longer lists the briefs.** Its "docs/briefs" section lists only files directly in that folder, which is now `README.md`. Not fixed (outside T5b); one line in `state.py` (`rglob`).
9. **Query wording.** `fy roadmap serve --focus n0` says "matches 10 nodes (showing up to 10)": `query.resolve` returns the capped list, so the count is the cap. Inherited from the CLI wording; unchanged.

## T5b, item by item (each its own commit, full suite before each)

| Item | What changed | Tests after (passed / failed) |
|---|---|---|
| (a) `18eccb2` | `criterion-unknown` warning when a leaf's `done_when` evaluates `unknown`; `roadmap.yaml` removed from the section 2 `roadmap/` row; roadmap banners carry `inputs sha256:<12>` only, and section 4 says so | 867 / 1 |
| (b) `91425a4` | `fy state` reads `Current <track> brief:` lines, one hash per track on the STATE line; no parseable line, a missing backtick, the old `Current brief:` form or two lines for one track prints a message naming `CLAUDE.md` and exits 1 without writing; a named file that does not exist reads `missing` for that track | 874 / 1 |
| (c) `31de3c1` | section 3 gains a "Track terms" paragraph: Ariadne (the digital thread, Stages 2, 3 and on) and architecture (repo tooling such as the roadmap) | 875 / 1 |
| (d) `8e8fe17` | schemas renamed with `git mv` to `roadmap-node-1.schema.json` and `roadmap-state-1.schema.json`; every reference updated; a test pins the name pattern of every file in `docs/schemas` | 876 / 1 |
| (e) `6c98a7e` | `done-out-of-order` also fires for an interior node whose children are all done while its effective blockers are not | 879 / 1 |
| (f) `f9dc745` | section 2: `fea/` row (structured study records) and `tests/` row (pytest modules and their fixtures; `pytest.ini` collects `tests/` and `checks/`) | 880 / 1 |
| (g) `75ba7c1` | decision template shows `"superseded-by: adr-NNNN"` quoted; a test pastes every listed status into a record and parses it (the unquoted form raises a YAML error) | 881 / 1 |

Choices where the instruction left room:
- (a) The 300-node fixture (seed 0) now yields 26 `criterion-unknown` warnings and the 600-node one (seed 3) 55. These are leaves the generator deliberately leaves with a missing record, a missing pointer or an unrecorded check. The generator now writes them to `fixture-intent.json` (`unknown_criteria`), and the tests require the warnings to be exactly those ids and nothing else. Its random draws are unchanged.
- (b) Tracks are listed in alphabetical order (`architecture` before `ariadne`), so the STATE line reads `brief architecture sha256:<h>, ariadne sha256:<h>`. The body has a path line and a hash line per track.
- (c) I added a new paragraph beside "Roadmap terms" instead of extending that one, because the new terms are not roadmap terms. `CLAUDE.md` already defines the same two tracks in prose; the two now agree.
- (e) "Own blockers" is read as effective blockers (own plus ancestors'), the set rule 2 of the derivation already uses. A finished subtree under a blocked ancestor therefore warns once per node on the path. The 300, 600 and 60-node fixtures contain no such case (they still warn only `criterion-unknown`).
- (f) Bench-run records, which the old row named, now have no directory in section 2 (decision 5).
- (d) `docs/memos/memo13` and the brief still use the old names; a brief is yours and a memo records what was true then.

## T6, notification

`.github/workflows/roadmap.yml` runs on push to `main` (the default branch of `JoeCiampa3/freyja-sim`): `permissions: contents read, issues write`; checkout with `fetch-depth: 0` so the before commit exists; Python 3.11; `pip install PyYAML==6.0.3 jsonschema==4.26.0` (the versions `requirements.txt` pins; a test compares them); `fy roadmap validate` (fails the job on errors); then `fy roadmap notify --before "$BEFORE" --after "$AFTER" --repo "$REPOSITORY"` with the event values passed through `env`, never interpolated into a script line (a test enforces it). `gh` gets `GH_TOKEN: ${{ github.token }}`.

`tools/roadmap/notify.py` (153 lines): `plan()` diffs the frontiers of `roadmap/state.json` at the two commits; one `Ready: <title> (<id>)` per new ready leaf and one `Expandable: <title> (<id>)` per new expandable stub, label `roadmap` (created first if the repo has none), body with the criterion, the estimate, the blockers that just cleared (before's uncleared minus after's; "none (new node)" for a node that did not exist) and a link to the node file at the after commit. Skipped when an open issue's title contains the id as a whole token (the `refs` rule, so `rm.foo` is not suppressed by `rm.foo-bar`). Nothing is opened when there is no before state: an all-zero or unknown before commit, a before commit without a state file, or one whose state does not match the schema. An unusable after state, or a `gh` failure, exits 1. `--dry-run` prints the issues and never calls `gh`; it therefore cannot check for duplicates, and says so. 21 tests, `gh` replaced by a recording fake, one end-to-end case on a throwaway git repository with two real commits.

**Not exercised:** the workflow on GitHub. There is no network here and no `actionlint`; its YAML is checked as text. The first run happens on your first push; with `roadmap/nodes/` empty it should print "0 issue(s) to open". Actions are pinned by major tag (`actions/checkout@v4`, `actions/setup-python@v5`), not by commit hash. To rehearse locally: `python tools/fy roadmap notify --before <sha> --after <sha> --repo JoeCiampa3/freyja-sim --dry-run`.

## T7, server

`tools/roadmap/server.py` (366 lines, standard library only; `App.handle` is the application and is tested without a socket, `Shell` is the thin `http.server` adapter; `ThreadingHTTPServer((HOST, port), ...)` with `HOST = "127.0.0.1"`). Endpoints as the brief lists them. `/api/state` returns whatever parsed with the errors, nodes that cannot be derived as `unknown`, and a library crash as a single `internal` problem (never a blank page). Security: random token per launch in a `<meta>` tag, required in `X-Roadmap-Token` on POST (constant-time compare); a request with an `Origin` that is not this server is refused; `/api/node` and `/api/open` accept only ids in the loaded graph and the file path comes from the library. Beyond the brief: a `Host` check against DNS rebinding, a Content-Security-Policy with `script-src 'self'`, `nosniff`, `no-referrer`. Static files are whitelisted by name and extension and only from `tools/roadmap/viewer/`. 46 tests. The real-socket numbers are in finding 4. `fy roadmap serve [--port] [--root] [--focus] [--no-browser]`; `--no-browser` is an addition for headless use.

## T8, viewer

`tools/roadmap/viewer/`: `index.html` (CSS inline), `app.js` (893 lines), `d3.min.js` 7.9.0 (ISC) and `marked.min.js` 12.0.2 (MIT), their licences, and `VENDORED.md` with source URL and sha256 (each file was fetched from two CDNs; the copies were byte-identical). Everything in the brief's sidebar, main view, keyboard, routing and presentation lists is built. Three small decisions of mine inside it:
- In the maximised sidebar a click on a band that has children zooms into it; a click on a leaf focuses it and restores the layout; "Focus on selection" and Enter focus the selected node. I chose not to use double-click because its two clicks would zoom twice.
- The tidy tree's edges for the selection that connect cards in the same row are drawn as arcs under the cards; the 22 px gap between neighbours hid the arrows.
- URL parameters seed the first view for captures (`select`, `tab`, `max`, `zoom`, `q`, `depth`, `theme`, `nolive`, `bench`). They change nothing for a normal launch.

Tests: `tests/test_roadmap_viewer.py` (9) and `tests/test_roadmap_viewer_ui.py` (1, holding 48 checks). Static: vendored hashes and versions, no external URL in `index.html` or `app.js`, markup compatible with the CSP, the single `innerHTML` is the Markdown renderer, the server serves every file the page needs. Logic: the pure functions run in headless Edge/Chrome against answers Python computes from the library: index, icicle invariants (proportional heights where the minimum does not bind, contiguity, minimum where it does), keyboard navigation for every node and key, 32 query cases against `query.resolve` including the `difflib` close-match port, blocker chains, Markdown escaping, routing, a broken graph. A mutation test feeds the harness wrong answers and requires it to fail. Interface: the real page with `fetch` and `EventSource` stubbed and a scripted session. These tests need a Chromium-family browser and skip, with the reason, when there is none; this machine has Edge 155.

**Measurements** (headless Edge, real time, 600-file fixture, 570 live nodes, server primed):

| Measure | Result | Reference |
|---|---|---|
| First render, navigation start to first paint | 159, 163, 171, 147 ms (12 px bands); 186, 176 ms (14 px bands) | brief limit 1000 ms |
| Full re-render on a selection change | 13.8 to 16.2 ms (12 px); 23.2 to 25.4 ms (14 px) | "no visible lag" |
| `/api/state` from the cache | 15 to 21 ms, 385 KB | |

Edge's virtual clock makes in-page timings meaningless (synchronous JavaScript costs about 0 virtual ms), so none were taken there. One capture in three at `bench=20` came back blank: a race in my capture script (the screenshot fired before the first render); the re-runs were fine.

**Screenshots** were produced with headless Edge (no new dependency) and read by me, but are not committed: `CONVENTIONS` section 10 leaves the policy for binaries open. They showed: the root focus in dark and light themes, a deep leaf page with its blocker chain, the maximised icicle, the candidate list, the Frontier tab, and a small roadmap with the selection's blocker and dependent arrows. To make one yourself, with a viewer running on port 8765: `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --screenshot=shot.png --window-size=1500,900 "http://127.0.0.1:8765/?nolive=1&select=rm.n002-gearbox&theme=light#/node/rm.n001-cable"`.

## Try the viewer (your acceptance check)

```
python tools/fy roadmap fixture --size 300 --out C:\temp\rm300
python tools/fy roadmap serve --root C:\temp\rm300
```

The out directory must be empty or absent. `serve` prints the URL (default `http://127.0.0.1:8765/`) and opens the browser. Other views:

```
python tools/fy roadmap serve --root C:\temp\rm300 --focus n279     # a blocked leaf with a 5-node blocker chain
python tools/fy roadmap fixture --size 600 --out C:\temp\rm600 --seed 3
python tools/fy roadmap serve --root C:\temp\rm600                  # the performance case
python tools/fy roadmap serve                                        # the real, empty roadmap: "No nodes"
```

Things worth trying: arrow keys, Enter, `e` (opens the node file in your editor, so set `FREYJA_EDITOR` or leave `code` on the PATH), `/` then a word, `m` then click bands, the depth buttons, "show superseded". To watch live updates, edit a file under `C:\temp\rm300\roadmap\nodes\` or change a record a `done_when` reads: the page should refresh in about a second with focus, selection and the maximised state kept.

## Tolerances and constants I chose

- `POLL_SECONDS = 1.0` and `HEARTBEAT_SECONDS = 15.0` (`server.py`): the brief says "about once a second"; the heartbeat is only there so a closed tab is noticed by a failing write.
- Sidebar minimum band 14 px (18 px maximised), column minimum 30 px (90 maximised), card 190 x 74 px, default tree depth 3 (the brief's number), depth limit 12, blocker-chain cap 60 nodes. They set what is drawn; no check depends on them except the 14 px rule above, which came from a failing test, not from tuning to a pass.
- No check tolerance was changed, and none was tuned toward a result.

## My mistakes

- My first patch script for T5b(a) used a shell heredoc and lost its backslash escapes, as `CLAUDE.md` warns; it failed before writing anything, and I redid the edits with the editor tool. Two later heredocs failed the same way. No commit was affected.
- A test string with a literal closing script tag in my browser harness ended its own script element, and the following `onerror=alert(1)` raised a real alert that hung the headless browser (three test runs of 90 to 300 s). Cleaning up, I stopped processes by matching their command lines: that killed my own pytest and about ten of my headless Edge processes. I did not look for anything else it could have hit.
- I guessed a minimum check count of 50 for the interface test; the real count was 47 (now 48). Corrected.
- I amended my own unpushed T8 commit once, to add the 14 px band minimum after the full suite had passed on the first version; the suite was run again before the amend (961 passed, 1 failed).

## Not done, by the brief's scope or by choice

The weekly report, staleness detection (the `stale` status is still never emitted), any real roadmap content, a write path from the viewer to the repo. Not done by choice: pushing; the workflow staleness guard; listing briefs in subfolders in `docs/STATE.md`; committing screenshots.

## Questions for Joe

1. The five decisions in the summary.
2. Do you want the first push of real nodes to open an issue for each new stub (the brief's rule, built as written), or only for nodes that become workable later?
3. Should "Ariadne" and "architecture" stay as a separate section 3 paragraph, or move into the roadmap-terms paragraph?
