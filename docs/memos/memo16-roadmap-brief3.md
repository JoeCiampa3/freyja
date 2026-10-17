STATE: base 9a1658e2fec9 | brief architecture sha256:f5d1a1aafa1f, ariadne sha256:0a67a27df03a | snapshot sha256:e5cc96ceed7e | tests 1095/1095 | dirty yes

**Decision summary (roadmap brief 3).** T1 to T3 are built, one commit each with the full suite before it: nodes can carry a short label, tags are checked against a vocabulary, and the map can be coloured by region or phase. The three commits are not pushed (`main` is 3 ahead of `origin/main`), `roadmap/nodes/` is still empty, and the full suite passes (1095).
- **What you can do now.** Give a node `short: Skeletal` (schema `roadmap-node/2`) and the map sectors, the map labels and the breadcrumb use it. Tag nodes `region:arm-l` and `phase:bench`; a typo is an error that names the node. In the map, Colour by Region or Phase fills the markers, a legend counts each value and dims the rest when clicked, and the view is in the URL hash. Search `tag:region:arm-l` or `tag:cad` filters the outline.
- **Numbers**, 600-file fixture (570 nodes), real time, headless Edge: map open 44 ms the first time and 6 ms reopened (limit 500); recolour 0.5 to 2.3 ms in the handler, 7 to 25 ms to the painted frame (a 60 Hz frame is 16.7); legend click 3 ms. Colours: every one keeps at least 3.00 : 1 contrast (WCAG 3 : 1 for graphics) on the light and dark backgrounds; the smallest CIE76 gap between two region colours or the grey, under normal vision and three simulated colour deficiencies, is 13.5 (goal 12); phase 22.9 (goal 20).
- **Decision 1.** I bumped the state file to `roadmap-state/3` (it needed `short` and the vocabulary) and renamed the two schema files with `git mv`, as brief 2 did for state. The node schema is `roadmap-node/2` and still accepts every `roadmap-node/1` file. Recommend: accept.
- **Decision 2.** The colours are metric-optimal, not pretty (many purples; left and right limbs are not related). A different look needs a hand-picked set that still passes `tests/test_roadmap_tags.py`. Recommend: look at the map first; edit `roadmap/tags.yaml` only if a pair confuses you.
- **Decision 3.** `tag:region` (a bare namespace) matches nothing, as the brief's syntax says. It would be easy to make it match any region value. Recommend: leave it unless you want it.
- **What would change this.** Your visual check of the map in both themes at your window size; a colour pair you cannot tell apart; or a link that does not restore the view.

# Roadmap brief 3, T1 to T3: short labels, tag vocabulary, colour by tag

Brief: `docs/briefs/architecture/roadmap-brief3.md` (sha256 prefix `f5d1a1aafa1f`, checked before work). Commits since `9d86025`:

| Task | Commit | Full suite after (passed / failed) |
|---|---|---|
| T1 short label | `02e6416` | 1052 / 0 |
| T2 tag vocabulary | `62395f6` | 1093 / 0 |
| T3 colour by tag | `9a1658e` | 1095 / 0 |

`CLAUDE.md` was not edited. This memo and `docs/STATE.md` are the last commit.

## Findings

1. **My three commits are not pushed.** `git status -sb` reads `main...origin/main [ahead 3]`, so the brief-2 commits were pushed and these are not. The GitHub connector failed to connect at the start of this session (as in memo 15), so I still cannot see an Actions run; T1 and T2 change what a push validates (`roadmap/tags.yaml` is now an input), so check the first run after you push.
2. **The state file's banner hash changed.** `tags.yaml` is now an input of `inputs sha256:` and of the server's file watch, so the committed empty roadmap's banner no longer reads `e3b0c44298fc` (the hash of nothing). Intended; the pre-commit hook regenerated `roadmap/state.json` and `STATUS.md` in each commit.
3. **Heredocs broke two test files again** (the failure `CLAUDE.md` warns about): `\n` and `\r` escapes inside a shell heredoc became real line breaks in `tests/test_roadmap_schema.py` and `tests/test_roadmap_validate.py`. Both failed loudly before any commit; I rewrote the lines with the editor tool. Later edits that needed backslashes went through the editor tool or script files.
4. **The `tag:` search matches exact tags only.** `tag:region` finds nodes carrying a tag literally called `region`, so none (decision 3). `tag:arm` finds the free tag `arm`.
5. **Legend order was wrong in my first build and I fixed it before committing T3.** The state file is written with sorted keys, so an object of values loses the order of `tags.yaml`; the legend then listed region values alphabetically (arm-l before head). The values are now an ordered list of `{value, colour}`. My first logic test compared sorted with sorted and passed; the state test now pins the file order (head, neck, torso ...), and I found the fault in a screenshot.
6. **Short length counts characters differently in Python and JavaScript.** The schema's 16 counts code points; JavaScript counts UTF-16 units. A label of astral characters (emoji) could be longer on screen. The viewer only truncates, so nothing breaks. Not changed.
7. **Superseded nodes are tag-checked too** (my reading: typo protection applies to every file). A retired node with a bad tag blocks the build. Say if retired nodes should be exempt.
8. **Old briefs and memos still cite `roadmap-node-1.schema.json` and `roadmap-state-2.schema.json`.** They are history and briefs are never edited; the files were renamed with `git mv`, so `git log --follow` finds them.
9. **The map's Colour by lives only in map mode,** as the brief says; the focus view still colours by status.

