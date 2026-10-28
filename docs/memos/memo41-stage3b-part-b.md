STATE: base 6cb36d4d9bf8 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2017/2021 | dirty no

# Memo 41: Stage 3b Part B, the round trip on the placeholder, the envelope, staleness and the `work` criterion (T5 to T9)

Brief: `docs/briefs/ariadne/stage3b-brief.md`, with your decisions on memo 40. Commits: `fy test --quick` `a9eeffa`, T5 `2f815c1`, T6 `4404684`, T7 `36abc94`, T8 and T9 `5bea1bb` and `6cb36d4`. Written for Joe, who signs off the gate table.

## Decision summary

- **What it means for Freyja.** The bridge works end to end on a real Fusion design. `Upper Arm v0` (a 6061 tube, 255.2347 mm after the push) goes out and back in 3.9 s: its length comes from the sheet through `snapshot#/upper_arm_right_length`, its mass (0.121239 kg) reaches `seg.upper_arm`'s budget through an address into the sidecar, its mesh enters the envelope as a component, and moving the sheet's length by 10 mm marks the CAD stale. All eight gates pass. Nothing in the bridge needs the part to be a design, so the real upper arm reuses it.
- **The numbers that matter.**

| Number | Value | Reference |
|---|---|---|
| `fy cad push` + `pull` on the placeholder (validate / status) | 3.9 s (1.2 s / 0.9 s) | budget 60 s (5 s) |
| Two pulls with no change: sidecar, STL, component yaml | byte-identical (3 of 3) | gate: identical sidecar and STL |
| Placeholder mass through the address | 0.121239 kg, 1 x on the right, in the budget row | gate: an address, not a typed number |
| Staleness: snapshot length +10 mm, in memory | `current -> stale`; reverted: `current` | gate: stale, then current |
| `fy envelope check`, placeholder as a designed component (cylinder example, feasible pose) | margin -15.78 mm, binds at (2.0, 14.8, -160.9) mm, confidence clear | no reference: the candidate overlaps the tube |
| Tessellation: chord bound, normal deviation, triangles | 0.0500 mm, 9.36 degrees, 1162; guarantee true | request 0.05 mm |
| Test suite | quick subset 4 min; full 17 min (2017 passed; `fy state`: 2017 passed, 1 failed, 3 skipped) | memo 40: full 18 min |

- **Decisions for you.** (1) Sign off the gate table (G1 to G8 below): recommended yes. (2) The sidecar pins document version 1, but the pushed length is an unsaved edit in Fusion (the bridge never saves): the pinned version does not describe the pulled state. Recommended: save `Upper Arm v0` yourself after a push, then pull, and let me add `unsaved_changes` to the sidecar's `document` with `fy cad stamp` refusing when it is true (a schema change; I have not made it). (3) The placeholder tube sticks out of the skin by 10.97 mm: expected from the contract (a part on the model's axis is not on the arm's centre line, the elbow node is near the lateral skin) but a convention for the real design needs deciding before it starts. (4) Adopt the `work` criterion on the nodes listed below.
- **What would change the conclusion.** The real upper arm has free-form faces (skin-following shells): `chord_guarantee` would be false and the envelope margin optimistic by an amount nobody has bounded. Also a Fusion defect that stops both the printed output and the file channel (memo 40, finding 4): not seen again this session.

## Process

