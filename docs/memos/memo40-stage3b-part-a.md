STATE: base 7fdd5b8d16f7 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 1934/1938 | dirty no

# Memo 40: Stage 3b Part A, the CAD bridge transport, contracts and safe-edit loop (T0 to T4)

Brief: `docs/briefs/ariadne/stage3b-brief.md`. Commits: T1 `562d2de`, T2 `11f2f5d`, T3+T4 `7fdd5b8` (coupled, one commit; see Process). Written for Joe, who decides the questions at the end.

## Decision summary

- **What it means for Freyja.** The bridge's foundations work against your live Fusion. A repo-owned module (`cad/fusion_addin/bridge.py`) pushes parameters by expression, reads mass properties and exports, rolls back a breaking edit with the failed feature named, and detects an inherited parameter changed by hand. G1 to G4 all pass on the scratch fixture. Nothing touched your documents except the fixture, which now sits in the root of your **Default Project** (see Q1).
- **The numbers that matter.**

| Number | Value | Reference |
|---|---|---|
| Parameter round trip, worst relative error over 5 parameters and 17 awkward values | 2.8e-12 | gate 1e-9 |
| Tube mass against closed form | 1.9e-16 relative | gate 0.1% |
| Tube centre of mass against closed form | 1.7e-13 mm | gate 0.01 mm |
| Tube principal moments against closed form | 1.9e-14 relative (worst) | gate 0.5% |
| Marker at ISB (0, -300, 0) lands at model | (1e-15, -2e-15, -300.000) mm | gate 0.01 mm |
| Breaking edit (wall 15 mm and 16 mm): failed feature reported, rollback exact | `marker fillet`; 0 expressions differ, timeline healthy | gate: names, then character-for-character equality |
| One capture, set, recompute, restore cycle; one physical-properties call | 0.45 s; 0.10 s | no gate; the 60 s budget is for push plus pull |

- **Decisions for you.** (1) Is the fixture in Default Project acceptable, or should it live elsewhere? Recommended: leave it, it is ours and Part B reuses it. (2) Accept the tessellation rule in finding 2 (chord tolerance turned into a normal deviation because Fusion ignores its own surface-deviation setting)? Recommended: accept. (3) Register the Fusion server with Claude Code as an MCP client, or keep my direct HTTP client? Recommended: keep the client, it is what the tests and `fy cad` use. (4) The placeholder document, below.
- **What would change the conclusion.** Finding 4 (script output capture) is a live defect of the server I could not reproduce on demand. If it recurs in Part B and the file channel fails too, G1 is at risk.

## Process

- **T3 and T4 are one commit** because they share one test file, one transport and one fixture builder (CONVENTIONS section 9, rule 10). T1 and T2 are separate commits as the brief says.
- **Test runs.** The full suite ran once before the T3+T4 commit: 1933 passed, 3 skipped, 14 deselected, 1082 s. I deselected the one known stale test (`test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce`: run records at model `cfa2e0743e83`, model now `1ceee2452e18`; you said leave it). T1 and T2 were not given a full run (schemas, docs and a new package only; the focused runs are in their commit messages). `fy state` runs the whole suite itself, so it costs the same 18 minutes again.
- `fy state` after the commits: 1934 passed, 1 failed (the known stale test), 3 skipped.
- Added test time in the default suite: `tests/test_cad_*.py` is 154 tests in 4.1 s. The 22 `fusion` tests take 20.9 s and are deselected unless `--fusion` or `-m fusion` is given.

## T0: inventory

- Fusion 360 build 2705.1.30, Python 3.14.0 inside it, on this machine. Server at `http://127.0.0.1:27182/mcp` (MCP over plain HTTP, session id in the `MCP-Session-Id` header). Port 27182 is owned by `Fusion360.exe`.
- **Server tool list (4 tools).** `fusion_mcp_read`: read-only queries (licensing, projects, documents, API documentation, screenshot, active command). `fusion_mcp_execute`: dispatcher on `featureType`; `script` runs Python in the active design (optional `readOnly`, enforced by Fusion), plus document open, close and save, `editImage` and `purchase`. `fusion_mcp_update`: `undo` and `redo` only. `fusion_mcp_electronics_read`: Electronics data, unused.
- A script run through `script` imports a module from `cad/fusion_addin/` by putting that path on `sys.path` (proved with a throwaway module, deleted). Every bridge call is `bridge.<verb>(**args)` sent that way and nothing else.
- Snapshot upper-arm keys (metres): `upper_arm_right_length` 0.255234699434, `upper_arm_left_length` the same, `upper_arm_right_jpos_z` 0, `upper_arm_right_pos_x/y/z` 0.0138137 / -0.192329 / -0.0775691 (body position in the parent, not a joint centre). The inherited parameter for the placeholder is `in_upper_arm_right_length`. Snapshot sha256 prefix `492fe816e6d8`, unchanged through the session.
- Envelope segment name `upper_arm_R` (`arms.py` `SEG_KEY`, cache `upper_arm_R.npz` present). `data/envelope/components/` holds only `thigh_R.yaml`.