## T1: short label

`roadmap-node/2` adds `short` (string, 1 to 16 characters, no line break of any kind, including U+2028 and U+2029). `roadmap-node/1` files load as before and may not carry `short`: a v1 file with it is a schema error whose message says to change the `schema:` line. One schema file, `roadmap-node-2.schema.json` (`schema` is an enum of both versions; an `if/then` forbids `short` on v1), so there is a single validator. State: `roadmap-state/3` (`short`, null when absent).

Viewer: map sector labels, map node labels (at the zoom where titles appear) and breadcrumb segments before the last use `short`; the last segment, the drawer, the outline and every tooltip keep the title (sectors gained a hover title with the full title; the map tooltip already had it). Fixtures: first-layer nodes and about one in five others carry `short` (v2 files), the rest stay v1. They use their own random stream, so no other fixture value moved (every earlier seed-dependent test passed unchanged).

Tests: the schema accepts `short` at 16 characters and rejects 17, empty, line breaks, non-strings and v1 with `short`; the loader reads both versions side by side; state carries it; the logic harness checks `crumbParts` and the sector `label`; the interface test checks the sector label text, the map node label text and the breadcrumb DOM. Mutating the viewer to ignore `short` fails them (run by hand).

## T2: tag vocabulary

`roadmap/tags.yaml` (authored, `roadmap-tags/1` schema, listed in `CONVENTIONS.md` section 2): `namespaces:` then namespace, value, optional `#rrggbb` or null. Exactly `region` (14 values) and `phase` (6), in the brief's order. Validation (`tools/roadmap/tags.py`): `tag-unknown-namespace` and `tag-unknown-value` are errors naming node, file and tag (the value error lists the allowed values); `tag-duplicate-namespace` is a warning; free tags pass; no file means no namespaces; a file that cannot be read or fails its schema is one `tags-file` error and its tags are not judged (an error per tag would bury it). Tags split at the first colon, so `a:b:c` is namespace `a`, and `region:head:left` is an unknown value. Hand-authored invalid fixtures, one per new error: `tag-unknown-namespace`, `tag-unknown-value`, `tags-file-broken` (in `tests/test_roadmap_validate.py`'s table). The fixture generator ships the real `tags.yaml` and tags about 70% of nodes with a region and 60% with a phase (never two values of a namespace), from its own random stream.

**Colours** (`analysis/tag_palette.py`, deterministic, seed 20261017; the script is the provenance of the hexes). Goals fixed before the search ran: contrast at least 3 : 1 with all four viewer backgrounds (light `--bg` and `--panel`, dark `--bg` and `--panel`; WCAG 2.1 1.4.11), so one hex serves both themes; CIE76 Delta E at least 20 within `phase` and 12 within `region`, each also against the grey for "no tag" `#8c8c88`, under normal vision, protanopia, deuteranopia and tritanopia (Machado et al. 2009, severity 1.0). Chosen:

| region | | | | phase | |
|---|---|---|---|---|---|
| head `#e409fc` | neck `#f94b01` | torso `#9155ac` | spine `#7e6a2e` | spec `#9029fa` | sim `#d27c06` |
| pelvis `#cc6add` | arm-l `#c13357` | arm-r `#5f7088` | hand-l `#e462b3` | design `#9a5397` | fab `#be3d25` |
| hand-r `#21a51d` | leg-l `#ad20c8` | leg-r `#2e775d` | foot-l `#9f03fb` | bench `#e149ed` | integrate `#3da25b` |
| foot-r `#4b78f7` | whole-body `#bf835e` | | | | |

Measured on the committed file: region, smallest contrast 3.001, smallest separation 13.47 (head and foot-l under protanopia and deuteranopia; per mode: normal 20.8, protan 13.5, deutan 13.5, tritan 15.8); phase, smallest contrast 3.033, smallest separation 22.95 (integrate against the grey under deuteranopia; per mode: normal 33.6, protan 24.4, deutan 22.9, tritan 25.9). A test asserts every one of these against the goals. Limits: CIE76 under a dichromacy simulation is a proxy, not a person; 14 region colours are near what the method can separate, which is why the goal is 12; left and right limbs are not visually related.

## T3: colour by tag

