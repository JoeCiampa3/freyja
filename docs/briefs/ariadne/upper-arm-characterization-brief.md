# Upper-arm characterization brief (for Claude Code): the schema, geometry, loads and file leaves of rm.v1-upper-arm-characterized

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `decisions/0045-upper-arm-characterization-contract.md` (all of it: this brief implements it and adds nothing to it except where "Decisions this brief makes" says so), `decisions/0008-elbow-load-basis.md` (D2 to D7 and its Amendments), `decisions/0042-arm-joint-anchors.md` (D1 to D5 and its Amendments), memo 59 (finding 7 and the shoulder row of its table), memo 60, `docs/schemas/envelope-oracle.md` and `tools/envelope/README.md`. This brief belongs to the Ariadne track. It specifies four roadmap leaves, in this order, each closed by Joe's sign-off of its own checkpoint memo: `rm.v1-upper-arm-char-schema`, `rm.v1-upper-arm-geometry-extracted`, `rm.v1-upper-arm-loads-computed`, `rm.v1-upper-arm-char-file`.

Tag: Delegate, all four groups. End each session with a few lines for Joe (the decision summary of `CLAUDE.md` rule 6, kept short); the full memo is for the next Code session.

## Purpose

The upper arm is the first part through the Ariadne loop. Its characterization file is the loop's input end: what the world and the task demand of the segment, the room it has, the range it moves through and where its interfaces sit, stated in the right-side CAD frame with every number traceable to an address and every position carrying its anchor's error bar. The requirement records (`rm.v1-upper-arm-requirements`) are authored from it, and every later segment is characterized by the same schema and the same library. So the library is segment-generic and the upper arm is its first instance (adr-0045 D2).

## Run order and what can run now