- **Commit rule (your Q5).** Every commit ran the quick subset or more; the full suite ran when staged paths left the bridge set, and each commit message says which rule applied. The tools/fy change, T5 (thread), T6 (CONVENTIONS, tools/fy, thread outputs), T7 (envelope) and T8 and T9 (thread, roadmap) all qualified: full suite 1946, 1981, 1995 (+2 fixed), 2017 passed, each with 3 skipped and the known stale ENVELOPE test deselected. The quick subset (`fy test --quick`): 828 passed in 246 s. My memo 40 estimate of 1 to 2 minutes was wrong: it is 4. T8 and T9 share one full-suite run (the tree held both) and are two commits.
- **My own mistakes.** The `fy test --quick` estimate (1 to 2 minutes; it is 4). Three shell-heredoc edits were dropped or half-applied (the `tools/fy/cli.py` edits for `--quick` and `fy cad`, and the test text for a Fusion STEP header): each was caught by a failing test or a missing attribute and redone with the editor tool or a checked script, as `CLAUDE.md` warned. The editor tool wrote `tools/fy/cli.py` with CRLF endings once; git normalises it to LF in the index, and I converted the working copy. One test I wrote (`test_validate_reports_an_address_that_does_not_resolve`) was wrong, because the name rule fired before the address check, and was rewritten; one assertion I wrote for the component box had a vacuous `or` clause and was made strict. I assumed the snapshot's values were numbers (finding 5).
- **Fusion state I left.** `Upper Arm v0` is active and **modified, unsaved**: `in_upper_arm_right_length` is `255.234699434 mm` (you had `255.2 mm`) from the push. `freyja-bridge-fixture` is open as a second tab, unmodified in content, because the `fusion` tests open it. Nothing was saved or closed.

## What changed

