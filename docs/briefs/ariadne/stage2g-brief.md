# Stage 2g brief (for Claude Code): the single snapshot change

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `decisions/0001-toe-joint.md` (with its amendment), `decisions/0004-hip-stop-pelvis-pose.md`, `decisions/0038-segment-scaling.md` and `docs/briefs/ariadne/stage2g-sheet-spec.md`. This brief belongs to the Ariadne track and closes roadmap leaf `rm.v1-toe-in-model`.

## Purpose

Several changes to Freyja's snapshot are decided and must land together, so that the full three-speed simulation is run once more, at the final snapshot, and not once per change:

1. a passive toe: a toe body and a hinge, with the foot split by conservation (ADR 0001);
2. the foot box built from anatomical landmarks in the sheet instead of the template's 41 mm and 165 mm (ADR 0038);
3. the standing posture as a sheet input, and the stature stack closed on vertical heights (ADRs 0004, 0038);
4. the arm, forearm, hand and foot lengths scaled with everything else (ADR 0038);
5. the seven missing joint ranges and the toe's range, entered in the sheet;
6. the dataset-to-model pelvis frame offset in the retargeting (ADR 0004), after an experiment (T1) that shows its effect.

Joe edits the sheet; Code never does. Part A (T0 to T6) changes code, template and tests against fixtures and ends at Checkpoint A. Part B (T7 and T8) builds from Joe's edited sheet, regenerates everything and ends at Checkpoint B. Do not start Part B until the prompt says so.

## Out of scope

- The band constants (`gait.BAND_CORR`, `gait.BAND_RMS_PCT`, `gait.BAND_STEMS`), the filter cutoff, the offset and pitch-flag subject lists, the sensitivity settings, the trunk modes, the 0.5 m/s first-harmonic table, and methods A, B and H themselves.
- Any toe stiffness or damping sweep: the sheet holds placeholders (`toe_stiffness_nm_per_deg`, `toe_damping_nm_s_per_rad`); tuning them is a later node. Do not tune toward a result.
- The hip stop: record 0004 keeps 31 degrees. The foot's width (0.050 m half width) moves from the template to the sheet unchanged.
- Any change to the sheet, `local_config.json` or credentials.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, including rule 10 on coupled tasks.

- **Every number comes from the sheet through the preprocessor.** Hard-coded foot or toe values in code or template are bugs. The one literal the template had (half width 0.050) is a sheet key now.
- **Findings stop the work.** A band verdict at 1.4 or 1.6 that changes class (pass to fail or back) because of the frame offset, a regression-test failure, a remainder inertia tensor that fails the triangle inequality, or a frame beyond a new joint limit is a finding: report the measured number and stop. Do not clip a frame, adjust a limit, a tolerance or a subject list.
- **Do not run `fy build` in Part A.** Fixtures and the committed snapshot only. Part B runs it on Joe's sheet.
- **Clean tree.** Before every gait run, `git status` is clean and the record's `git_dirty` must come out false. Report it.
- **Thread records.** Create `jnt.toe` as `proposed` (CLAUDE.md rule 2). If `check.thread.coverage` or `fy thread build` then rejects it, stop and say so; Joe activates it.
- Determinism: same inputs, byte-identical outputs; no timestamps in tracked artifacts.

Stop and ask before:
- changing any constant named under Out of scope;
- changing a check tolerance or a schema version;
- adding a dependency;
- clipping or dropping a frame;
- adopting the frame offset as a default if T1 trips the finding rule above.

## Part A

**T0. Baseline.** Run `fy test`; record the count and time. Record the snapshot, model and manifest hashes. Confirm that `decisions/0001-toe-joint.md`, `0004-hip-stop-pelvis-pose.md` and `0038-segment-scaling.md` exist with `status: accepted`; if any does not, stop.

**T1. The frame offset experiment (gate).** Memo 23 (D2) measured the dataset's IK pelvis frame 13.57 degrees (SD 2.62) posterior of the Dumas frame the model's pelvis is built in, and the retargeting applies the two with no offset.