Groups S (schema) and G (geometry) can run now. Group L (loads) waits on `rm.v1-fall-case-arm-backward`, which waits on `rm.v1-shoulder-concept` (Joe's ruling, 2026-11-13, in the loads node). Group F (file) waits on L. Do not start L or F until `fy roadmap` shows `rm.v1-upper-arm-loads-computed` ready, and do not start any group whose predecessor's memo Joe has not signed off. If adr-0025 changes anything group L assumes (the backward case's load path, its stop, the flag of lc.fall-shoulder-lateral), that is a finding at L's T0: stop, and Joe overwrites this brief.

## What this brief does not do

- It reads nothing from `catalog/actuators/` and carries no actuator quantity: no peak or stall torque, torque-speed curve or reflected inertia (adr-0045 D1). The actuator-peak case belongs to `rm.v1-upper-arm-requirements`.
- It carries no bolt circle, clocking, fastener, dowel, compliance stroke or overload stop (adr-0045 D3; decision 0020).
- It assumes no shoulder geometry and carries no shoulder ROM (adr-0045 D3, D4).
- It subtracts no component from the available volume. The volume is the body envelope inside the 5 mm shell, not the free field: `part.arm.upper_member` is a placeholder, and demand-only means the room the body offers, not what is left after a design.
- It edits no decision record, no roadmap node, no accepted thread record except lc.fall-shoulder-lateral's one field (T2), no `done_when` and no `signed_off`. It sets no record `active`. It stamps nothing unless Joe's prompt says so.
- It runs no simulation and does not rebuild the envelope. If a value it needs exists only in the voxel cache or the mesh, that is a finding (see "Stop and ask").

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, rule 10 on coupled tasks included. There is no test-run waiver: every group changes library code, so the full suite (about 8 minutes) runs as `CLAUDE.md` rule 1 says, and every checkpoint runs `fy state`.

The frame of the file is the right-side ISB/CAD segment frame (CONVENTIONS section 3: origin at the shoulder joint centre, x anterior, y proximal, z lateral, mm). The envelope ledgers are in the model body frame (x anterior, y left, z up). Convert only through `tools/envelope/registry.isb_to_segment` and its transpose; never retype the rotation. Ledger stations are distances below the top of the field, not below the joint centre (the upper arm's field is 291.23 mm long against the sheet's 255.234 mm); read the joint stations from the ledger and the sheet, never assume them.

Every number in any output is one of three things, and the memo says which: read from an address the work item consumes; computed from such values by committed code (the memo names the function); or one of the authored inputs of T5, each citing its clause. A number that is none of the three is a defect.

## Stop and ask before

- Any change to `thread-record/2` beyond the optional `contact_in` and the derived `fall_contacts` (adr-0045 D5), or to the CSV addressing beyond T3's definition.
- Extending `tools/envelope/foreign.py`, the oracle or the ledger build, or writing a second sweep tool, if the existing ones cannot sweep the forearm envelope over elbow flexion (T7).
- Reading geometry from `data/envelope/cache/` or the mesh into any value the file carries.
- Any authored input in T5 whose clause does not state it as a number (for example Morrey's arc bounds, which 0008 D2 marks [source needed]).
- Any flag for a (case, segment) pair that adr-0045 D5(e) does not give, including the backward case's.
- Adding a dependency.

## Report as a finding, and stop if it blocks a task

- The upper arm ledger's origin is not the adr-0042 D1 shoulder joint centre (the sheet's, through the trunk registration), or its axis does not end on the D1 elbow node.
- The two joint centres are not the sheet's `upper_arm_right_length` apart within 0.1 mm (adr-0042 D3).
- Any reproduction gate below (G-L1, G-L3, G-L4) misses its reference. The reference is the accepted record; the code does not get tuned toward it, and the record is not quietly trusted over the code either.
- Any ray labelled skin that the ledger records as ending on a cut plane (memo 59, finding 7).
- A case reaching `seg.upper_arm` through `fall_cases` or `fall_contacts` with no flag.

## Gate criteria

Authored before the work (roadmap README section 8). Each is reported in its group's memo as pass or fail with its numbers, and Joe signs off the gate table. Do not change a criterion to make a result pass; a criterion that looks wrong is a finding.

### Group S: `rm.v1-upper-arm-char-schema`

- **G-S1** (adr-0045 G1). Every existing thread record validates unchanged under the amended `thread-record/2`, checked before lc.fall-shoulder-lateral is edited. Report the count.
- **G-S2** (adr-0045 G2). Every segment's derived `fall_cases` is byte-identical to before.
- **G-S3** (adr-0045 G3). `seg.upper_arm`'s `fall_contacts` is exactly [lc.fall-hand-arm, lc.fall-shoulder-lateral]; `seg.thorax`'s `fall_contacts` no longer holds lc.fall-shoulder-lateral; `seg.thorax`'s `fall_cases` still does.
- **G-S4** (adr-0045 G4). A mutation test: `contact_in` naming a non-segment fails the build; `contact_in` on a gait or scenario case fails the build.
- **G-S5. Addressing unchanged.** After T3, every address in every existing record, stamp and CAD sidecar resolves to the same hash as before. Report the count. `work.upper-arm-cad` stays `current`.
- **G-S6. CSV addresses.** A CSV address resolves to the cell's string as written. Mutation tests: editing a different row leaves the address's hash unchanged; editing the cell changes it; a duplicate first-column key, a missing column and a missing row each fail with an error naming the file and the key.
- **G-S7. Schemas.** A hand-written minimal fixture validates against `segment-characterization/1`, and one against the inputs schema of T4. Mutation tests, each must fail: a missing banner key; an unknown top-level key (`actuator` among them); a position without its bar; an SJC bar of 0 (only a number from a record or the string `unstated` is allowed); a fall case without a flag or without its basis.
- **G-S8.** `fy thread build` reports 0 errors and 0 warnings, and the full suite passes.

### Group G: `rm.v1-upper-arm-geometry-extracted`

- **G-G1. Provenance.** The upper arm and forearm ledgers name `data/makehuman/freyja-body-v3.obj`; report their inputs hashes (the upper arm read `770c1272e683` at memo 59; a different hash is reported, not a fail).
- **G-G2. Frames.** The shoulder and elbow frames share axes; the axes are orthonormal and right-handed to 1e-9; the elbow origin is `upper_arm_right_length` from the shoulder origin within 0.1 mm, along -y.
- **G-G3. Bars.** Elbow 7 mm, mostly anteroposterior; wrist 5 mm; shoulder `unstated` (adr-0045 D6). The axis tilt bound atan(bar / length) is computed and reproduces adr-0045 D6(a)'s 1.6 degrees to 0.05 degrees.
- **G-G4. Interface sections.** Each interface carries its two bracketing ledger rows with their signed offsets from the joint station, no interpolation. Every ray is labelled `skin` or `cut_plane` by the ledger's own definition (Code finds and cites it; a zero `hw_` is the observed signature, not the definition). At the shoulder, the first row with a lateral skin ray is station 40 and its `hw_lat_mm` reproduces memo 59's 34.30 mm to 0.01 mm.
- **G-G5. Elbow room on the D1 node.** At the last full-section row above the elbow station, every `r_` ray from the node's axis is positive. Report all eight, the anterior-minus-posterior and medial-minus-lateral differences, and each against the 7 mm bar. A non-positive ray is a finding (memo 43's one-sided room on the old anchor is what this checks).
- **G-G6. ROM.** The anatomical range is read from the snapshot (`elbow_extension`, `elbow_flexion`) and equals it exactly; the mechanism's flexion end comes from the T5 inputs file; signs follow `checks/joint_polarity.yaml`, flexion positive, extension negative.
- **G-G7. Volume.** The inner volume at the 5 mm shell equals the ledger's `inner_volume_l.t5` exactly (read, not recomputed). The station rows carried are the ledger's rows, converted to CAD y, unchanged in value.
- **G-G8. Flexion clearance** (adr-0045 Consequences). The forearm envelope swept over elbow flexion from 0 to the mechanism's end, against the upper arm's: the least separation of the two 5 mm inner shells and the deepest skin interpenetration, at 1 degree steps from 120 degrees to the end and at 0, 30, 60 and 90. Two runs byte-identical. At 0 degrees the inner shells are separated; if not, stop. The angle at which the inner shells first touch is reported; if it is at or below the mechanism's end, that is a finding for Joe, not a fail of this gate. Skin interpenetration is reported and not gated: skin is soft tissue in a human and a shell in Freyja, and which it is here is a design question.

### Group L: `rm.v1-upper-arm-loads-computed`

- **G-L1. Static reproduction.** From the snapshot, the elbow hinge torque at forearm horizontal is 5.00, 3.45 and 1.89 N·m at the design payload, the nominal payload and self-weight, to ±0.005 N·m (adr-0008 D2, D7).
- **G-L2. Sweep exact.** The gravity wrench is linear in the gravity direction, so its maximum over the sphere per component and in magnitude is computed analytically at every elbow angle. A sampled cross-check (at least 2000 directions, Fibonacci) is never above the analytic value and is within 0.5% of it everywhere.
- **G-L3. Swing reproduction.** Inertia about the hinge 0.046, 0.097 and 0.147 kg·m² (to ±0.0005); S1 to S3 inertial torque 0.42, 0.33, 1.33 N·m and with static 2.3, 5.3, 6.3 N·m, to the record's printed precision; peak speeds 2.95 and 1.47 rad/s (adr-0008 D3, D7). The minimum-jerk constants 1.875 and 5.77 are computed from the polynomial, not typed.
- **G-L4. Hand-arm fall geometry.** The miss distance of the hand-to-shoulder line from the elbow node at the extension stop, computed from the sheet's lengths and the model's hinge, is reported against adr-0008 D6(f)'s "about 10 mm", and the moment at the 30 kN rating as a band over the elbow's ±7 mm anteroposterior bar, against 0008's 320 N·m. The transverse force from the frame tilt at 30 kN reproduces adr-0045 D6(a)'s 0.8 kN to 0.05 kN. 320 N·m outside the band is a finding; the record is not amended here.
- **G-L5. Case coverage.** The fall cases in the output are exactly `fall_cases` ∪ `fall_contacts` of `seg.upper_arm`, read from the derived document (adr-0045 D5(c)). Each carries its flag and the flag's basis from the T5 inputs file. Mutation: removing a flag from the inputs fails generation.
- **G-L6. Shoulder-lateral row.** It carries the station and normal from `data/falls/room.json`, the energy from the case record (540 J), the skin depth along the normal from the CSV (34.30 mm), the flag `clearance`, provisional, and a clearance magnitude of null with its reason (`rm.v1-shoulder-concept`).
- **G-L7. Demand only.** The work item consumes no `catalog/` address, and a test shows the loads code reads nothing under `catalog/`.

### Group F: `rm.v1-upper-arm-char-file`

- **G-F1.** `data/characterization/upper_arm.json` validates against `segment-characterization/1`.
- **G-F2.** Two builds are byte-identical, and a test shows the committed file equals a fresh build.
- **G-F3. Consumes exactly.** A test with a recording resolver shows the set of addresses the generator resolves equals `work.upper-arm-characterization`'s `consumes`, no more and no fewer.
- **G-F4. Staleness works.** `fy thread impact --edit` on each of `snapshot#/forearm_right_mass`, one CSV cell of the upper arm's sections, `lc.fall-hand-arm#/source/energy_j` and one T5 input lists `work.upper-arm-characterization`; `snapshot#/thigh_right_mass` does not.
- **G-F5.** `fy thread build` reports 0 errors and 0 warnings, the full suite passes, and the memo lists every computed value with the function that computes it.

## Tasks

**T0. Baseline (every group, no commit).** `fy thread build`, `fy test --quick`; record counts, warnings and timings. Check adr-0045, 0008, 0042 and 0037 are `accepted`. Check the leaves this group needs are ready in `fy roadmap`. Group S also: confirm the address resolver has no CSV support today, and `seg.upper_arm`'s `fall_cases` is [lc.fall-hand-arm]. Group G also: confirm the ledger's origin and axis against adr-0042 D1 (the first two findings above), read `foreign.py`'s stops and say whether it can take the elbow (owner `forearm_R`, host `upper_arm_R`) without change.

### Group S

**T1. Contact field and derived relation (one commit).** In `thread-record/2`, in place: optional `contact_in` on the energy-defined form only, naming a segment record; derived `fall_contacts` on each segment, every case whose contact is that segment (`contact_in`, else `zone_in`). Housing, reserves, claims and budgets stay keyed on `zone_in`. CONVENTIONS sections 3 (thread terms: `contact_in`, `fall_contacts`, the reading rule of adr-0045 D5(c)) and 8 (the load-case line) change in the same commit (rule 7). Tests first; G-S1 is measured before T2. G-S2, G-S4.

**T2. lc.fall-shoulder-lateral gains `contact_in: seg.upper_arm` (one commit).** Its `notes` gains one sentence citing memo 59 finding 7 and adr-0045 D5(d). G-S3.

**T3. CSV addressing (one commit).** A tracked CSV is an address source. Its value is a mapping from the first column's cell string to a mapping of header to cell string, `#`-prefixed lines skipped, cells kept as written (no float parse, so the hash is the text's). Example: `data/envelope/upper_arm_R_sections.csv#/40.0/hw_lat_mm`. CONVENTIONS section 3's address definition changes in the same commit. G-S5, G-S6.

