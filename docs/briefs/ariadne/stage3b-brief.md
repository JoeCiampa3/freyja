# Stage 3b brief (for Claude Code): the CAD bridge

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `docs/envelope-component-contract.md` and `docs/schemas/envelope-oracle.md`. This brief belongs to the Ariadne track. It closes `rm.v1-stage3-brief` by existing and specifies `rm.v1-bridge-tooling`.

Tag: Delegate (Part A after Joe's prerequisite), Pair (Checkpoint A), Delegate (Part B).

## Purpose

Ariadne traces every v1 part from the sheet to a validated CAD model. Stage 3a built the system model the trace runs on. Stage 3b builds the bridge between that model and Fusion 360. The bridge does four things:

1. It pushes values the repo owns (snapshot keys, requirement values, later interface dimensions) into a Fusion design as user parameters, through thread addresses.
2. It pulls what the CAD owns back out: every parameter, the mass properties and the geometry. These go into a generated sidecar per part, which is the one home of CAD-derived quantities.
3. It feeds the part's geometry to the envelope tooling as a component, in the model body frame of its segment, so `fy envelope check` and `fy envelope free` see it.
4. It records what each CAD state consumed as a thread work item and stamp, so a changed input marks the CAD stale.

The vehicle is the upper arm, but the upper arm cannot be designed yet. Its load basis, actuator, connectors and requirement records are all still open (`rm.v1-elbow-load-basis`, `rm.v1-elbow-actuator-selected`, `rm.v1-upper-arm-connectors`, `rm.v1-upper-arm-requirements`). So the bridge is proven on two things:

- **A scratch fixture document** that Code builds, with analytically known answers.
- **A placeholder upper-arm member** that Joe models: a plain tube, recorded as a proposed part. It is a bridge test article, not a design. When the real design starts it is revised under the same id.

No load number, structural check, ROM sweep or sensitivity study is computed here. Those belong to the characterization stage (`rm.v1-upper-arm-characterized`), which reuses the envelope tooling and this bridge.

Two parts, two checkpoints:

- **Part A (T0 to T4)** proves the transport, the contracts, the units and the safe-edit loop on the fixture document. It ends at Checkpoint A.
- **Part B (T5 to T9)** runs the round trip on the placeholder, wires it into the thread and the envelope, and adds the roadmap criterion type 3a deferred. It ends at Checkpoint B.

Do not start Part B until the prompt says so.

## Gate criteria for `rm.v1-bridge-tooling`

These are stated before the tooling is built. Each is reported in the Checkpoint B memo as pass or fail with its measured numbers. The tolerances are provisional and authored here; do not adjust one to make a result pass. The gate passes when Joe signs off the memo's gate table.

**G1. Transport.** Claude Code attaches to the official Autodesk Fusion MCP server on Joe's machine. Every bridge operation runs as a function of the repo-owned Fusion-side module (`cad/fusion_addin/`), invoked through that server, never as an ad hoc script. The memo records the server's tool list.

**G2. Units.**

- Every user parameter in the fixture survives set-by-expression then read-back unchanged: relative error at most 1e-9 for lengths in mm, angles in degrees and unitless values.
- A static test proves the Fusion-side module never assigns a parameter's `.value`.
- The fixture's mass properties match their closed-form values: mass within 0.1%, centre of mass within 0.01 mm, principal moments within 0.5%. The comparison is made after conversion from Fusion's internal cm, rad and kg·cm² to the repo's mm, degrees and kg·mm².

**G3. Safe edits.** A parameter set that breaks regeneration in the fixture is reported with the names of the failed features. It is then rolled back. After rollback, every user parameter's expression equals its value before the edit, character for character, and the timeline is healthy.

**G4. Provenance.**

- Every user parameter of a bound document carries a class prefix. An unprefixed user parameter is an error.
- Every inherited parameter's value comes from its address.
- `fy cad drift` fails when an inherited parameter has been changed in Fusion. A mutation test in the fixture proves it.

**G5. Round trip on the placeholder.**

- `fy cad push` then `fy cad pull` produce a sidecar that validates against `cad-sidecar/1`.
- Two pulls with no change in between give byte-identical sidecar and STL.
- The placeholder's mass enters `seg.upper_arm`'s budget through an address into the sidecar, not through a typed number.

**G6. Staleness.**

- The placeholder's work item is stamped against the addresses it consumed.
- An in-memory edit of one consumed input (`fy thread impact --edit snapshot#/<upper-arm length key>=<value>`) reports the work item as stale.
- Reverting it reports current again.

**G7. Envelope and frames.**

- The placeholder flows into the envelope as a component with id equal to its part id, plus a revision and a geometry hash.
- `fy envelope check` on the right upper arm reports a margin for it.
- In the fixture, a marker at ISB point (0, -L, 0) lands at model-frame point (0, 0, -L) within 0.01 mm.

**G8. Roadmap.** The `work` criterion type evaluates `pass`, `fail`, `awaiting` and `unknown` correctly on fixtures.

## Concepts

**Bound document.** A Fusion design that the bridge reads or writes. Each one has an authored binding file, `cad/bindings/<part id>.yaml` (schema `cad-binding/1`), holding:

- the part id and its `revision` (a string Joe sets);
- the Fusion document's name and its stable id;
- the side (`right`; see Frames);
- the chord tolerance for mesh export (default 0.05 mm);
- the component's `clearance_mm` for the envelope;
- the parameter list.

A Fusion document with no binding is invisible to the bridge. The fixture's binding lives under `tests/fixtures/cad/`.

**Parameter classes.** Every user parameter of a bound document is in exactly one class, named by its prefix:

| Class | Prefix | Owner | Rule |
|---|---|---|---|
| Inherited | `in_` | the repo | Pushed one way from a thread address, never edited in Fusion. The binding gives its address and unit. Its name is `in_` plus the address with `snapshot#/` removed, every other `#`, `/`, `.` and `-` replaced by `_`. Example: `snapshot#/upper_arm_right_length` becomes `in_upper_arm_right_length`; `req.elbow.flex_max#/value` becomes `in_req_elbow_flex_max_value`. |
| Design | `dv_` | Fusion | Authored in Fusion. Code may set one only inside an explicit task, through snapshot and rollback. The sidecar records each one's expression and value on every pull. Named `dv_<part short>_<quantity>`. |
| Derived | `dr_` | Fusion | Defined by an expression of other parameters. Never set by the bridge. |

Two addresses that map to one name is an error. There are no unit suffixes in Fusion names, because Fusion carries the unit in the expression; the sidecar's keys carry units. Model parameters (sketch and feature dimensions) are not tracked. Any dimension that matters must reference a user parameter, which is Joe's modelling rule and not something the bridge checks.

**Expressions, not values.** The bridge writes a parameter only by setting its expression, with an explicit unit: `"312.4 mm"`, `"62 deg"`, or a bare number for unitless. It reads both the expression and the evaluated value. Fusion stores lengths internally in cm, angles in rad and inertia in kg·cm², regardless of document units. One conversion module in `tools/cad/` is the only place those factors appear.

**Snapshot and rollback.** Before any write, the bridge captures every user parameter's expression. After the write it recomputes and checks timeline health: every timeline object's health state, and the names of failed features. On failure, or when the task says so, it restores the captured expressions, recomputes and verifies that they are equal and the timeline is healthy. The capture lives in memory for the command's duration, and in a file outside the repo when a command spans calls. It is never committed.

**Sidecar.** `cad/sidecars/<part id>.json`, schema `cad-sidecar/1`. It is generated by `fy cad pull`, carries the CONVENTIONS section 4 banner keys, and has no timestamps. It holds:

- **Identity.** The part id, revision, side and the binding's hash.
- **Document.** The Fusion document's name, id and version number.
- **Parameters.** Every user parameter as `{name, class, expression, value, unit}`; for inherited ones, their address and that address's hash at push.
- **Drift.** Inherited parameters whose Fusion value differs from their address's current value. An empty list means clean.
- **Timeline.** Healthy or not, with failed feature names.
- **Mass properties.** Material name and density, `mass_kg`, `com_mm` and `inertia_kgmm2` (about the centre of mass, six components), all in the model body frame of the owner segment, with the calculation accuracy used.
- **Exports.** The STL's path, canonical hash, chord tolerance and triangle count; the STEP's path and normalised hash.
- **Component.** The envelope registry entry for this part.
- **Consumes.** The addresses the CAD state consumed, with their hashes. This is what the work item's stamp records.

**Frames.** CAD is modelled in the ISB segment frame of the right side, in millimetres:

- origin at the proximal joint centre;
- x anterior, y proximal (up in the neutral pose), z lateral (right);
- for the humerus, y runs from the elbow joint centre to the glenohumeral centre.

The bridge converts to the owner's model body frame on pull (x anterior, y left, z up, origin at the proximal joint centre, axes parallel to the world at q = 0), using `tools/envelope/registry.isb_to_segment` and never a second copy of that rotation. Left-side parts are not modelled: a bilateral part is designed once on the right and carries `sides: [left, right]` in its thread record. The bridge refuses `side: left`.

**Mesh export.** The bridge exports the STL from Fusion to a temporary file at the binding's chord tolerance. It reads it, converts it to the model body frame and writes the tracked STL itself with a fixed header, so the bytes are deterministic. The canonical mesh hash is the sha256 of the vertices rounded to 1e-4 mm and the faces in sorted order. It does not depend on Fusion's byte order.

**STEP.** STEP is the FEA hand-off format, and FEA is out of scope. STEP headers carry a timestamp, so the STEP export is gitignored. The sidecar records the hash of the file with its `FILE_NAME` header timestamp blanked. That leaves room for a later `fea-case/1` record to pair a STEP with its load cases.

**What the repo can and cannot reproduce.** The `.f3d` lives in Autodesk's cloud, not in git. The sidecar pins the document id and version, the full parameter set and the geometry hash. The tracked STL is the geometry of record for the envelope. Reproducing the CAD itself depends on Fusion's version history. State this in the memo plainly; do not paper over it.

**Thread binding of a CAD part.** A CAD part is a thread `part` record plus a `work` item:

- The part's `mass` gains a second form, `{address: <sidecar address>, source: <text>}`. It resolves at build to the sidecar's `mass_kg`, so the budget never holds a typed copy.
- The work item has `of: <part id>`, `mode: assisted`, `output: cad/sidecars/<part id>.json`, and `consumes` equal to the binding's inherited addresses.
- `fy cad stamp <part id>` calls the thread's stamp function with that list. It refuses when the sidecar shows drift, an unhealthy timeline, or consumed hashes that differ from the current ones.

## Layout

| Path | Holds | Kind |
|---|---|---|
| `cad/fusion_addin/` | the Fusion-side module: pure functions, JSON in and JSON out, run inside Fusion through the MCP server | authored |
| `cad/bindings/<part id>.yaml` | one binding per bound document | authored |
| `cad/sidecars/<part id>.json` | one sidecar per part | generated, tracked |
| `cad/exports/<part id>.stl` | the canonical mesh in the model body frame | generated, tracked; stop and ask above 5 MB |
| `cad/exports/<part id>.step` | the FEA hand-off export | generated, gitignored |
| `data/envelope/components/cad/<segment>.yaml` | `components/1` entries built from sidecars | generated, tracked |
| `tools/cad/` | the library; `fy cad` calls it | authored |

## Out of scope

- **The upper arm's design.** Real geometry, requirement records, interface records, connector decisions, the load basis and actuator selection.
- **Analysis.** Any load number, structural screening, ROM sweep, sensitivity study, clearance heat map or FEA run. The envelope's existing `check` is run once, for G7.
- **Fall protection.** The fall design basis is `rm.v1-fall-design-basis` (decision 0037). Joe's input to it is in the follow-ups below; nothing here implements it.
- **Feature-level edits.** Creating or editing features in any bound document, except the scratch fixture that Code builds.
- **The left side's CAD frames.** Mass closure and loads rerun on CAD masses (`rm.v1-ariadne-mass-closure`). An in-Fusion chat palette. The thread viewer.
- **Inputs owned elsewhere.** Any edit to the model, the template, `pre_processor` or the sheet. Any envelope behaviour other than T7's registry alignment.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, including rule 10 on coupled tasks.

- **Fusion is Joe's live application.** Open, create or write only these: the scratch fixture document Code creates in T3, under a name starting `freyja-bridge-fixture`; and the placeholder document Joe names at Checkpoint A, through its parameters only. Never open or modify any other document. If a tool would save a new version of a document you were not told to touch, stop.
- **Tests that need Fusion** carry the pytest marker `fusion` and are deselected by default, so `fy test`, the hook and any machine without Fusion stay green. Run them explicitly in T3, T4 and T6 and record their results in the memo. Everything else (conversions, naming, schemas, sidecar writing, drift logic, canonical hashing, frames) is tested without Fusion on recorded fixtures.
- **Dependencies.** None new on the repo side without asking. `tools/cad/` must not import `mujoco` or `adsk`. The Fusion-side module imports only `adsk` and the standard library.
- **Determinism.** Sorted keys, LF endings, repo-relative paths, no timestamps in tracked files.
- **Findings stop the work.** Report the measured number and stop, rather than change a tolerance, a frame or a rule to make a gate pass. Findings include: a tolerance missed; a Fusion export that is not deterministic after canonicalisation; a frame disagreement; the official server unable to run Python inside Fusion.
- **New tests' cost.** Keep the default suite's added time under about 15 s, and report it.

Stop and ask before:

- adding a record kind, relation, address source or parameter class not in this brief;
- touching a Fusion document other than the two above;
- creating any thread record as `active`;
- stamping a real work item, except in T8 when the prompt says so;
- adding a dependency;
- making any check a gate.

## Amendments to CONVENTIONS (land with T1)

1. **Section 2.** Replace the `cad/` row with the layout above. Add a `tools/cad/` row.
2. **Section 3.** Replace the sentence "Fusion user parameters cannot contain dots, so the CAD bridge maps `.` to `_` on the Fusion side only" with a **CAD terms** paragraph defining:
   - bound document, binding and sidecar;
   - the three parameter classes and their prefixes;
   - the name rule for inherited parameters;
   - expressions with explicit units;
   - snapshot and rollback.
3. **Section 3.** Add the CAD frame rule (ISB, right side, origin at the proximal joint centre, millimetres; converted to the model body frame at the bridge; the left side by mirror only).
4. **Section 8.** Add the binding and sidecar formats, one short example each. Add the part record's second `mass` form, and amend `thread-record-1.schema.json` in the same commit.
5. **Section 9.** Claude Code:
   - writes only expressions, never values;
   - never edits features in a bound document;
   - creates geometry only in scratch fixture documents;
   - sets a `dv_` parameter only inside a task that says so, through snapshot and rollback.
6. **`roadmap/README.md` and `docs/schemas/roadmap-node-2.schema.json`.** The `work` criterion type (T9), with a row in the criterion table.
7. **`docs/envelope-component-contract.md`.** Drop "DRAFT". Align its fields with the sidecar's component entry and record the answers to its four open questions:
   - the format is this brief's;
   - the left side is mirrored, never modelled;
   - joint-angle-dependent poses stay with `poses_file` and the simulation;
   - the bridge regenerates a component on pull, and staleness after a snapshot change is the work item's status.

## Part A

**T0. Baseline and transport.**

1. Run `fy test` and `fy state`, and record `params/snapshot.csv`'s sha256 prefix. If the snapshot or the model changes while you work, stop at the next commit boundary and write the memo with the new hash.
2. Confirm that Claude Code and Fusion run on the same machine, and that the Fusion MCP server is reachable from this session.
3. List the server's tools, with one line each on what it does. Find the tool that runs Python inside Fusion, and confirm a script it runs can import a module from the repo's `cad/fusion_addin/` path.
4. Confirm the snapshot holds the upper arm's length and joint-centre keys under `pre_processor`'s naming, and list them.
5. Check the envelope cache's segment name for the right upper arm (volume-extractor brief 8).

Commit nothing. Stop at T0 if the server is unreachable, cannot run Python inside Fusion, or cannot import from the repo path; report what it can do instead. The fallback (a community bridge) is Joe's decision, not yours.

**T1. Contract.** Write these schemas in `docs/schemas/`:

- `cad-binding-1.schema.json`
- `cad-sidecar-1.schema.json`

Land the CONVENTIONS amendments 1 to 5 in the same commit. Tests: each schema accepts one valid example and rejects one example of each schema-level error, including an unprefixed parameter, a duplicate name, an inherited parameter without an address, and `side: left`.

**T2. Library, without Fusion.** In `tools/cad/`:

- binding load and validation;
- inherited-parameter resolution through `tools/thread`'s address resolver (imported, not copied);
- the name rule;
- the unit conversion module;
- expression formatting;
- drift comparison;
- the frame conversion through `registry.isb_to_segment`;
- the mass-property transform to the model body frame (rotation of the inertia tensor, translation of the centre of mass);
- canonical mesh writing and hashing;
- STEP header normalisation;
- the sidecar writer;
- the component entry builder.

The component's required bounding primitive is the axis-aligned box of the converted mesh in the model body frame, with `clearance_mm` from the binding.

Tests:

- known-answer conversions both ways for every unit used;
- a rotated, offset tube's inertia transformed and checked against the parallel-axis theorem;
- the name rule on every address form, including the collision error;
- the drift logic;
- mesh canonicalisation (the same mesh in two vertex orders hashes the same);
- the ISB marker case of G7 on synthetic points;
- a mutation test for each check-like function (a broken conversion factor, a swapped axis, a missing prefix each make a test fail).

**T3. Fusion-side module and fixture.** In `cad/fusion_addin/`, write the bridge's verbs as pure functions that return JSON:

- `doc_info`
- `read_params`
- `set_expressions` (with recompute and the health report)
- `capture` and `restore`
- `physical_properties` (at the highest accuracy setting the API offers)
- `export_stl`
- `export_step`

No other function writes to a document. Then create the scratch fixture document `freyja-bridge-fixture`. It holds:

- a parameterised tube of 6061 aluminium in the ISB frame, its axis along -y from the origin, with `in_` (length), `dv_` (outer diameter, wall) and `dr_` (inner diameter) parameters;
- one unitless and one angular user parameter, the angle driving a feature;
- a small marker body at (0, -L, 0) for the frame test;
- its binding under `tests/fixtures/cad/`, with addresses into a fixture snapshot.

Tests (`fusion` marker):

- G2's round trip on every parameter;
- G2's mass properties against the closed form for the tube (the marker body excluded, or included in the closed form);
- the static `.value` check.

**T4. Safe edits and drift in the fixture.** Tests (`fusion` marker):

- G3: set a wall thickness at or above the outer radius, see the failure reported with the feature names, roll back and verify;
- G4's drift mutation: change an inherited parameter in Fusion, see `drift` fail, push, see it clean;
- the unprefixed-parameter error: add one, see validation fail, remove it.

Restore the fixture to its committed binding state at the end.

**Checkpoint A.** Write the memo per `CLAUDE.md` rule 6. Include:

- the T0 inventory and the server's tool list;
- what was built;
- G1 to G4 with their numbers;
- the measured time of one capture, set, recompute and restore cycle, and of one physical-properties call;
- the tests added and their runtime, default and `fusion`;
- every finding;
- the questions for Joe.

Ask Joe to create the placeholder document (below) and to give its name. Run `fy state` and stop.

## Prerequisite for Part B (Joe)

Create a Fusion design for the placeholder upper-arm member in the right humerus's ISB frame (origin at the shoulder joint centre, y up toward it from the elbow, x anterior, z lateral). It is a tube from the origin along -y to the elbow joint centre, of 6061 aluminium, with exactly these user parameters:

- `in_<upper arm length key>`, with the name per the rule, from the key T0 listed;
- `dv_uam_od` and `dv_uam_wall`, any plausible values;
- `dr_uam_id = dv_uam_od - 2 * dv_uam_wall`.

The tube's length must reference the inherited parameter. Tell Code the document's name.

## Part B

**T5. Binding and records.** Write the following:

- `cad/bindings/part.arm.upper_member.yaml`, revision `p1` (placeholder 1);
- the thread records, all `status: proposed`:
  - `part.arm.upper_member`: purpose states it is a bridge test article to be revised when the real design starts; `housed_in: seg.upper_arm`; `sides: [left, right]`; `category: structure`; `mass` in the address form pointing at `cad/sidecars/part.arm.upper_member.json#/mass_properties/mass_kg`;
  - `work.upper-arm-cad`: `of: part.arm.upper_member`, `mode: assisted`, the sidecar as `output`, and `consumes` from the binding.

Run `fy thread build` and confirm the budget row shows the arithmetic and the address. Before the first pull, the address does not resolve; that is `address-unresolved`, a warning, and expected.

**T6. Commands.** Add these commands, each taking `--root DIR`. `tools/fy` gets a thin wrapper only.

| Command | Does |
|---|---|
| `fy cad validate [<part id>]` | Checks the binding against the schema and the bound document's parameters against the binding: every prefix, every inherited parameter present, no extra user parameters. |
| `fy cad push <part id>` | Resolves the inherited addresses, captures, sets the expressions, recomputes and checks health; on failure restores and exits 1. |
| `fy cad pull <part id>` | Reads parameters, mass properties and exports; writes the sidecar, the STL and the generated component registry. Refuses on an unhealthy timeline. |
| `fy cad drift <part id>` | Inherited values in Fusion against the current addresses; exits 1 on drift. Reads only. |
| `fy cad stamp <part id> [--note TEXT]` | Stamps the work item through the thread's stamp function, refusing as described in Concepts. |
| `fy cad status` | One line per binding: revision, document version, drift, timeline, work status. |

Run G5 on the placeholder: push, pull, pull again, and compare bytes. Tests without Fusion run every command on recorded fixture responses. Tests with the `fusion` marker run push and pull on the fixture document.

**T7. Envelope alignment.** Make the envelope's registry loader read `data/envelope/components/cad/<segment>.yaml` beside the authored file, with this behaviour:

- a duplicate component `id` or `name` across the two is an error;
- `id` must match the part-id form when it comes from the bridge;
- the generated file carries `revision`, `sha256` (the canonical mesh hash) and `parameter_inputs` (the sidecar's consumes hash) per component.

Existing envelope outputs must reproduce exactly. Run `fy envelope check` on the right upper arm with the placeholder as a designed component, and report the margin, the binding point and the confidence. Land amendment 7.

**T8. Staleness.** When the prompt authorizes it, run `fy cad stamp part.arm.upper_member --note "bridge gate G6"`. Then run `fy thread impact --edit snapshot#/<length key>=<value + 10 mm>`, confirm `work.upper-arm-cad` reports stale, and run it without the edit to confirm current. No real edit to the snapshot is made.

**T9. Roadmap criterion type `work`.**

- Fields: `work` (a work id) and `status` (one of the thread's work statuses; default `current`).
- It passes when `thread/graph.json` reports that status for that work item.
- `awaiting` when the work item exists but is unstamped. `unknown` when the work item is missing or the graph is unreadable. `fail` otherwise.
- The evaluator reads `thread/graph.json` and never builds the thread. Add the file to the node's referenced files.

Tests: each outcome on fixtures. Edit no real node. In the memo, propose which nodes should adopt it; Joe edits them.

**Checkpoint B.** Write the memo per `CLAUDE.md` rule 6. Include:

- what changed;
- the gate table G1 to G8, with numbers;
- timings (push, pull, the hook's added time if any);
- the proposed `CLAUDE.md` command lines and `docs/OVERVIEW.md` glossary terms (you edit neither);
- the nodes proposed for the `work` criterion;
- every finding;
- the questions for Joe.

Run `fy state` and stop.

## Performance

`fy cad push` plus `fy cad pull` on the placeholder take under 60 s. `fy cad validate` and `fy cad status` take under 5 s with Fusion running. Report the measured times either way.

## Decisions this brief makes (Joe approves them by committing it)

1. The official Autodesk Fusion MCP server is the transport. The repo owns every bridge verb in `cad/fusion_addin/`.
2. Three parameter classes with the prefixes `in_`, `dv_` and `dr_`, and the inherited-name rule above.
3. Parameters are written by expression with explicit units, never by value.
4. CAD is modelled in right-side ISB segment frames and converted to model body frames at the bridge. The left side is mirrored, never modelled.
5. The sidecar is the one home of CAD-derived quantities. A part's mass may be an address into it.
6. The STL is tracked as the canonical mesh, written by the bridge. The STEP is gitignored, with a normalised hash.
7. The placeholder `part.arm.upper_member` revision `p1` is a proposed bridge test article, not a design.
8. The envelope's component registry gains a generated companion file per segment, written by the bridge.
9. The `work` roadmap criterion type.

## Follow-ups carried for later briefs and records (not this session)

- **For decision 0037 (fall design basis), from Joe's discussion of Oct 26–27.** The arm's fall protection follows a hierarchy, in this order:
  1. bypass the expensive parts with secondary load paths that engage under overload deflection (hard stops, overload shoulders, shell-to-structure contact);
  2. limit torque into drivetrains (backdrivable or controlled-yield joints);
  3. absorb energy over a defined stroke with damped compliance;
  4. let cheap parts take what remains.

  Bearings are checked against their static rating C0 for rare impacts. A shoulder backdriving to bleed momentum requires a bus clamp or brake resistor on the 48 V bus. The three arm cases Joe named:
  - arms outstretched to catch, using the elbow's extension hard stop as the lock;
  - an arm trapped under the torso, accepted as repairable damage;
  - a lateral fall onto the shoulder, where the shell must bottom out on torso structure before the pitch bearing takes thrust.
- **For 0037 and the thread, Joe's clavicle observation.** A segment's fall protection need not sit in that segment. Compliance in the clavicle could protect the shoulder in a lateral fall. The open question is a convention for parts that serve another segment without breaking modularity. One candidate is that such a part is housed in its own segment and reaches the protected one only through an interface record.
- **For 0020 (upper-arm connectors).** The connector record should carry a compliance stroke and an overload-stop provision, alongside the bolt circle and clocking.
- **For 0019 (structural method).** Joe's discussion set static SF of at least 2 on yield at peak stress including stress concentration, under the actuator-peak case; fatigue SF of at least 1.5 against fatigue strength for swing and payload cycling; and an advisory deflection of at most 1 mm at the hand under the design payload. These are inputs to the record, not decided here.
- **For 0008 (elbow load basis).** Payload is 1.0 kg at full extension (design) and 0.5 kg (nominal). The speed requirement is minimum-jerk trajectories from the literature, checked as a trajectory on the actuator's torque–speed curve with 70% headroom, robot inertias from the snapshot, and each paper's movement onset and end definitions recorded. The elbow's ROM ceiling is Soucie's, with Morrey's arc for loads; Magermans shows activities of daily living reaching about 157 degrees, so the mechanism must reach the full ceiling.
- **Answer to memo 19's Q5.** 3b writes part and work records first, for the upper arm's placeholder.