## What was built

- **T1.** `cad-binding-1` and `cad-sidecar-1` schemas, the second form of a part's `mass` (`{address, source}`) in `thread-record-1`, and CONVENTIONS amendments 1 to 5 (layout rows, CAD terms, CAD frame, the two formats with examples, rule 12). 46 rejection cases, each proven to be rejected.
- **T2.** `tools/cad/`: units (the only home of the factors), names, binding, params, drift, frames, mesh, step, sidecar, component. 80 tests with mutation tests: a broken unit factor, a removed prefix rule, a loosened drift tolerance, a swapped frame axis and a wrong parallel-axis mass each make a known-answer test fail. A static test keeps unit factors out of every other module.
- **T3.** `cad/fusion_addin/bridge.py`: `doc_info`, `read_params`, `timeline_health`, `capture`, `physical_properties`, `max_curvature_radius`, `export_stl`, `export_step`, and the only two writers, `set_expressions` and `restore` (user-parameter expressions only; `dr_` never; classes outside `allowed_prefixes` refused before anything is written). Every verb takes `expect_name` and refuses another document. `tools/cad/transport.py`, `massprops.py`. The scratch document `freyja-bridge-fixture`: a 6061 tube along -y (`in_fixture_length`, `dv_fx_od`, `dv_fx_wall`, `dr_fx_id`), a cube marker at (0, -L, 0), a revolved sector driven by `dv_fx_angle`, unitless `dv_fx_ratio`, and a fillet on the marker with radius `dr_fx_id / 100` (finding 5). Binding and snapshot fixtures in `tests/fixtures/cad/`.
- **T4.** Tests only, plus `drift.check` and the fixture builder's `add_user_parameter` and `remove_user_parameter` (fixture documents only, because the bridge has no verb that adds a parameter).

## Gates

- **G1 transport.** Pass. Every call in the 22 `fusion` tests goes through the server's `script` tool as a function of `bridge.py`. Tool list above. Claude Code itself is not registered as an MCP client of this server (finding 8).
- **G2 units.** Pass. Round trip worst error 2.8e-12 (`in_fixture_length`, limited by the 12 significant digits of the expression), the others 1e-16 to 7e-14. Static test: no Fusion-side module assigns `.value`, tested on the AST with a mutation set (`p.value = 1`, `+=`, annotated, `setattr`). Mass properties: table above, tube alone at `veryhigh` accuracy, converted from cm, rad and kg cm^2; the marker and sector are excluded by asking for the tube body.
- **G3 safe edits.** Pass. `dv_fx_wall` = 15 mm and 16 mm: `ok` false, `failed_features` `["marker fillet"]`, Fusion's own text kept (zero radius: "could not be created at the requested size"; negative: "Cannot create fillet with a negative value"), rolled back, `equal` true, 0 differing expressions, timeline healthy; the whole expression set compared as strings.
- **G4 provenance.** Pass. An unprefixed parameter is a validation error (added, seen, removed); an extra `dv_` parameter and a missing one are also reported. The inherited value comes from its address (300 mm from 0.3 m). Mutation: set `in_fixture_length` to 310 mm in Fusion, `drift` reports `in_fixture_length` 310 against 300, push, clean.

## Findings

