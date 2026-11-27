# Shoulder room brief (for Claude Code): the required set tightened, then the room around the shoulder joint centre along the chosen axis 1, for the differential-versus-serial-roll decision

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then memo 66 (all of it), `docs/briefs/ariadne/shoulder-axis-search-brief.md`, memo 59 (findings 5 to 7 and its shoulder rows), `docs/schemas/envelope-oracle.md`, `tools/envelope/README.md`, `data/envelope/README.md` and `data/envelope/reservations.yaml`. This brief belongs to the Ariadne track. It has two groups (A, then B), each closed by its own checkpoint. Its output is an input to `decisions/0025-shoulder-actuation-concept.md`, which Joe writes. It closes no roadmap leaf.

Tag: Delegate, both groups. End each session with a few lines for Joe (the decision summary of `CLAUDE.md` rule 6, kept short).

`upper-arm-characterization-brief.md` stays paused (Group L waits on adr-0025).

## Purpose

The shoulder is a three-axis gimbal with the axes intersecting at the SJC, axis 3 along the humerus and the centre fixed (see the axis search brief's Purpose). Memo 66 placed axis 1. Joe has taken the up-posterior-lateral basin (memo 66 basin 2, chat 2026-11-26): the upper end is a rarely used direction, raised behind; the lower end points down, forward and medial. Two things remain before the transmission can be chosen.

1. **Group A: the required set.** Memo 66's B1 is one box built from per-angle extremes of different tasks. Basin 2 binds on two of its corners, so its 25.98 deg floor is probably an artefact of the box. Group A replaces the box with the union of per-task boxes, refines axis 1 inside basin 2, and checks the singular lower end against a folded-arms patch. Memo 66 did not check folded arms. By hand estimate the lower end is about 20 deg from it, in front of the abdomen and not inside the torso.
2. **Group B: the room.** The candidates are a thorax-side bevel differential (both motors in the thorax, input bevels coaxial with axis 1) and a serial roll stage (the roll actuator rides on the axis-1 stage). Every part on the axis-1 stage, bevels and spider in the first case and the roll actuator in the second, sweeps a solid of revolution about axis 1 as q1 moves through its 233 deg. So the governing quantity is the radius budget r(s) of a disc about axis 1 at each position s along it. Next comes the room in the thorax for motors coaxial with the inner end of axis 1. Last is the corridor for the clavicle member from the sternal joint to the SJC.

## What this brief does not do

- It chooses no transmission, actuator, gear or bearing, and it carries no torque. Catalogue dimensions appear only as scale marks (B, M2).
- It changes nothing under `tools/envelope/`, the model, the template, `pre_processor`, the sheet, `reservations.yaml` or any registry. Group B composes the oracle and the fields in a new `analysis/` script (Decisions, item 3).
- It does not decide the spine placement (`rm.v1-spine-reservation-decided`). Every room figure is reported with the v2 spine modules subtracted and without them.
- It sets no fall cap or stroke. The clavicle corridor is room only.
- It edits no decision record, roadmap node or thread record, and stamps nothing.

## Stop and ask before

- Any change under `tools/envelope/`, `field.py` and `oracle.py` included. If the measures below need one, stop with a description of it.
- Adding a dependency.
- Any required-set number that is not a snapshot address, a Gates 2016 table cell cited by table, row and column, or an inputs-file entry with its source.
- Choosing a step, tolerance or threshold by tuning toward a result.
- Placing the sternal joint node anywhere other than the rule in M4.

## Report as a finding, and stop if it blocks a task

- Gates 2016 Table 1 does not give per-task ranges for both plane of elevation and elevation (A, T1). Then Group A reports that and stops; Group B runs with memo 66's basin-2 axis unchanged.
- Basin 2 does not survive the refinement: the local search seeded at memo 66's basin-2 u1 converges more than 20 deg away, or into basin 1's region (upper end anterior, phi > 0).
- The thorax or upper-arm field treats the shoulder plane as skin (B, T0). The union measures assume it is a cut; say which it is before measuring.
- Any measure in Group B whose binding point is a slab overrun rather than skin or a reserved component.
- `part.arm.upper_member` (the CAD placeholder in `components/cad/upper_arm_R.yaml`) intrudes on r(s). It is reported, not subtracted (Decisions, item 4), but the memo must say where.

## Group A: the required set

### Inputs

`data/shoulder/inputs/axis_search.yaml` gains two entries. B1 stays as it is.

- **B1T, per-task ADL boxes.** For each task in Gates et al. 2016 Table 1, the plane-of-elevation and elevation ranges as the table gives them. One entry per task, each value citing its table cell. The required set is the union of the per-task boxes on B1's 1 deg grid, edges included. The plane convention is the one memo 66 confirmed. The cautions memo 66 recorded (participant means; the contralateral 105 deg edge) carry over to the entries they concern.
- **S4, folded arms (sensitivity only, `source_needed`).** A patch, not a point: plane of elevation 100 to 140 deg and elevation 20 to 50 deg on a 1 deg grid. From memory, chat 2026-11-26. It stands for the humerus with the arms folded across the chest. Look for a source giving humerothoracic angles for folded or crossed arms. If you find one, report it beside the patch; do not replace the patch without Joe.

### Gates

- **G-A1. Table consistency.** The union of B1T's per-task extremes equals B1's bounds (-65 to 105, 0 to 108) to the table's printed precision. If not, that is a finding and B1 is not replaced.
- **G-A2. Regression.** With B1 in place of B1T, the script still reproduces memo 66: basin 1 at 28.894 deg and basin 2 at 25.982 deg, to 1e-6 deg.
- **G-A3.** Memo 66's V1 to V7 pass unchanged on the refined run.

### Tasks

**T0. Baseline (no commit).** `fy thread build`, `fy test --quick`; record counts and timings. Confirm `data/shoulder/axis_search.json` is memo 66's output.

**T1. B1T (one commit; tests first).** Read Gates 2016 Table 1 (PMC4690598) and type B1T into the inputs file, cell by cell. The memo carries one table: task, plane range, elevation range, cell reference. G-A1.

**T2. Refined search (one commit; tests first).** Basis R' = A1 to A3 plus B1T. Run the global search as memo 66 did, then the local refinement seeded at memo 66's basin-2 u1, read by address from the committed output and not typed. Report:

- the global optimum and the basin-2 optimum, each with floor, sigma, gain, binding entries, q1 span and q2 span, beside memo 66's figures;
- S1, S2, S3 and S4 at the basin-2 optimum, not re-optimised: least angle to the singular line, rate gain and where. For S4, also the patch point nearest the lower end;
- the angle between the lower singular end and the nearest point of the model's torso geoms (the thorax and abdomen ellipsoids in `sim/models/freyja.xml`). This is a coarse indicator of whether the end points into the body, labelled as such; the geoms are design placeholders, not the envelope.

The output keeps memo 66's records and gains the refined ones. G-A2, G-A3.

**Checkpoint A.** Memo with the gate table, the B1T table, the basin comparison, the S1 to S4 table, findings and questions. Recommend the u1 for Group B: the basin-2 optimum under R'. `fy state`, stop. Group B starts only after Joe signs off this checkpoint and names the u1. His prompt will name it as an address into `data/shoulder/axis_search.json`.

## Group B: the room

### Frames and conventions

All geometry is in the thorax model body frame, which since volume-extractor brief 7 is the frame the oracle takes for the thorax (x anterior, y left, z up, mm, origin at the CJC). The SJC is the model's `upper_arm_right` position. u1 is the vector Joe names, oriented to its upper end. s is the signed distance along u1 from the SJC: positive toward the upper end (raised behind) and negative toward the lower end (down, forward, medial, into the chest). Shell t = 5 mm (adr-0007 D4) throughout. Margins are to the skin, never to a cut plane.

The upper arm's field is in its own segment frame. Its pose against the thorax at neutral follows the arm-union example (`data/envelope/examples/arm_union_*`) and `clearance_union`'s part offsets. Read those, do not retype them.

### Measures

**M1. Revolution budget r(s).** For s from -150 to +60 mm at 2 mm steps (one voxel), r(s) is the largest radius of a disc centred on the axis at s, normal to u1, whose every sample lies inside the skin with margin at least t. Find r by bisection to 0.5 mm on the feasibility of a thin cylinder (length 1 mm) posed along u1. Compute it under two bounds and two reservation states:

- **N, neutral union.** Thorax ∪ upper_arm_R at the neutral pose (`clearance_union`). This is optimistic: the arm moves away from its neutral place in other poses.
- **S, pose-proof.** Thorax ∪ B, where B is the largest ball centred on the SJC that lies inside upper_arm_R alone with margin t. A ball centred on the joint centre maps to itself under any arm rotation, so the arm carries it in every pose. This is conservative: it credits the arm with nothing beyond the ball. Compute the ball radius R_B with the oracle on upper_arm_R alone (a capsule of zero length is a sphere). Then a point's margin under S is the larger of its thorax margin and R_B - t - |p - SJC|.
- **Reservations off and on.** "On" subtracts the thorax components of `data/envelope/reserved/thorax.yaml` (the v2 spine modules), dilated by their clearance, as the free field does. The modules are alternatives across bodies (memo 59, finding 6), so "on" is the conservative side.

Report: r(s) at every 10 mm for the four combinations; the maximum r and its s; the s range over which r ≥ 20, 30 and 40 mm; R_B; and for each combination the binding surface at the maximum (skin, which body; or which module).

**M2. Stage budget for a body of axial thickness w.** From M1, for w = 10, 20, 30, 40, 50 and 60 mm, the largest R_w such that r(s) ≥ R_w for every s in some window of length w. Report R_w with its window, under S and N, reservations on and off. This is the number the transmission is sized against: a bevel set's pitch radius plus tooth depth, or a serial roll actuator's radial extent from the axis, must stay within R_w over its axial thickness. As scale marks only, print beside the table the AKH70-48 envelope (diameter and length from `catalog/actuators/akh70-48-specs.md`). A serial roll actuator lies along axis 2, perpendicular to u1, so its axial thickness along u1 is its diameter and its radial extent is its distance from the SJC plus its length. Do not compare beyond printing.

**M3. Thorax room for motors coaxial with the lower end.** Cylinders coaxial with u1 on the negative side, starting at s0 = -(R_B) (just outside the joint ball) and running toward negative s. For diameters 50, 60, 70, 80 and 90 mm, report the greatest length that fits, thorax alone, with reservations off and on, and what binds (skin, module, slab). Then, from the thorax free field (`fy envelope free --union`, reservations on), give the largest free sphere whose centre lies within 150 mm of the SJC, with its centre and radius. That is a hint at off-axis motor room for a belt or cable drive, labelled as such.

**M4. Clavicle corridor.** The sternal end node: Dumas 2015 Table 1's SUP landmark (`data/envelope/dumas2015_table1_female.json`, thorax, CJC origin, Dumas axes X anterior, Y up, Z right), scaled by the sheet's thorax length over Dumas's reference length 313 mm. Find the sheet's thorax length by address; check its value and that the trunk registration does not already place SUP. If it does, use that placement and say so. Convert to the model frame and offset laterally (toward the right shoulder) by c, the sternoclavicular joint's distance from the suprasternal notch. c is `source_needed`. Run c = 15, 25 and 35 mm as sensitivity rows; none is basis. Along the segment from that node to the SJC, report the largest capsule radius that fits in the thorax (t = 5 mm), reservations off and on, with where it binds. At the node, report the largest ball (the spherical sternal joint) that fits. The thorax body ends at the shoulder plane; the last stretch of the segment runs into the S union, so use S there and say where the switch happens.

### Gates

- **G-B1. Frames.** The SJC used equals the model's `upper_arm_right` position to 0.01 mm. u1 is unit to 1e-12 and equals the named address. The skin found along -y (lateral, right arm) at the upper arm's station 40 reproduces memo 59's skin distance (192.33 + 34.30 = 226.63 mm from the midline, in the thorax ledger frame; convert to the model frame through `frames.py`) within one voxel (2 mm).
- **G-B2. Synthetic.** On a synthetic cylinder body from `tools/envelope/synthetic.py` with a known axis, M1's bisection reproduces the analytic r(s) within one voxel at every s, for an axis parallel to the cylinder's and an axis tilted 30 deg to it.
- **G-B3. Ball.** R_B from the oracle equals the minimum over upper_arm_R's skin of the distance from the SJC, less t, within one voxel (computed independently from the field).
- **G-B4. Bound order.** At every s, r_S(s) ≤ r_N(s) and r(reservations on) ≤ r(reservations off). A violation is a defect.
- **G-B5.** Two builds are byte-identical, and the committed output equals a fresh build.

### Tasks

**T0. Baseline (no commit).** As Group A's T0. Also: read how the thorax and upper_arm_R fields treat the shoulder plane (cut or skin) and report it before measuring. Confirm the cache is present and current for thorax and upper_arm_R (the ledgers' input hashes).