Control, fills, grey, rings, sectors and legend are as the brief says. Choices the brief left open: the legend lists every vocabulary value (zero counts included, so `neck 0` shows) in the order of the file, then "no <namespace> tag"; counts cover every node on the map, interior nodes too, and add up to the node count (a test asserts it); dimming applies to every marker and its label; a value without a colour is drawn grey and its legend row says so on hover; the select blurs after a change (a focused select swallows the map's keys); hover on a marker adds the chosen namespace's value. State and hash: the choice lives in the page for the session and in the hash as `#/node/<id>?colour=<namespace>&only=<value or _none>&map=1`, with the default view having no parameters. Opening a link restores it (the map opens if `map=1`); an unknown namespace is ignored, an unknown value is dropped; a hash without `colour` leaves the current choice alone; changes use `replaceState`, so they add no history entries. A namespace that vanishes from the vocabulary falls back to Status. Search: `tag:` as described in finding 4; the outline shows matches plus ancestors, and the candidate list shows up to 10 matching nodes.

**Measured** (600-file fixture seed 3, 570 nodes, `fy roadmap serve` on loopback, headless Edge driven over the DevTools protocol, real time; the capture script is a scratch file, not in the repo):

| Measure | Result | Limit or reference |
|---|---|---|
| first render of the focus view | 166 ms in the page, 178 ms from navigate (cold) | 1000 ms (memo 15: 246 cold) |
| map open, first (layout and 570 markers built) | handler 44.6 ms, 53 ms to the second frame | 500 ms (memo 15: 35 to 46) |
| map reopened (cached) | handler 6.2 to 7 ms, 11 to 15 ms to the second frame | |
| recolour, handler | 0.5 to 2.3 ms (the page's own timer: 0.5 to 2.0) | no visible lag |
| recolour, to the second painted frame | 7 to 25 ms (mostly 15 to 16: the frame interval) | 60 Hz frame 16.7 ms |
| legend click (dim 563 of 570) | handler 3.1 ms, 14 ms to the second frame | |

Recolouring repaints the existing markers and rebuilds only the legend (about 15 buttons); no layout is recomputed. SVG is still enough.

Tests: the logic harness (colour mapping per namespace against Python's reading of the node files and `tags.yaml`; the grey; legend counts and order; `carries`; value-without-colour; hash round trips; the `tag:` queries, including case and spacing) and the interface test (181 checks, was 144: Colour by options; fills as painted by the browser, grey included; shape, status, kind, rings, wedges and sector styles unchanged; legend rows and counts; dimming and its undo; persistence across close and reopen; the hash at each step; links with good and bad parameters; the recolour timer; no vocabulary; the outline and candidates for `tag:`). Four hand mutations (inverted `carries`, wrong grey, a hash sync that does nothing, a search that ignores tags) each fail named checks.

## Try it (your acceptance check)

PowerShell, from the repo root. Stop any old viewer first (`serve` now refuses a port that is taken):

```
Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue | Select-Object OwningProcess
python tools/fy roadmap fixture --size 300 --out C:\temp\rm300d
python tools/fy roadmap serve --root C:\temp\rm300d --port 8770 --no-browser
```

Then open these in your browser (the second and third restore the whole view from the link):

```
http://127.0.0.1:8770/
http://127.0.0.1:8770/#/node/rm.n000-root?colour=region&map=1
http://127.0.0.1:8770/#/node/rm.n000-root?colour=phase&only=fab&map=1
```

On the first, press `m`, then pick Colour by Region and then Phase, click legend rows, press Esc and `m` again (the choice stays), and try the top-down layout. In the search box (`/`) try `tag:region:whole-body`, `tag:cad` and `tag:phase:sim`. Sector titles and the breadcrumb show short labels (the first-layer nodes have them). The same fixture with 600 nodes: `python tools/fy roadmap fixture --size 600 --out C:\temp\rm600d --seed 3`.

## Tolerances and constants I chose

Colour goals as above, fixed before the search; none was tuned toward a result (the first search met them). Presentation constants: legend dim opacity 0.13 (markers and labels), legend panel 190 to 280 px wide and at most 45% of the height; the `short` limit 16 and the candidate cap 10 (the existing cap) came from the brief and the existing code. `UNTAGGED` grey `#8c8c88` (3.23 : 1 on the light `--bg`, 3.38 on white, 5.37 on the dark `--bg`, 4.90 on the dark panel; a test asserts at least 3 : 1) is shared by the palette script and the page, and a test pins the two to the same hex. No check tolerance was changed.

## My mistakes

- The two heredoc corruptions (finding 3).
- My first T3 logic test compared the vocabulary's order with a sorted copy of itself, so it could not fail on order (finding 5); a screenshot showed the alphabetical legend, and the test now pins the file order from the real `tags.yaml`.
- I edited `roadmap/state.json` with `sed` once to change the version string, then reverted it and regenerated it with `fy roadmap build`; it is a generated file and nothing hand-edited was committed.
- I first parsed a `schema:` line in a fixture test out of the whole file, which picked up a `done_when` schema path; the test now anchors on the line start.

## Not done, by the brief's scope or by choice

`roadmap/nodes/` content, any change to the sector structure, any viewer write path beyond the pins file, committing screenshots (they are in `C:\temp\shots`, not the repo), pushing, a `tag:<namespace>` form, and Colour by in the focus view. The nested-button and hover-only accessibility points from memo 15 are unchanged.

## Questions for Joe

1. The three decisions in the summary.
2. Should retired (superseded) nodes be exempt from tag checks (finding 7)?
3. Do you want a hand-picked palette in place of the optimised one after you have looked at it?