1. **Baseline.** One known failing test, stale run records against the rebuilt model (above). Not mine.
2. **Fusion ignores its own surface-deviation setting.** STL triangle count for the tube is identical for a chord of 0.005 mm and 0.5 mm at normal deviations of 2, 5 and 15 degrees (21600, 3744, 1764 triangles); it changes only with the normal deviation. The binding's `chord_tolerance_mm` therefore cannot be passed through. I added a rule: `normal_deviation_deg(chord, r_max)` = 2 acos(1 - chord / r_max), clamped to 2 to 15 degrees, where `r_max` is the largest analytic arc radius from the new `max_curvature_radius` verb (the largest radius is the strictest case). Tube: 9.36 degrees for 0.05 mm. Free-form surfaces get the 15 degree default and no chord guarantee. Also: Fusion's `normalDeviation` is in degrees (default 15), not radians; my first call passed radians and produced 298,112 triangles (14.9 MB, over your 5 MB stop).
3. **Fusion returns inertia about the world origin as matrix entries.** Principal moments come about the centre of mass. The sector's recorded xz product has the sign of minus the integral (centre of mass has positive x and z, Fusion reports -0.016179 kg cm^2, closed form 0.016179), so the tensor convention matches MuJoCo's and `frames.py`. Pinned in `tests/test_cad_massprops.py`.
4. **The server's script output capture stopped working mid-session.** After a long run of script calls in one Fusion session (well over a hundred), every script still ran but returned an empty message (`print` goes to a `_NsSanitizedWriter` that returned nothing; exceptions still came back). I could not find the trigger: it began during a run that also issued a deliberately refused write from a read-only script, which I suspect but did not prove. I added a second channel: each call also writes its JSON result to a temporary file outside the repo and the client reads that first. This defect is in a path you use.
5. **The brief's G3 case does not break regeneration in a plain tube.** A wall of 15 mm or 16 mm gives an inner diameter of 0 or -2 mm and Fusion keeps the timeline healthy. I made the failure real by design: a fillet on the marker with radius `dr_fx_id / 100`, which fails at diameter 0 and below. The fixture's test is G3 as intended (an edit that breaks regeneration), through a different feature than the brief names.
6. **A JSON Schema cannot say "two parameters share a name".** The schema rejects identical duplicate entries only; name uniqueness and the inherited-name rule are in `binding.check` (tested).
7. **Binding field not in the brief: `address_unit`.** The snapshot holds metres; the binding needs the unit at the address as well as the Fusion unit.
8. **Claude Code is not an MCP client of this server.** `claude` is not on this shell's path and the session lists no Fusion tools; the repo's client talks to the endpoint directly. G1 as worded ("attaches to") is met by that client, not by a registered MCP server.
9. **`dataFile.id` is a local file path until Fusion finishes syncing**, then `urn:adsk.wipprod:dm.lineage:...`. A local path must not enter a tracked file. `fy cad validate` will refuse a document whose id is not a `urn:`. Document names carry no version suffix (`freyja-bridge-fixture`).
10. **What the repo can and cannot reproduce.** The `.f3d` lives in Autodesk's cloud, not in git. The sidecar will pin the document id and version, the full parameter set and the geometry hash; the tracked STL is the geometry of record. Reproducing the CAD itself depends on Fusion's version history. Nothing in this memo changes that.
11. **`fy state` costs 18 minutes** because it runs the suite. Calling it twice per part (checkpoints only) is my plan.
12. **Reading `Default Project`:** it holds 14 of your documents; I listed their names to find the root folder and opened none. One is called `Untitled`; it is yours and I did not touch it.

## Answer to your question on a test subset

The suite is 1,900 tests and 18 minutes, dominated by the sim, gait and envelope files, none of which this brief touches. A subset is safe for iteration (it is what I ran per task) but not for the commit gate, because the whole suite compares committed outputs with fresh builds, and a thread, schema or `conftest.py` change can fail files that look unrelated. Proposal: add `fy test --quick` that runs the CAD, thread, roadmap, registry and conventions files, about 1 to 2 minutes, for use between commits, and keep the full run before each commit. I have not built it; it touches `tools/fy`. Say if you want it.

## Questions for Joe

1. The fixture `freyja-bridge-fixture` is saved in the root of **Default Project** (two versions). Keep it there? It is also fine to move it to a folder you name.
2. Accept the tessellation rule in finding 2?
3. Register the server with Claude Code as an MCP client, or keep the direct client (finding 8)?
4. **The placeholder.** Please create it as the brief's prerequisite says: a Fusion design in the right humerus's ISB frame (origin at the shoulder joint centre, y up toward it from the elbow, x anterior, z lateral), a 6061 tube from the origin along -y to the elbow, with exactly these user parameters: `in_upper_arm_right_length` (the name per the rule, from the key `upper_arm_right_length`), `dv_uam_od` and `dv_uam_wall` (any plausible values), `dr_uam_id = dv_uam_od - 2 * dv_uam_wall`. The tube's length must reference the inherited parameter. Give me the document's name. Open and active in Fusion when Part B starts, saved once so it has a `urn:` id.
5. The fixture's sector and marker bodies exist for the tests only; nothing in Part B depends on them.