**T3. Script and gates (one commit; tests first).** `analysis/shoulder_room.py`, no arguments, writing `data/shoulder/room.json` (generated, tracked, banner keys, no timestamp), the way `analysis/fall_room.py` writes `data/falls/room.json`. Tests: G-B1 to G-B5. The output test that needs the cache skips without it and says so.

**T4. M1 to M4 (one or more commits).** The measures above. Also write the r(s) profiles as a plot to an untracked path if matplotlib is pinned (memo 66 says it is), with the four combinations on one axis and the AKH70 radius marked, and give the path.

**Checkpoint B.** Memo per `CLAUDE.md` rule 6. Lead with the decision summary, in plain language: how large a disc about axis 1 the shoulder can hold, and over what length, under the pose-proof bound and the neutral bound; what that means for a bevel set against a roll actuator on the stage, as R_w beside the AKH70 marks; how much motor fits coaxially in the chest, and whether the spine reservation is what limits it; and whether the clavicle corridor is generous or tight. Then the gate table, the M1 to M4 tables, findings and questions. `fy state`, stop.

## Decisions this brief makes (Joe approves them by committing it)

1. The governing room quantity for a thorax-fixed axis-1 stage is the revolution budget r(s). Every part on the stage sweeps a solid of revolution about u1 over the q1 span, so a single disc-radius profile bounds bevels, spider and a serial roll actuator alike.
2. Two bounds, N and S, bracket the true room, because the body's shape around a moving joint is not defined by rigid segments. S's joint-centred ball is the only part of the arm's envelope that is pose-invariant. Neither bound is basis alone; adr-0025 reads both.
3. A new `analysis/` script composes the oracle and the cached fields rather than extending `tools/envelope/`. Its output, `data/shoulder/room.json`, is a tracked file carrying cache-derived numbers, as `analysis/elbow_flexion_clearance.py`'s output does. Joe approves that exception for this file by committing the brief.
4. `part.arm.upper_member` is a placeholder from the first CAD pass and will be redesigned around the shoulder, so it is not subtracted; its intrusion is reported. The v2 spine modules are reservations and are subtracted in the "on" state.
5. Group A replaces B1 with B1T in the basis only if G-A1 passes. S1 to S4 stay sensitivity entries until each has a source.

