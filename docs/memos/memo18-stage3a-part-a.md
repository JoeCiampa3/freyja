# Memo 18: Stage 3a Part A, the system model library

STATE: (filled in by the commit that regenerates docs/STATE.md)

## Decision summary

- The thread library works and the reallocation test passes. Moving an actuator (M2) from the thigh to the pelvis is an edit to one record (two fields on it: `housed_in` and `reacts_into`). The build then changes exactly 16 generated files, byte for byte as the test states them. The shank's files, the hip joint's and the harness run's do not change by a byte. Four work items go stale or drifted, two stay current, and the pelvis goes over its mass budget.
- Numbers that matter:
  - generated files changed by the move: 16 of 62 (reference: the brief's test is "exactly the expected set"; the set is written out in `tests/test_thread_reallocation.py` with a reason per entry);
  - pelvis mass claim 5.69 kg before, 10.44 kg after, against a target of 9.49 kg (the sheet's pelvis mass);
  - what-if on that fixture: 0.13 s in the library, 0.53 s end to end through `fy` (reference: under 3 s);
  - build of that fixture 0.17 s (the Part B reference is under 2 s on the real store; not measured yet, there is no real store);
  - new tests: 178 (68 schema, 88 library, 22 fixture and acceptance), about 9 s of the suite (reference: under about 20 s);
  - full suite 1274 passed in 323 s; the baseline was 1096 passed in 342 s (`CLAUDE.md` says "about a minute and a half": it is five and a half minutes).
- Decisions for Joe (recommended option first):
  1. Accept the proposed real record set: 10 segments, 9 joints (hip, knee, ankle, lumbosacral, thoracic, cervical, shoulder, elbow, wrist). Questions Q1 to Q4 below.
  2. Which scenario classes become load cases in T7 and what `independent_source_required` is for each (Q5). Recommended: `stand_static` false, `walk_treadmill` true, `rom_sweep` false.
  3. Mass budget semantics for bilateral parts (Q6). Recommended: keep it per side on a bilateral segment and doubled in a unilateral one. Under that rule the pelvis rises by twice M2's per-side mass when M2 moves in, not by M2's mass, which is what the brief's T4 sentence says literally.
  4. Say whether the Part A coupling is acceptable (below, Finding 1). Recommended: yes; the alternative is a dossier renderer that does not exist until T5.
- What would change the conclusion: a real-store build slower than 2 s (the library is plain Python over about 260 snapshot rows and about 30 records, so I expect well under), or a record set from Joe that binds a hinge to two joints.

## What was built

Commits (one per task, except T3 and T4 together):

- T1 `ea58587`: `docs/schemas/thread-record-1`, `thread-stamp-1`, `thread-graph-1` and the five CONVENTIONS amendments.
- T2 `fdcf562`: `tools/thread/` library: `addr` (grammar, canonical JSON, hash, pointers, overlap), `edges` (the edge-type registry, 21 types), `store`, `build` (validation, bindings, inverse relations, mass budgets, work status, outputs, stamp and output writers), `render` (banner, derived JSON, dossier sections 1 to 6, STATUS.md), `impact`.
- T3+T4 `2b3e979`: `fixture` (general and reallocation), `seed` (the proposed structural records), `cli` (`fixture`, `impact`), `fy thread` wiring, and the acceptance test.

Every error and warning in the brief has a hand-authored fixture under `tests/fixtures/thread/` (one base root plus 18 invalid and 6 warning overlays), each yielding exactly its class. Names (`EXPECTED_SEGMENTS`, `BILATERAL`, the column lists) are imported from `pre_processor`; a test patches `BILATERAL` and sees the library follow. `pre_processor` imports numpy and nothing else heavy (0.21 s, no mujoco, no sheet access), so no stop was needed. A test checks the library does not import mujoco.

## T0: inventory

Run before any record exists; nothing is committed from it.

**`pre_processor`:** `EXPECTED_SEGMENTS` = head_neck, thorax, abdomen, pelvis, upper_arm, forearm, hand, thigh, shank, foot (10). `BILATERAL` = upper_arm, forearm, hand, thigh, shank, foot (6).

**Model (`sim/models/freyja.xml`):** 16 bodies, 31 hinges, one free joint (the pelvis root; not a record). Body tree: pelvis > {thigh_r > shank_r > foot_r; thigh_l > shank_l > foot_l; abdomen > thorax > {upper_arm_r > forearm_r > hand_r; upper_arm_l > forearm_l > hand_l; head_and_neck}}.

**Snapshot:** 261 keys = 16 body names x 15 columns (240) + 19 ROM keys + `target_mass` and `target_stature`. Keys claimed by a segment (240) or a joint (19): 259. Unclaimed: `target_mass`, `target_stature` (body-level; the whole-body budget reads `target_mass`). Keys two records would both claim: none.

**Proposed record set** (it is in `tools/thread/seed.py`, and the structural records of the fixture are built from it):

| joint | hinges (per side where bilateral) | ROM keys | parent > child segment |
|---|---|---|---|
| hip (bilateral) | hip_fe, hip_aa, hip_ier | 6 | pelvis > thigh |
| knee (b) | knee | 2 | thigh > shank |
| ankle (b) | ankle_pdflex, ankle_ie | 4 | shank > foot |
| lumbosacral | lsj_fe, lsj_lat, lsj_ax | 4 named, 0 in the snapshot | pelvis > abdomen |
| thoracic | tj_fe, tj_lat, tj_ax | none | abdomen > thorax |
| cervical | cj_fe, cj_lat, cj_ax | none | thorax > head_neck |
| shoulder (b) | shoulder_fe, shoulder_aa, shoulder_ier | 6 named, 3 in the snapshot | thorax > upper_arm |
| elbow (b) | elbow | 2 | upper_arm > forearm |
| wrist (b) | wrist | 2 | forearm > hand |

Every one of the 31 hinges maps to exactly one joint; every one of the 16 bodies to exactly one segment. Built on the real model and snapshot the structural records give 0 errors, 0 `unbound-body`, 0 `unbound-hinge`.

**Rule for side-specific names from one binding.** A binding names a base. If the model has a body or hinge of that exact name it is the binding (pelvis, abdomen, lsj_fe). Otherwise the binding is `<base>_left` and `<base>_right`, both of which must exist. `sides: [left, right]` on the record is then compared with `pre_processor.BILATERAL`: for a segment, its own name; for a joint, its child segment (found through the model's body tree); for a part, a part housed in a bilateral segment must carry `sides` (which side would it be otherwise). Snapshot keys follow `pre_processor`'s own rule: `<name>_<column>`, or `<name>_right_<column>` and `<name>_left_<column>` for a bilateral name, read from the right.

**Scenarios and specs:** `hold_pose` (`envelope: false`), `rom_sweep`, `stand_static`; sweep `posture_sensitivity`; gait spec `walk_treadmill` with `camargo_mapping`. `sim/runs/ENVELOPE.md` includes `rom_sweep`, `stand_static` and `walk_treadmill`; not yet included: stairs, sit-to-stand, overground walking, ramps.

**Questions for Joe from the inventory** (Part A continued on fixtures regardless):

- Q1. The model body is `head_and_neck` and the segment is `head_neck`. The segment record needs an explicit `body: head_and_neck`. Accept, or rename the body in the template (a template change, which I may not make)?
- Q2. The two trunk joints are named in the model `tj_*` ("thoracic joint", between abdomen and thorax) and `cj_*` ("cervical joint", between thorax and head and neck). I wrote `jnt.thoracic` and `jnt.cervical`. Anatomically the abdomen/thorax junction is thoracolumbar and the head/thorax junction is cervicothoracic. Which names do you want?
- Q3. Seven ROM keys the template names are not in the snapshot (the seven missing sheet values): `lumbosacral_flexion`, `lumbosacral_extension`, `lumbosacral_lateral_bending`, `lumbosacral_axial_rotation`, `shoulder_adduction`, `shoulder_external_rotation`, `shoulder_internal_rotation`. The joint record lists them so the binding is already right when the sheet gets them; the derived file shows them under `rom_missing`, no value invented. Recommended: keep them listed. The alternative is to list only keys the snapshot has and edit the record later.
- Q4. The ankle is one joint with two hinges (plantar/dorsiflexion, inversion/eversion); no separate subtalar record. Any objection?
- Q5. For T7: `ENVELOPE.md` includes three classes. Do you want a load-case record for each, and what is `independent_source_required` for each? My proposal: `stand_static` false (statics at a design pose with a design CoM position; no cited quiet-standing CoM), `walk_treadmill` true (the rows rest on method A with the human CoP, flagged provisional; method B failed), `rom_sweep` false (gantry gravity torque, a pipeline test more than a design condition; drop it if you do not count it as a load source). Walking at 1.4 and 1.6 m/s: one record with both speeds in the condition, or two?

## Acceptance test result

`tests/test_thread_reallocation.py`, 9 tests, all pass. Fixture: M1 (pelvis) and M2 (thigh), both bilateral, acting across `jnt.hip`; M3 in the shank; `hn.leg-power` pelvis > thigh > shank; six work items. Masses are set from the sheet's pelvis mass (9.49 kg): M1 = 0.30 x 9.49 = 2.847 kg per side, M2 = 0.25 x 9.49 = 2.373 kg per side. Both modules sit in the pelvis after the move, so the pelvis claims 2 x (2.847 + 2.373) = 10.44 kg against 9.49. The fractions are by construction (0.6 of the target before, 1.1 after), not tuned toward a result.

- Changed files after the edit: `part.hip.m2`, `seg.thigh`, `seg.pelvis`, `work.thigh-houses`, `work.pelvis-houses`, `work.m2-mount`, `work.pelvis-mass` (derived and dossier each, 14), plus `graph.json` and `STATUS.md`. The test lists the set and a reason per entry. Byte-identical: the shank, `part.leg.m3`, `hn.leg-power`, `jnt.hip`, `if.m2-thigh`, `work.shank-only`, `work.hip-actuation` (derived and dossier asserted for the ones I name).
- Statuses: thigh-houses, pelvis-houses, m2-mount stale; pelvis-mass (pinned baseline) drifted; hip-actuation (consumes the hip's `acted_on_by`, which did not change) and shank-only current. Diffs name each moved address with both values (for example `thread/derived/seg.pelvis.json#/budgets/mass` stamped `over: false`, now `over: true`).
- Budget: thigh claim falls by 2.373 kg (M2, per side); pelvis claim rises by 4.746 kg. `budget-over` fires for the pelvis and only for the pelvis (the whole-body claim stays under the 65 kg target).
- What-if (`fy thread impact --edit ... --edit ...`) reports the same 16 files and the same four status changes as the real edit, and the root is byte-identical afterwards (tested over every file).
- Reverting returns all six items to `current` and every output to the bytes of the first build. Two builds from the same inputs are byte-identical.

How the "nothing unrelated changes" property is obtained: a generated file's banner carries `inputs sha256:<12>`, the hash of the addresses its content was built from, and each build records those addresses at the field level (`part.hip.m2#/acts_across`, not the whole record). If a banner hashed whole records, the hip joint's files would change whenever M2's housing changed, because the joint lists M2 under `acted_on_by`.

## Timings

| what | time |
|---|---|
| fixture generation (general) | 0.30 s |
| build of the general fixture (92 outputs) | 0.08 s |
| build of the reallocation fixture (62 outputs) | 0.17 s |
| impact what-if, library | 0.13 s |
| impact what-if, `python tools/fy thread impact ...` end to end | 0.53 s |

The real-store build time is a Part B number.

## Tests added

178 under `tests/test_thread_*.py`: schema 68, addr 25, validate 32, derive 31, fixture 13, reallocation 9. They run in about 9 s together, inside the 20 s allowance. Full suite: 1096 before, 1274 after.

## Findings

1. **The brief's tasks are coupled; I should have said so before building.** T4 asserts which derived files and dossiers change and runs `fy thread impact`; the renderer is T5 and the command T6. I put the output builder (derived JSON, `graph.json`, `STATUS.md`, dossier sections 1 to 6), the stamp and output writers and the `impact` command into Parts T2 to T4, and committed T3 and T4 together because the fixture module and `cli.py` serve both. CONVENTIONS section 9, rule 10 asks for this to be said in advance; I did not. Left for Part B: dossier sections 7 (references) and 8 (neighbourhood), their link test, and `validate`, `build`, `show`, `why`, `stamp` (the writer exists in the library; the command does not), the hook, the `fy state` line.
2. **Wording in T4.** The Purpose says the move is "a one-line edit to one record"; T4's sequence edits two fields (`housed_in` and `reacts_into`). Both are on the one record, but a move with only `housed_in` edited leaves a reaction into the thigh, which is valid (tested: the what-if of the single edit is clean). And the brief says the pelvis's claim "rises by" M2's mass; for a bilateral part moved into a unilateral segment it rises by twice the per-side figure (Q6).
3. **Suite time.** The baseline took 342 s, not "about a minute and a half" as `CLAUDE.md` and `state.py` say. I ran the full suite once per task as the rule asks.
4. **Roadmap node count.** `docs/STATE.md` says 160 nodes; the pre-commit hook's roadmap build says 165. The roadmap commit `f67a0d1` added nodes after `STATE.md` was written. Regenerating `STATE.md` in this task fixes the line.
5. **Choices the brief left open** (each is in the schema and CONVENTIONS, so it is cheap to change now and not later):
   - Record field names: segment `body`; joint `hinges` and `rom_keys`. The brief says "binds to its model body or bodies / hinges and the ROM keys" without names.
   - `kind` values are `segment`, `joint`, `part`, `interface`, `load_case`, `harness_run`, `work_item` (the brief's table writes them with spaces).
   - A record that fails its schema is excluded from derivation, so one bad file does not cascade into reference errors. A reference to it still resolves.
   - With errors present, only the warnings that need no derivation (`unbound-*`, `active-refs-inactive`) are reported; the others need the build.
   - Superseded parts are listed under `houses` (housing is a relation) but claim no mass; proposed and active parts claim.
   - The whole-body budget compares the sum of part claims (bilateral claims counted twice) with `target_mass`. The segment masses already sum to `target_mass` by the closure check, so this body check only says something once hardware claims are real.
   - An address into a generated thread output resolves against a build with the work statuses left out, otherwise a work item that consumes `seg.x.json#/work/...` would depend on its own status. CONVENTIONS section 3 says "everything but the work statuses".
   - In a snapshot what-if the banner's snapshot hash is a hash of the edited key table, not the hash of a rebuilt file, so it moves with the edit but will not equal a later real rebuild's. Output bytes are only compared between two in-memory builds, so this does not affect any reported change.
   - `impact <address>` with no `--edit` lists the outputs built from the address as it stands now. An edit that moves the value to a new place (M2 into the pelvis) only shows the destination file in the `--edit` form. A brief that wants the potential dependents of a field in advance needs a different definition.
6. **Tolerances I chose, with reasons.**
   - `MASS_EPS_KG = 1e-9`: a sum of decimal masses carries float round-off of about 1e-15; an over-claim smaller than a nanokilogram is not one.
   - `MASS_DIGITS = 6`: kg figures in the derived files are rounded to a microgram, so files carry no float noise.
   - Stamp value limit 2048 bytes: the brief's.
   - `SHOW_CHARS = 100`: values are cut at 100 characters in `STATUS.md` and the dossiers; `why` (Part B) shows them whole.
   - The 3 s what-if allowance is asserted in the test as the brief states it; it is not tuned.
   - Fixture masses are fractions (0.30, 0.25) of the sheet's pelvis mass, set by construction as above.
7. **My own mistakes.**
   - My first schema-writing command used a shell heredoc with an apostrophe inside it and the shell rejected it; I wrote the generator to a file instead. No file was damaged.
   - I started two full test runs at once by mistake (a `pkill` that does not exist on this setup); I stopped the first and used the second, started after the last change of the library files.
   - My T2 commit message gave the test counts by file wrongly (29, 32, 27 against 25, 32, 31, same total 88); I amended the unpushed commit, which is why T2 is `fdcf562`.
   - A warning fixture over-filled the pelvis and the whole body at once (99 kg); the test caught it and I reduced it to 11 kg.
   - I wrote one acceptance-test case with a leftover `__wrapped__` branch and rewrote it before it was committed.
   - Not a mistake but worth knowing: I reworded five purpose strings in `seed.py` after the full suite ran for T3+T4 (the thoracolumbar/cervical wording, Q2) and re-ran the thread tests only (178 passed). No test reads them.
8. **Defects seen outside the task.** None in the hook, the CLI or the viewer. The pre-commit hook rebuilt the roadmap on all three commits and staged nothing.

## Questions that need Joe

- Q1 to Q5 above.
- Q6. Bilateral part masses. `mass.kg` is per side. On a bilateral segment (thigh) a part with `sides` claims its per-side kg against the right-side target (`thigh_right_mass`); in a unilateral segment (pelvis) it claims twice, because both modules sit there. The whole body counts bilateral claims twice. Alternative: store a total and a count. Recommended: keep per side.
- Q7. One home for the structural table. `tools/thread/seed.py` holds the proposed segment and joint records so that the fixture covers the real model today. When T7 writes the real records, the fixture should read `thread/records/` for its structural part and `seed.py` should go. Do you want that, or do you want the table to stay as the authored source and the records generated? CONVENTIONS says authored or generated, never both, and the records are authored, so I would delete the table at T7.
- Q8. Is the combined T3+T4 commit and the early output builder acceptable (Finding 1)?

## Checkpoint

Part A ends here. Part B (T5 to T8) starts when you say so, after your answers to Q1 to Q8.