**T4. Schemas, layout rows (one commit).** `docs/schemas/segment-characterization-1.schema.json` (adr-0045 D2) and `docs/schemas/characterization-inputs-1.schema.json` (T5). The characterization schema requires: banner keys and no timestamps; `segment`, `side: right`; the frame statement; anchors with positions and bars; interfaces as frame plus bracketing section rows plus a wrench per case; ROM (anatomical, mechanism, loaded arc, flexion clearance); volume; load cases split static, inertial and fall, each fall case with energy, direction, contact station, flag, basis and, where 0008 D6 gives one, the rating. `additionalProperties: false` throughout. Field names are Code's; Joe reviews them at this checkpoint, so the memo prints the schema's outline (keys and types, not the JSON). CONVENTIONS section 2 gains rows for `data/characterization/` (generated, plus `inputs/` authored) and `tools/characterization/`; section 8 gains the inputs file and the sentence "A change to a decision record that moves a value a characterization inputs file carries edits that file in the same commit." G-S7, G-S8.

**Checkpoint S.** Memo per `CLAUDE.md` rule 6 with the gate table, the schema outline, the counts of G-S1 and G-S5, every finding and the questions for Joe. `fy state`, stop.

### Group G

**T5. Authored inputs (one commit).** `data/characterization/inputs/upper_arm.yaml`, each entry `{value, unit, source}` with the source a decision clause, and nothing that an address already holds: the shell 5 mm (adr-0007 D4); anchor bars 7 mm elbow, anteroposterior, and 5 mm wrist (adr-0042 D2); the mechanism's flexion end 157 degrees (adr-0008 D4); payloads 1.0 and 0.5 kg at the hand's centre of mass (0008 D2); the swing rows S1 to S3, amplitude, duration and payload (0008 D3); the hand-arm contact at the wrist (0008 D5's design reach) and its rating 30 kN axial (0008 D6(f)); the loaded arc as null with `source_needed` (0008 D2); the BSIP spread about 3% (0008 D2); the flags, lc.fall-hand-arm `structural` (0008 D6(f)) and lc.fall-shoulder-lateral `clearance`, provisional (adr-0037 D5, adr-0045 D5(e)). The memo carries one table: entry, value as written, the clause's number as read from the decision (quoting at most the cell or phrase), equal or not. All equal, or a finding.

**T6. Geometry library (one or more commits).** `tools/characterization/` (segment-generic) with `geometry.py`: the two frames, the bars and the tilt bound, the bracketing section rows at each interface with ray labels, the elbow-room readout, ROM, volume. Everything read through `tools/thread` address resolution. `fy characterize <segment> --dry-run` prints a summary (no arrays). G-G1 to G-G7.

**T7. Flexion clearance (one commit).** Reuse `foreign.py` and the oracle if T0 found they can sweep the forearm envelope in the upper arm's frame over elbow flexion; otherwise stop and ask. Write `analysis/elbow_flexion_clearance.py`, no arguments, output `data/characterization/upper_arm_flexion_clearance.json` (generated, tracked, banner keys), the way `analysis/fall_room.py` writes `data/falls/room.json`; the file reads it by address. G-G8.

**Checkpoint G.** Memo with the gate table, the T5 table, the interface sections with labels, the elbow-room rays, the flexion table, findings, questions. `fy state`, stop.

### Group L

**T8. Static sweep.** `loads.py`. For each payload (design, nominal, none), elbow angle over the mechanism travel at 1 degree and both ends, the wrench of gravity on everything distal of each interface, at each interface origin in that frame: the forearm, hand and payload at the elbow; those plus the upper arm's own mass at the shoulder. The gravity direction is free over the sphere (decision 4), maximised analytically (G-L2), and the governing direction is reported. Payload rows across the whole travel are labelled "beyond the claim outside the loaded arc, whose bounds are unsourced" and the self-weight rows stand beside them, so that sourcing the arc narrows the claim without recomputation. Each value carries the BSIP spread; each value resolved in a frame carries the tilt bound. G-L1, G-L2.

**T9. Swing rows.** Minimum-jerk elbow strokes S1 to S3 with the shoulder fixed (decision 5), inertia from the snapshot, start angle swept over every start that keeps the stroke inside the travel. The output is the envelope over start angle and time of the full wrench (static at the worst gravity direction plus inertial) at each interface, provisional as 0008 D3. G-L3.

**T10. Fall cases.** The cases of G-L5. lc.fall-hand-arm: energy and direction from the record, contact at the wrist, the 30 kN rating as compression along the hand-to-shoulder line at the extension stop, the wrench at both frames with the moment band of G-L4; the shoulder frame's idealised zero moment is stated as such, and 0008 D6(h)'s off-line moment on the shoulder mounts is carried as open (`rm.v1-shoulder-concept`), not computed. lc.fall-hand-arm-backward: from its record and adr-0025 only. lc.fall-shoulder-lateral: G-L6. G-L4 to G-L7.

**Checkpoint L.** Memo with the gate table, the reproduction tables beside 0008's numbers, the governing case per interface and wrench component, findings, questions. `fy state`, stop.

### Group F

**T11. Work item and file (one commit; coupled, so say so first).** `thread/records/work.upper-arm-characterization.yaml`, `proposed`, `of: seg.upper_arm`, `mode: assisted`, `output: data/characterization/upper_arm.json`, `consumes` exactly the addresses the generator resolves. `fy characterize upper_arm` writes the file. G-F1 to G-F5. Do not stamp unless the prompt says so; the leaf's criterion reads `awaiting` or not current until Joe's stamp, which is expected.

**Checkpoint F.** Memo with the gate table, a one-page reading of the file for Joe (what governs each interface, the room, the ROM and its clearance, what is provisional and why), findings, questions. `fy state`, stop.

## Decisions this brief makes (Joe approves them by committing it)

1. Four groups, four checkpoints, one leaf each. L and F wait on the backward case (Joe's ruling); S and G run now.
2. CSV addressing (T3). The section ledgers live only in CSV, which CONVENTIONS section 3 does not address, so without it the file could not consume its own volume and section data. Rejected: duplicating the rows into JSON (two generated homes), and consuming the ledger YAML's inputs hash as a proxy (it does not move when ledger code alone changes).
3. An authored inputs file per segment (T5) for values that live only in decision prose, with the CONVENTIONS section 8 sentence. adr-0045 D2's "none is typed" then holds for the file and its generator; the typing lives in one authored file, checked against its clauses as the fall cases' energies were.
4. The static sweep takes gravity over the whole sphere in the segment frame. That is a superset of any shoulder pose, so it assumes no shoulder ROM (adr-0045 D4) and cannot be invalidated by the shoulder concept, only made conservative.
5. Swing rows hold the shoulder fixed; shoulder swing waits on the shoulder concept.
6. Interface sections are the bracketing ledger rows with their offsets, not interpolated, and every ray is labelled skin or cut plane.
7. Available volume is the body envelope inside the 5 mm shell, not the free field.
8. The library is `tools/characterization/`, segment-generic, called by `fy characterize <segment>`; the flexion clearance is an `analysis/` script writing tracked JSON, after `fall_room.py`.

## Prerequisites for Joe

- Point the "Current Ariadne brief" line in `CLAUDE.md` at this file, commit the brief, and prompt Code with its path, its `sha256sum` prefix and the group to run (S first).
- Sign off each leaf from its memo (`signed_off: true`); Code never sets it.
- Roadmap batch owed by adr-0045's Consequences: `rm.v1-upper-arm-requirements` gains `rm.v1-elbow-actuator-selected` as a blocker.
- Before F: the stamp of `work.upper-arm-characterization` is yours to call for in the prompt.