## Prerequisites for Joe

- Pull first: this brief was written into a clone that predates memo 66. Then point the "Current Ariadne brief" line in `CLAUDE.md` at this file, commit both, and prompt Code with the path, the `sha256sum` prefix and "Group A".
- At Checkpoint A, name the u1 for Group B (an address into `data/shoulder/axis_search.json`).
- If you know a source for the sternoclavicular joint's offset from the suprasternal notch, or for folded-arms humerothoracic angles, give it before the run.

## Amendment 1 (2026-11-26): Group B rulings after memo 68

This amendment supersedes the SJC sentence of "Frames and conventions", the first clause of G-B1, and the union rule of M1's N bound. It sets M4's sternal-node frame chain and adds T0a. Everything else above stands. Read memo 68 before starting. Tag: Delegate.

### Why a premise changes

The brief took the model's `upper_arm_right` position as the joint centre of the body envelope. Memo 68 finding 1 measured that this point sits 37.79 mm behind the envelope's shoulder joint, 8.5 mm from the back skin, with the arm field displaced 38 mm behind the thorax's. That was a wrong premise, not a result to tune toward. The room is a property of the skin, so it is centred where the skin's shoulder is. The disagreement itself is logged below and is not fixed here.

### Rulings

- **R1. Centre (memo 68 Q1).** The SJC for every Group B measure is the envelope's: `data/envelope/upper_arm_R.yaml#/mesh_nodes_mm/sjc` mapped through `bodies.trunk_map(...).apply`, less the thorax `origin_xyz`, then into the thorax model frame through `frames.segment_offset_mm`. It is computed by the script, never typed. Memo 68 measured it at (51.60, -192.33, -77.57) mm. The upper-arm field sits at its own origin there. u1 is unchanged: it is a direction, and the axis search does not depend on the centre's position.
- **R2. G-B1, first clause, replaced.** The SJC used equals R1's computed point to 0.01 mm. Its y and z equal `upper_arm_right`'s to 0.01 mm, and the x difference from `upper_arm_right` is reported (memo 68: 37.79 mm). u1 is normalised by the script and its residual reported; memo 68's 7.7e-14 is within the 1e-12 clause. The lateral clause (226.63 mm at station 40) stands.
- **R3. N bound, union rule (memo 68 Q2).** N holds a point by region, `occupancy.skin_field`'s rule, not by z-slab. `oracle.clearance_union` would credit the thorax field's extended-solid flesh beyond the shoulder cut (memo 68 finding 2). Use the existing function; do not change it. As a diagnostic only, report r_N at its maximum under the slab rule beside the region rule.
- **R4. M4 sternal node.** Dumas SUP is measured from the mesh's thorax centre line at the CJC, as `trunk_bodies.json`'s shoulder plane already is (its `x_note`), and goes through the same chain as R1. The scaling and the c rows are unchanged.
- **R5. The disagreement is logged, not fixed.** The memo gives one paragraph on what the 37.79 mm offset touches downstream. That covers the sim's arm inertia placement, the thorax-to-shoulder interface location in CAD (whose upper-arm frame origin is the sheet's SJC), and memo 59's shoulder fall rows. Give the source of the model's SJC x (sheet cell). Dumas 2015 supplies none (`dumas2015_table1_female.json`, `SJC_note`). Do not edit the model, the sheet, `analysis/fall_room.py` or `data/falls/room.json`.

### Task added

**T0a. Worker cap (own commit, before T3; tests first).** In `tools/testkit`, cap xdist's workers at min(logical CPUs, 12) (memo 68 finding 4). A test pins the cap with a mocked CPU count of 32 and of 4. Until this lands, set `PYTEST_XDIST_AUTO_NUM_WORKERS=12` for every run. Rule 1's full-suite condition applies to this commit.

### Open, not this session's work

Memo 67 finding 4 (`fy state` on a Current-brief line without backticks). Memo 66 finding 5 (the serial-fallback warning). Memo 68 finding 3 (memo 59's two "mesh SJC x" rows), which is due before adr-0025 sets the shoulder fall arc. The model-versus-envelope SJC reconciliation (R5), which is due before the thorax is designed in CAD.