- **`fy test --quick`** (tools/fy): the CAD, thread, roadmap, envelope registry and conventions test files.
- **T5.** `cad/bindings/part.arm.upper_member.yaml` (rev `p1`, document `Upper Arm v0`, urn `...6NP5Ui4eTYeclyPrItX66g`, checked in Fusion first: parameters and 6061 as you listed), thread records `part.arm.upper_member` and `work.upper-arm-cad`, both `proposed`. `tools/thread/build.py`: a part's mass may be `{address, source}`; an unresolved address is the `address-unresolved` warning and claims 0 kg, with the address in the budget arithmetic and in the segment's sources (so `impact` sees it). Before the first pull the thread showed that one warning; after it, 0 warnings. Three existing tests described the old real store (no parts, 25 records, no warnings) and were updated to the new one.
- **T6.** `fy cad validate | push | pull | drift | stamp | status` (`tools/cad/ops.py`, `cli.py`; `tools/fy` has the wrapper), each with `--root`. The sidecar's STL entry records `normal_deviation_deg`, `chord_bound_mm` and `chord_guarantee` (your Q2; schema and CONVENTIONS section 8 in the same commit). `validate` and `pull` refuse a document whose id is not a `urn:` and a timeline that is not healthy. The generated `data/envelope/components/cad/upper_arm_R.yaml` and the tracked 58 KB STL (limit 5 MB). `.gitignore` gains `cad/exports/*.step`.
- **T7.** `tools/envelope/registry.py` reads `components/cad/<segment>.yaml` beside the authored file (duplicate id or name across the two is an error naming both files; a bridge id must be a part id; `revision`, `sha256`, `parameter_inputs` required per generated component and carried into the free ledger's inputs hash). `fy envelope check` names the file a component came from. Contract amendment 7: DRAFT dropped, the four open questions answered. A segment with no companion loads exactly as before (thigh_R tested). Two existing arm tests ran skin-only example checks that now met the placeholder; they pass `--no-occupied`.
- **T8.** `fy cad stamp part.arm.upper_member --note "bridge gate G6"`: stamp `thread/stamps/work.upper-arm-cad/20261027-2231.json`. This is the only real stamp.
- **T9.** `work` criterion: `tools/roadmap/evaluate.py`, the node schema, `roadmap/README.md`'s table, the text and viewer renderers (`render.py`, `viewer/app.js`). No real node edited.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G1 transport | pass | The Autodesk server at 27182, 4 tools (memo 40); every call is a verb of `cad/fusion_addin/bridge.py` through `fusion_mcp_execute`'s `script`. Your decision: the direct HTTP client meets G1. File channel kept: every result in Part B was read from it; the printed fallback was not needed. |
| G2 units | pass | Part A numbers stand (round trip 2.8e-12, mass 1.9e-16, centre of mass 1.7e-13 mm, principal moments 1.9e-14, all on the fixture). On the placeholder: `Aluminum 6061`, density 2700 kg/m^3. Against the closed form for the tube (od 30, wall 2, length 255.2347 mm): mass 0.12123873 kg, relative error 9.2e-16; centre of mass z -127.61735 mm = half the length, error about 1e-14 mm; principal moments `izz` 23.88403 kg mm^2 (error 1.4e-14) and `ixx` 670.114 kg mm^2 (error 3.2e-15), in the model frame with the axis along z. |
| G3 safe edits | pass | Part A: `marker fillet` named, rollback exact, timeline healthy. Not repeated on the placeholder (it has no feature that can fail; the bridge never edits features). |
| G4 provenance | pass | `fy cad validate` on the placeholder: ok (urn id, every parameter prefixed, no extras). Drift mutation on the fixture (Part A) and `fy cad drift` on the placeholder: no drift after the push. |
| G5 round trip | pass | Push, pull, pull: sidecar `ec067d0e...`, STL `8427f354...`, component yaml `8fa9409d...` identical across the two pulls; sidecar validates against `cad-sidecar/1` (the assembler refuses otherwise); mass in the budget through `cad/sidecars/part.arm.upper_member.json#/mass_properties/mass_kg`: `1 x 0.121239 kg, part.arm.upper_member right (mass from ...) = 0.121239 kg`. |
| G6 staleness | pass | Stamp `20261027-2231` against `snapshot#/upper_arm_right_length` (hash `d245be483398`, value `0.255234699434`). `fy thread impact --edit snapshot#/upper_arm_right_length=0.265234699434`: `work.upper-arm-cad: current -> stale`. Without the edit: `current`. Nothing written. |
| G7 envelope and frames | pass | Component `part.arm.upper_member`, revision `p1`, sha256 `ff0c57fd...`; `fy envelope check` reports its margin (-15.78 mm). Marker at ISB (0, -300, 0) lands at model (1e-15, -2e-15, -300.000) mm on the fixture (gate 0.01 mm). |
| G8 roadmap | pass | `work` evaluates `pass`, `fail`, `awaiting`, `unknown` on fixtures (20 tests): current by default, any other status fails and names it, unstamped is awaiting (and passes when unstamped is asked for), a missing work item or an unreadable graph is unknown with a `criterion-unknown` warning. |

Tolerances I chose: the drift tolerance `REL_TOL` 1e-9 (the round-trip gate, so a value that reads back within the gate is not drift), `ABS_TOL` 1e-12 (only matters at zero), the expression precision 12 significant digits (worst relative error 5e-13), the mesh rounding 1e-4 mm, the box digits 4 (the same resolution), the normal-deviation clamp 2 to 15 degrees (15 is Fusion's default; 2 keeps the tracked STL small). None was tuned toward a result.

## Timings

Measured with Fusion running, `python tools/fy cad ...` from a cold process: validate 1.2 s, status 0.9 s, drift 1.1 s, push 1.3 s, pull 2.6 s, push + pull 3.9 s. The hook adds nothing for `fy cad` (it is not in the hook); `fy thread build` and the roadmap rebuild it already runs now cover 27 records.

## Findings

1. **The placeholder sticks out of the skin by 10.97 mm** (`fy envelope check` warning, `inside_skin_mm` -10.97). The contract already says why: a segment's axis runs near its lateral skin, so a tube on the model's axis is not on the arm's centre line. It is a bridge test article; the real design needs a rule (place the part relative to the skin, not the axis).
2. **Adding the placeholder to the upper arm's registry changed two existing tests.** `tests/test_envelope_arm_bodies.py` ran two skin-only example checks that now found a registry and went INFEASIBLE; they pass `--no-occupied`. No committed envelope output changed. Any future example check on `upper_arm_R` is occupied by default.
3. **The sidecar's document version does not describe an unsaved push** (decision 2).
4. **Fusion's STEP header carries a comment before each field,** which my first normaliser did not parse (the fusion test failed, then a unit test on Fusion's own header was added).
5. **The thread hands the snapshot's values as text.** `snapshot#/upper_arm_right_length` resolves to the string `"0.255234699434"`; its hash is the hash of that text. The bridge accepts a numeric string as a number and hashes what the thread hashes. Tests: `test_the_snapshots_numeric_text_is_a_number_and_hashes_as_the_text`.
6. **`python` on the PATH of a spawned process is not the repo's `.venv`** and lacks `jsonschema`; `fy` from the shell works. Not a repo defect, but a subprocess that runs `python tools/fy` must use `sys.executable`.
7. **The quick subset takes 4 minutes, not 1 to 2** (above).
8. **The what-if reports 56 outputs would change** for any edit to the sheet's length, because every generated thread file carries the snapshot hash in its banner. True and expected; the work-status line is the one to read.

## How the envelope should consume the chord bound (not done; your instruction)

A tessellated convex surface lies inside the true one by up to `chord_bound_mm`, so every distance measured to a convex part's mesh is too large by up to that, and the margin too optimistic. A concave surface (a bore) tessellates the other way and is conservative, so only the convex faces matter, and the bridge records one number for the whole part. Proposal, in order:

1. The generated registry entry gains `chord_bound_mm` and `chord_guarantee` (from the sidecar's STL entry), next to `sha256`.
2. `occupancy.component_margins` reports `margin - chord_bound_mm` for such a component (equivalently its clearance raised by the bound), and prints the bound in the margin line.
3. When `chord_guarantee` is false the oracle cannot subtract a number: it should report the component's confidence as `unguaranteed` (a new value beside `clear` and `marginal`) and say which faces, rather than a smaller number.
4. The box primitive comes from the mesh's vertices, so it is inside the true bounding box by the same bound; the same subtraction applies when the primitive, not the mesh, is the binding geometry.
5. The skin side is separate: the skin field has its own voxel error (2 mm) and is not changed by the bridge.

For the placeholder the bound is 0.05 mm, far below the 2 mm voxel; it will matter for thin skin-following shells with a margin of a few millimetres.

## Proposed wording for `CLAUDE.md` (I edit nothing)

Commands (add under "Commands"):
- `python tools/fy cad validate [<part>] | push <part> | pull <part> | drift <part> | stamp <part> [--note T] | status` (needs Fusion running with its MCP server and the bound document active; `--root DIR` on each). Never `stamp` unless the prompt says so.
- `python tools/fy test --quick` (CAD, thread, roadmap, envelope registry and conventions tests, about 4 minutes).

Rule 1, replacing "run the full suite once before each commit": "Every commit runs `fy test --quick`. The full suite (about 17 minutes) runs before a commit when `git diff --cached --name-only` leaves the bridge set (`cad/`, `tools/cad/`, `tests/test_cad_*`, `docs/schemas/cad-*`, `docs/memos/`, `docs/briefs/`), and at every checkpoint through `fy state`. Say in the commit message which rule applied and the numbers."

## Proposed `docs/OVERVIEW.md` glossary terms (I edit nothing)

**Bound document**: a Fusion design with a binding. **Binding**: `cad/bindings/<part>.yaml`, the document's name and id, the side and the parameter list. **Sidecar**: `cad/sidecars/<part>.json`, the one home of CAD-derived quantities. **Parameter classes**: `in_` inherited from a thread address, never edited in Fusion; `dv_` design, authored in Fusion; `dr_` derived. **Push / pull / drift**: the repo's values out to Fusion by expression; Fusion's parameters, mass properties and meshes back; an inherited parameter that no longer equals its address. **CAD frame**: right-side ISB, mm, converted to the model body frame on pull. **Canonical mesh**: the STL the bridge writes, with a hash independent of Fusion's ordering. **Chord bound / guarantee**: the achieved worst-case chord error of the tessellation, and whether it covers every face.

## Nodes proposed for the `work` criterion (Joe edits them)

- `rm.v1-upper-arm-designed` (manual today, "until Stage 3 defines the part's sidecar"): `done_when: {type: work, work: work.upper-arm-cad, status: current}`. The placeholder's work item is revised under the same id when the real design starts, so the criterion stays right.
- `rm.v1-thigh-structure` and `rm.v1-forearm-structure` (same pattern, when their work items exist).
- `rm.v1-bridge-tooling` stays manual: its criterion is your sign-off on this memo's gate table.

## Questions for Joe

1. Sign off the gate table?
2. Unsaved push (decision 2): save after the push, add `unsaved_changes` to the sidecar and have `stamp` refuse on it?
3. The 10.97 mm: settle the placement convention before the real upper arm, or leave it to its brief?
4. Edit the nodes above, and the `CLAUDE.md` and `OVERVIEW.md` text?
5. May I leave the fixture open in Fusion, or should the `fusion` tests close it when they finish?