- Ingestion: store per subject the static Dumas tilt (`snapshot_diag.dumas_pelvic_tilt_deg`) and the static IK pitch (`static_pelvis_pitch_deg`, already in the manifest) as additive keys. Existing arrays stay byte-identical (hash them before and after); the manifest changes, so report its old and new `dataset_manifest_sha256`.
- Retargeting: add a spec option `pelvis_frame_offset: none | measured`, default `none`. With `measured`, add the subject's offset delta (Dumas tilt minus IK pitch) to the pelvis tilt and to the hip flexion, sagittal only, with signs set by `checks/joint_polarity.yaml`; nothing else moves.
- Tests first: delta added to both leaves each thigh's world orientation and hip-centre world position unchanged to 1e-9; the pelvis body's orientation changes by delta; the lumbosacral rows follow from the trunk targets.
- Experiment: run `fy gait walk_treadmill` at 1.4 m/s, all subjects, with the option `none` and `measured`, from the same commit. Report side by side: the `A_filtered`, B and H band table (correlation, RMS as a percentage of peak-to-peak, and RMS in N m) for hip, knee and ankle; the 95th percentile and maximum torque per joint; B's backward CoP offset (median, hip-referenced); the hip extension peaks of the model hinge against memo 23's Dumas-frame numbers (they should differ from the dataset's by delta on average); the lumbosacral rows; and the world position of the hip centre relative to the lumbosacral joint in a standing frame against 34.3 mm forward and 107.5 mm below (derived for a 12.43 degree tilt at the current scale).
- Commit the code and tests. The option stays `none` until Joe decides at Checkpoint A.

**T2. Foot and toe in the preprocessor and template.** Read the sheet contract in `stage2g-sheet-spec.md`. Tests first (on a synthetic fixture sheet and the committed snapshot's whole-foot values).

- `pre_processor`: read the new `design` range (key and value, like `targets`); validate presence, units and positivity. Derive, per side, from the sheet's whole-foot row and the design keys: the foot box (rear, front, half width, height) from `foot_heel_behind_ankle_mm`, `toe_hinge_ahead_ankle_mm` and `foot_half_width_mm`; the toe body (position at the hinge, box from the hinge to `toe_tip_ahead_ankle_mm`, height `toe_height_mm`, mass fraction, centre of mass fraction); and the remainder foot's mass, centre of mass and inertia by conservation:
  `m_r = m_w - m_t`; `c_r = (m_w c_w - m_t c_t) / m_r`; `I_r = I_w - I_t - m_r PA(c_r - c_w) - m_t PA(c_t - c_w)` with `PA(d) = (d.d) E - d d^T`, all in the foot frame, full tensors including products. The toe's inertia is its box (about its centre) shifted to its centre of mass by the parallel axis theorem.
- Template (`freyja_template.xml`, foot bodies at lines 31 to 34 and 55 to 58): the foot body takes the remainder values and the new box; add a child body `toe_<s>` at the hinge with a box geom (same friction and condim as the foot, no literal sizes), a hinge `toe_<s>` (axis `0 -1 0`, positive is extension, range `-toe_flexion` to `toe_extension`, `stiffness` and `damping` from the design keys converted to N m/rad), and the hinge axis at the toe box's mid-height. Keep `site_sole_<s>`. Remove `FOOT_REAR_FRACTION` and every derived value that used it.
- Segments: `EXPECTED_SEGMENTS` and `BILATERAL` do not change (the toe is not a sheet segment); bodies go 16 to 18 and hinges 31 to 33.
- **Conservation test with a mutation test:** the toe and the remainder reproduce the sheet's whole-foot mass, centre of mass and inertia about the whole-foot centre to 1e-9, for both sides.
- **Regression test:** with the old box (heel 41 mm, toe tip 165 mm), a toe mass fraction of 1e-6 and the toe welded, the 1.4 m/s `A_filtered` results reproduce the tracked extract to the existing reproduction tolerance. If you cannot build that test, say why and stop.
- **ANSUR provenance test.** The `design` range carries four `ansur_female_*` keys that nothing else reads. When `data/ansur2/raw/ANSUR_II_FEMALE_Public.csv` exists, a test recomputes the four means (stature, foot length, ball of foot length, lateral malleolus height) and compares them with the sheet's values to 0.05 mm; it is skipped when the file is absent. Mutation-test it.
- Update `check.mjcf.mass_closure` (the toe's mass counts under the foot), `checks/joint_polarity.yaml` (the toe hinges, with a probe point on the toe), and the mirror check (it should need nothing).

**T3. Method A with the toe, B and H with it free.** The dataset's foot is rigid. In A the toe is welded flat (the ankle carries the rigid-foot moment); in B and H the toe is free and moves under its spring and damper. Tests first: with a nonzero toe mass the welded toe's ankle moment equals the rigid whole-foot moment to 1e-6. Update `dynamics._foot_boxes` so the contact polygon includes the toe's box (A: flat; B and H: at the toe's current angle). Report the toe's peak angle and the time it spends at either stop in B and H at Checkpoint B.

**T4. Posture and the stack.** Tests first.

- Read `stand_pelvis_tilt_deg` through the `design` range. The standing pose has the pelvis tilted by it, the hips flexed by it, the thighs vertical, and the lumbosacral joint extended by it so that the trunk stack is vertical; `leanpose.solve_lean` then sets the lean and the ankle for flat soles and the centre of mass at `com_x_rel_ankle_m` (still 0.0). Assert in a test: trunk and thighs vertical within 0.05 degrees, soles flat, the centre of mass over the ankle reference. `gait.Ctx.stand` uses it.
- Add an advisory check `check.mjcf.top_of_head`: the built model's top of head minus `target_stature`, at the standing pose, within 3 mm (both a mutation test and a fixture that fails). Do not make it a gate.
- `foot_pitch.py`'s flat-foot threshold (`OFF_FLAT_DEG`, asin of the 25 mm band over 206 mm) is derived from the model's foot length, not a constant.

**T5. Thread.** Bind the toe body to `seg.foot` and add `jnt.toe` (hinge `toe`, ROM keys `toe_extension` and `toe_flexion`, purpose: the metatarsophalangeal joint), as `proposed`. Update the counts that assume 16 bodies and 31 hinges: `tests/test_thread_real.py:46`, `checks/test_thread_checks.py:32`, `checks/test_mjcf_checks.py:127`, `tests/test_watch.py:198`, and the docstring example at `pre_processor.py:930`. `fy thread build` and `fy thread validate` pass; the hook regenerates the dossiers.

**T6. Hard-coded foot numbers.** Update, from the geometry in the model (not by retyping): `sim/scenarios/hold_pose.yaml:7` and `stand_static.yaml:5` ("heel margin 41 mm"), the assertion at `tests/test_stage2b_housekeeping.py:51`, `tests/test_double_support.py:136, 155`, `tests/test_scenarios.py:284`, `tests/test_statics.py:144-145`, `tests/test_template.py:103-109`, the print string at `foot_pitch.py:305`, and `checks/joint_polarity.yaml`'s ankle probe point (0.12, 0, -0.03 m: still in the foot). Report anything else you find that assumes 41 or 165 mm.

**Checkpoint A.** Write the memo per `CLAUDE.md` rule 6, numbered one above the highest in `docs/memos/`. Include: what was built; T1's side-by-side table and verdict; the conservation and regression results; the tests added and their runtime; every finding. Run `fy state` and stop. Joe decides at this checkpoint whether `pelvis_frame_offset: measured` becomes the spec default.

## Part B

Starts when Joe has edited the sheet per the spec, entered the ROM values, run `fy build` (or handed you an `--xlsx` export) and committed the snapshot, model and sheet-derived files, and the prompt says so.

**T7. Build and checks.** Confirm the snapshot's new keys against the spec; `fy test`, `fy check` (every gate passes; the waived `check.mjcf.com_pct_stature` is re-read and its measured value reported, not re-waived); `fy thread build`. Report the per-segment length table old to new, the ankle height, the top-of-head residual, the standing pose (pelvis tilt, hips, lumbosacral, lean, ankle), the mass closure and the centre-of-mass height as a percentage of stature. Report every frame of the dataset that falls outside a limit that was previously missing (the seven new ROM values and the toe); do not clip any.

**T8. Regenerate once.** On a clean tree, with `pelvis_frame_offset` as Joe set it: ingestion if needed, the three-speed `fy gait walk_treadmill` run, the extract, `fy runs envelope` and `fy runs digest`. Write the three-speed `GAIT` files. Report the stamps (`git_dirty` false for the record and the extract). Then:

- before and after, per speed: the `A_filtered`, B and H band tables, the 95th percentile and maximum torque per joint, the polygon rates by stance decile (and the same kinematics against the old box, to separate the box from the rest), B's CoP offset, the hip extension peaks in the model's own frame;
- the sizing statistics that existing decisions cite (knee, hip, ankle; 1.4 and 1.6), flagged where they moved more than 5%;
- the lumbosacral rigid-mode lateral torque maxima (memo 23 D5): whether AB23 stride 0 at 0.5 m/s is the first stride of its trial, and AB15's share at 1.6. Report only; do not exclude strides;
- the toe's peak angle and time at the stops in B and H.

Run `fy state`, write the memo, stop.

## Performance

A warm `fy thread build` stays under 2 s; the new tests add under 40 s to the suite; the three-speed run and extract take about 33 minutes (memo 22). Report measured times either way.

## Decisions this brief makes (Joe approves them by committing it)

1. The toe is welded in method A and free in B and H.
2. The frame offset is an option, default off, adopted only at Checkpoint A.
3. The toe's hinge axis sits at the mid-height of the toe box.
4. `jnt.toe` is created `proposed`.
5. The regeneration happens once, in Part B; nothing here is final before then.

## Prerequisites for Joe

- Accept ADRs 0004 and 0038 (`status: accepted`), commit them, the sheet spec and this brief, and point the "Current Ariadne brief" line in `CLAUDE.md` at it.
- Part A needs no sheet edits. Part B needs the sheet edited per the spec, the seven ROM values entered, `fy build` run, and the result committed.
