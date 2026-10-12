STATE: base f9049c793003 | brief sha256:f0fa6873f77a | snapshot sha256:4db751576eb9 | tests 495/495 | dirty no

# Stage 2, T3c checkpoint: trunk modes, double support, feasibility reporting, and where B's error comes from

Brief hash checked first: `sha256sum docs/briefs/stage2-brief.md` starts with `f0fa6873f77a` (no CRLF issue). Order followed: T8, T3c.0, then T3c.1 to T3c.5 with tests first. T6 and T7 were not started and no torque or power row was added to the envelope. All figures below were run from clean commits of this repository unless stated; every diagnostic is a subcommand of `sim/scripts/gait_diag.py` (`trunk`, `trunk-imu`, `double`, `polygon`, `pushoff`, `swing`, `masses`, `placement`, `foot`, `cop`, `a-agreement`), so each number can be regenerated. Strides: the first 4 per subject, 17 subjects, so 68 strides per speed unless a table says otherwise; the full 469 and 519 strides are used in the gait record.

## Headline

1. **The trunk explains the lateral discrepancy, and the data say the trunk is neither rigid nor perfectly counter-rotating.** With `counter_rotate` the lateral force goes from correlation 0.08 to 0.86 (1.4 m/s) and the lateral CoP error from 210 to 70 mm rms. The trunk IMU gives a trunk-to-pelvis amplitude ratio of 0.57 to 0.63 in roll and 0.76 to 0.93 in yaw, with phase lags of 65 to 116 degrees, so neither extreme is supported.
2. **Double support was over-constrained by the old rule.** The measured total CoP is inside the hull of Freyja's two contact polygons in 94% of double-support frames (outside by a median 9 mm), against 28% to 29% outside for B with `counter_rotate` (median 24 to 29 mm) and 72% to 75% with `rigid` (median 77 to 85 mm). The earlier "measured CoP fails in 72 to 75% of double-support frames" came from testing each foot's CoP against its own polygon, which is the wrong test.
3. **B's leg torques remain 2.4 to 3.5 times A's at the hip and knee, and the double-support bound does not change that.** The bound differs from the nominal torque by between -2 and +7 N m at the 95th percentile because the peaks occur in single support, where there is no split to choose. The cause is the fore-aft CoP error (mean 65 to 66 mm too far back, 102 to 126 mm rms), which is mostly where the pelvis and trunk mass sits and what its fore-aft motion adds; segment masses explain about 12 mm of the rms and 18 mm of the mean.
4. **A rigid, toeless foot box cannot represent push-off.** In the last decile of stance the measured CoP, placed on Freyja's foot, is outside that foot's polygon in 66% to 85% of single-support frames and in 99% to 100% of double-support frames (median 32 to 105 mm). It is an open item for Joe, not a change.

## T8. `fy state` and `docs/STATE.md` (commit 4bd2b15)

`python tools/fy state [--no-run]` writes `docs/STATE.md`: banner, the STATE line, base commit and branch, dirty flag and the hash of `git diff HEAD` with `docs/STATE.md` excluded, the brief path from `CLAUDE.md` and its hash with line endings normalised to LF, snapshot and model hashes, test counts, every check with tier and outcome, waivers with `confirmed` and review date, latest run per scenario, latest gait record, the memo and brief file names, and the tracked-file count (not counting STATE.md itself). Logic is in `sim/scripts/state.py`; `fy` only calls it. Nine tests (`tests/test_state.py`) run against a throwaway git repository: byte-identical runs, one byte of the brief changes only the brief hash and the base, an untracked or modified file makes the tree dirty, generating the file leaves the dirty state and hash unchanged, CRLF does not change the brief hash. CONVENTIONS section 2 names `docs/STATE.md` as generated and tracked; `CLAUDE.md` has the new line. The dirty flag also counts untracked files, so "dirty no" means nothing is untracked either.

## T3c.0 housekeeping and naming (commit cf658f5)

- `docs/memos/memo4-stage2-t3b.md` is the `dee54b0` report, unchanged.
- Renames: `pelvis_pitch_offset_deg`, `pitch_mean: measured | <degrees>`, `trunk: rigid | counter_rotate` in `walk_treadmill.yaml`; GAIT.md and the record say pitch, roll and yaw. `camargo_mapping.yaml` and the audit README record that the dataset's `pelvis_tilt` is the roll, `pelvis_list` is the sagittal pitch (anterior pitch is minus `pelvis_list`) and `pelvis_rotation` is the yaw. A numeric `pitch_mean` marks methods A and H `hybrid` in the record (`hybrid_methods`, tested).
- **Root referencing (c).** The hip-centre midpoint was already in the retargeted root that B and H use in every step 2 to 4 figure of `memo4` (`Cycle` takes the hip centres whenever they are passed). Only the first full gait record (20261011-1413) used the pelvis origin. Re-measured now, 4 strides per subject, measured pitch, rigid trunk:

| 1.4 m/s | stance float (mean of per-stride maxima) | penetration | swing clearance min | stance slip rms |
|---|---|---|---|---|
| root at the pelvis origin | 45.8 mm | 0.0 mm | 6.3 mm | 0.36 m/s |
| root at the hip midpoint | 45.5 mm | 0.0 mm | 5.8 mm | 0.35 m/s |
| earlier figures | 46.1 mm | | | 0.34 m/s |

At 1.6 m/s: 47.8 and 46.5 mm, slip 0.34 and 0.33 m/s. So the referencing change did not move the float or the slip; the float is not an origin offset.
- **Regression (d).** With the rigid trunk the `dee54b0` numbers reproduce exactly: the `cop` step output at 1.4 m/s differs only in its header label, and the A agreement table is identical (hip 0.845/16.5%, 0.911/14.7%; knee 0.898/13.3%, 0.913/12.7%; ankle 0.994/11.6%, 0.995/10.9%). A golden hash of the rigid retargeted cycle (recorded before T3c.1) is now a test.
- **Manifest.** Static and walking means for pelvis roll and pitch are separate, per subject. Pitch (anterior positive): static median -0.2 degrees (range -6.4 to 5.0); walking median -7.6 at 1.4 m/s (range -14.4 to 1.0) and -7.0 at 1.6; walking minus static median -5.0 and -3.9 degrees. Roll: static median 0.4 (range -3.7 to 8.6), walking median -0.7 (range -2.6 to 1.4). A side check against the ASIS and PSIS markers (6 subjects): the marker-based pelvic tilt changes by -4.5 to +1.1 degrees from static to walking, the IK pitch by -0.5 to -14.7. The sign agrees; the size does not for AB12 and AB19 (-2.0 against -14.7, -2.6 against -13.1). The dataset's IK pelvis pitch is not what the pelvic markers alone would give for some subjects. A and H use the IK pitch, which is what the dataset's inverse dynamics used.

## T3c.1 trunk modes (commit 19747da)

`trunk: counter_rotate` sets the lumbosacral lateral and axial joints so that the abdomen, thorax and head hold their standing roll and yaw in the world. The construction is exact: with the pelvis rotation written as Ry(theta) Rz(a) Rx(l) (intrinsic Y-Z-X), joints Rx(-l) Rz(-a) leave the abdomen at Ry(theta), the pelvis's pitch only. Tests (`tests/test_retarget.py`), all first and failing before the implementation: world roll and yaw of abdomen, thorax and head are constant at the standing values to 1e-9 at the 101 phase points while pitch follows the pelvis; the joints are zero when the pelvis does not roll or yaw (a standing input stays standing); integrating `qvel` with `mj_integratePos` returns `qpos` to 1e-9 including the new joints; flipping the sign breaks the constancy test (mutation); the rigid output is hash-identical to before. Between phase points the cancellation is a cubic spline of exact values and stays within 0.02 degrees (also tested). The compensation columns are not low-pass filtered, because a filter does not commute with the nonlinear decomposition.

Results, B and H under both modes, A as the reference (pitch measured, 68 strides per speed):

| | 1.4 rigid | 1.4 counter_rotate | 1.6 rigid | 1.6 counter_rotate |
|---|---|---|---|---|
| lateral force, peak-to-peak ratio / correlation (like for like) | 1.85 / 0.08 | 1.31 / 0.86 | 2.18 / -0.05 | 1.42 / 0.78 |
| fore-aft ratio / correlation | 1.00 / 0.87 | 1.06 / 0.89 | 1.07 / 0.84 | 1.13 / 0.86 |
| vertical peak ratio / correlation | 0.97 / 0.97 | 0.97 / 0.97 | 0.97 / 0.97 | 0.97 / 0.97 |
| A root-row residual, force rms % BW (native / filtered) | 19.0 / 17.2 | 13.8 / 11.5 | 23.3 / 20.8 | 17.2 / 14.0 |
| A horizontal moment residual rms N m (native / filtered) | 70.8 / 66.9 | 58.8 / 53.5 | 79.3 / 74.4 | 63.6 / 56.4 |
| H horizontal moment residual rms N m | 137.7 | 73.6 | 166.3 | 89.1 |

B and H use Freyja's own total force, so they share the force rows; A uses the measured force. Agreement with the dataset's moments, both limbs pooled (correlation, RMS as % of peak-to-peak), 1.4 m/s:

| joint | method | rigid | counter_rotate |
|---|---|---|---|
| hip ab/adduction | B | 0.74, 68% | 0.78, 35% |
| | H | 0.12, 78% | 0.83, 31% |
| | A native / filtered | 0.90, 25% / 0.97, 18% | same (leg torques do not depend on the trunk) |
| hip rotation | B | 0.56, 80% | 0.46, 44% |
| | H | 0.04, 44% | 0.82, 22% |
| | A native / filtered | 0.81, 22% / 0.86, 18% | same |
| ankle inversion | B | -0.18, 567% | 0.05, 172% |
| | H | -0.02, 90% | -0.13, 104% |
| | A native / filtered | -0.12, 109% / -0.12, 108% | same |

1.6 m/s follows the same pattern (hip ab/adduction B 0.72 to 0.78, H 0.01 to 0.75, A filtered 0.97). The ankle inversion moment disagrees with the dataset for every method including A (correlation about -0.1, RMS above 100%). It is not a sign flip (that would give a strongly negative correlation); the dataset's subtalar axis is oblique and Freyja's `ankle_ie` is a pure anteroposterior axis, so the two moments are about different axes. Under the brief's rule ("a sign disagreement is a mapping error until explained") this is explained by the axis difference but not proved; it needs your decision (question 3).

Lumbosacral lateral and axial joints, peak per stride (finding for the Joint ROM sheet's functional-demand column; both joints are unlimited today, nothing clipped):

| | 1.4 counter_rotate | 1.6 counter_rotate |
|---|---|---|
| lateral bending peak angle, median / 95th / max | 5.6 / 7.4 / 8.0 deg | 6.2 / 8.4 / 9.7 deg |
| axial rotation peak angle, median / 95th / max | 7.5 / 11.9 / 13.4 deg | 7.6 / 13.0 / 16.7 deg |
| lateral bending peak torque, mean / 95th / max | 16.5 / 23.5 / 27.1 N m | 18.9 / 34.3 / 83.3 N m |
| axial peak torque, mean / 95th / max | 0.5 / 0.6 / 0.7 N m | 0.5 / 0.9 / 1.8 N m |
| peak speed, 95th (lateral / axial) | 1.43 / 1.38 rad/s | 1.64 / 1.66 rad/s |
| peak power 95th (lateral: positive / regeneration; axial) | 15 / 17 W; 1 W | 11 / 38 W; 1 W |

For comparison, the rigid mode has to carry the trunk through the pelvis's roll: lateral bending torque 68.9 N m mean, 95.6 N m 95th percentile at 1.4 m/s (82.8 and 112.5 at 1.6). The sagittal rows are the same in both modes by construction.

## T3c.2 is the trunk counter-rotating? (commit d876558)

The dataset has no shoulder or trunk markers (markers: ASIS, PSIS, thigh, shank, knee, ankle, heel, toe only), so I used the trunk IMU (accelerometer in g, gyroscope; the gyro reads as rad/s because its rms is within a factor 0.6 to 1.9 of the pelvis's). The IMU's orientation is unknown; I find it from the accelerations (vertical from the mean, heading from the dynamic horizontal part, both low-passed at the kinematics' 6 Hz) against the pelvis's specific force from the kinematics, then integrate the gyro in the pelvis axes (drift removed) and compare first harmonics with the pelvis's own angles. The arithmetic is in `sim/scripts/trunkimu.py` with tests on synthetic signals (alignment recovers a known orientation to 1e-9, a half-turn flip is detected, amplitude ratio, lag and cancelled fraction recovered exactly).

Alignment quality (accelerometer correlation per pelvis axis forward / up / right): median over 17 subjects 0.85 / 0.97 / 0.70, worst 0.64 / 0.95 / 0.10. Median across subjects, with the lower and upper quartile in brackets:

| | amplitude (pelvis / trunk) | trunk-to-pelvis ratio | phase lag | cancelled fraction |
|---|---|---|---|---|
| 1.4 roll | 3.7 / 2.2 deg | 0.57 [0.45, 0.76] | 101 deg [52, 122] | 1.27 [0.94, 1.39] |
| 1.4 yaw | 4.6 / 4.4 deg | 0.93 [0.67, 1.42] | 70 deg [53, 75] | 0.69 [0.47, 0.79] |
| 1.6 roll | 3.6 / 2.6 deg | 0.63 [0.56, 0.80] | 116 deg [67, 120] | 1.32 [1.12, 1.44] |
| 1.6 yaw | 5.1 / 4.6 deg | 0.76 [0.62, 1.30] | 65 deg [53, 80] | 0.71 [0.62, 1.08] |

Restricting to the 11 subjects whose alignment is at least 0.6 on every axis changes little (roll ratio 0.58 and 0.74, lag 74 and 108 degrees; yaw ratio 0.74 and 0.67, lag 65 and 54 degrees). The cancelled fraction is one minus the real part of the complex ratio; a value above 1 in roll means the trunk's roll is partly opposite to the pelvis's, but it is reached through a quarter-cycle lag, so a single scalar misrepresents it. The trunk's absolute amplitudes (2.2 to 2.6 degrees of roll, 4.4 to 4.6 of yaw) are the more direct numbers. **Nothing adopted.** The ratio is clearly not 1 and clearly not 0. If you want a parameter, the options are (a) `counter_rotation_fraction` per axis using the cancelled fraction (about 0.7 for yaw, about 1.0 for roll, clipped) and ignoring the lag, or (b) a gain and a lag per axis. Estimate caveats: the IMU location on the trunk is not stated, the sensor-to-pelvis rotation is estimated from accelerations that include the trunk's own rotation terms, and integrating gyro rates has a drift correction that assumes periodicity.

## T3c.3 double support (commits b047194, 07a88b1)

The total CoP is computed from the root rows and is independent of the split (property-tested: for every solution the root rows close to 1e-7 of body weight and the CoP matches `cop_decomposition` to 1e-12). The feasible set is every split alpha and every pair of CoPs inside their polygons whose alpha-weighted mean is the total CoP (21 values of alpha, 5 points of the right-foot CoP along its feasible segment, found by linear programs along the polygon's longest direction). It is non-empty exactly when the total CoP is in the hull of the union of the two polygons, and feasibility is that test. The weighted-mean identity holds to 1e-12; a CoP outside the hull is reported infeasible with its distance; shrinking a polygon turns a feasible frame infeasible (mutation); the bound includes the nominal case whenever that is feasible, so the worst case is at least the nominal torque (tested). **A defect I found and fixed (07a88b1):** the first run called a frame infeasible when the 21-point alpha grid happened to miss a thin feasible set; feasibility is now the hull test alone, and the first run's baseline figures (62% to 65% outside) were wrong. Figures below are from the fixed code.

| double-support frames | 1.4 rigid | 1.4 counter_rotate | 1.6 rigid | 1.6 counter_rotate |
|---|---|---|---|---|
| B: total CoP outside the hull | 72.1% | 28.0% | 75.4% | 29.3% |
| B: outside distance, median / 95th | 77 / 213 mm | 24 / 90 mm | 85 / 212 mm | 29 / 109 mm |
| measured total CoP on Freyja's feet, outside | 6.3% | 6.3% | 8.7% | 8.7% |
| measured: outside distance, median / 95th | 9 / 33 mm | 9 / 33 mm | 7 / 36 mm | 7 / 36 mm |
| nominal split inside the feasible set | 8.1% | 14.9% | 3.6% | 9.6% |
| nominal rule's own per-foot CoP placement fails | 100% | 100% | 100% | 100% |
| measured force share inside the feasible set | 8.4% | 30.3% | 5.8% | 22.7% |

The nominal rule's placement (both CoPs at the same normalised offset along their boxes with a shared lateral shift) fails in every frame, which is why the old per-foot test over-constrained the problem; the nominal split is still reported because it is the sizing bracket. Peak joint torque over strides, mean / 95th, N m, 1.4 m/s (nominal B | bound B | A filtered), right side:

| joint | rigid | counter_rotate |
|---|---|---|
| hip flexion | 169.5 / 194.7 \| 169.8 / 194.7 \| 48.1 / 67.1 | 172.0 / 196.9 \| 172.5 / 199.7 \| 48.1 / 67.1 |
| knee | 129.2 / 164.4 \| 129.5 / 164.4 \| 54.1 / 72.0 | 122.1 / 144.9 \| 123.0 / 144.9 \| 54.1 / 72.0 |
| ankle dorsiflexion | 141.5 / 206.2 \| 141.5 / 206.2 \| 132.8 / 149.9 | 155.4 / 201.2 \| 153.9 / 201.2 \| 132.8 / 149.9 |
| hip ab/adduction | 144.3 / 172.2 \| 144.3 / 172.2 \| 66.3 / 84.1 | 80.2 / 90.5 \| 80.2 / 90.5 \| 66.3 / 84.1 |

(1.6 m/s is in the same pattern: hip flexion B 186.8 / 208.5 against A 58.3 / 84.4.) The bound differs from the nominal torque by -2 to +7 N m at the 95th percentile (largest: hip flexion at 1.6 m/s rigid, 208.5 to 215.5 N m). It can be lower than the nominal because it is the worst case over the feasible set, and the nominal case is in that set only when its own CoP placement is inside the polygons, which it never is (so the "worst case is at least the nominal torque where the nominal case is feasible" test is exercised on a constructed pose, not on walking data). **This contradicts the brief's reasoning that the bound is a useful bracket for sizing:** the peaks are single-support peaks, where the force split plays no role, and the double-support bracket cannot reach the factor of 2.4 to 3.5 between B and A at the hip and knee. The ankle is the exception: B and A agree there (141 against 133 N m) because the CoP error is fore-aft and the ankle lever is mostly set by the foot.

## T3c.4 feasibility reporting (commits 1fe549a, f34cf90, f9049c7)

Everything that reports a polygon test now gives rate and outside-distance distributions for B and for the measured CoP placed on Freyja's own foot at the same normalised place (heel and toe-tip markers; the baseline uses this mapping whatever mapping A and H use, tested), single support (the stance foot's polygon) and double support (the hull of both), at polygon bands of 10, 25 and 40 mm. The band says which foot-box vertices form a polygon (those within the band of that foot's lowest vertex); 25 mm is the definition in force and 10 and 40 mm are sensitivity. Outside medians and 95th percentiles are over outside frames. Rates are percentages of frames. No pass or fail.

| 1.4 m/s | band | support | B rigid | B counter_rotate | measured |
|---|---|---|---|---|---|
| | 10 mm | single | 95.1% (161 / 344 mm) | 82.9% (74 / 203) | 73.5% (50 / 178) |
| | 10 mm | double | 83.6% (88 / 238) | 65.0% (35 / 111) | 45.4% (23 / 99) |
| | 25 mm | single | 88.5% (138 / 315) | 58.0% (37 / 146) | 31.6% (12 / 96) |
| | 25 mm | double | 72.1% (77 / 213) | 28.0% (24 / 90) | 6.3% (9 / 33) |
| | 40 mm | single | 87.2% (133 / 310) | 51.6% (30 / 125) | 24.5% (11 / 67) |
| | 40 mm | double | 69.1% (77 / 213) | 25.2% (23 / 90) | 3.1% (8 / 27) |
| 1.6 m/s | 25 mm | single | 93.6% (187 / 406) | 71.0% (57 / 206) | 42.7% (14 / 69) |
| | 25 mm | double | 75.4% (85 / 212) | 29.3% (29 / 109) | 8.7% (7 / 36) |

B's median outside distance at 25 mm with the pitch mean measured, then plus and minus 5 degrees (a diagnostic, not a design choice), 1.4 m/s, single / double support: rigid 138 / 77 mm, 146 / 84 mm (+5), 134 / 78 mm (-5); counter_rotate 37 / 24 mm, 49 / 25 mm (+5), 49 / 32 mm (-5). With the counter-rotating trunk the measured pitch is the best of the three (a 5-degree change in either direction adds 12 mm to the single-support median and 17 to 22 points to the outside rate); with the rigid trunk the three are within 12 mm of each other.

**Can a rigid, toeless foot box represent push-off? No.** The measured CoP on each foot's own polygon, by decile of that foot's stance, 1.4 m/s, `counter_rotate` kinematics (outside rate, median outside distance):

| stance decile | single support | double support |
|---|---|---|
| 0 to 10 | none | 85.2% (38 mm) |
| 10 to 20 | 19.1% (5 mm) | 39.7% (202 mm) |
| 40 to 50 | 12.5% (13 mm) | 79.3% (27 mm) |
| 60 to 70 | 30.9% (11 mm) | 39.5% (32 mm) |
| 70 to 80 | 38.3% (16 mm) | 87.2% (57 mm) |
| 80 to 90 | 33.5% (17 mm) | 99.0% (32 mm) |
| 90 to 100 | 65.9% (9 mm) | 99.7% (86 mm) |

At 1.6 m/s the last decile is 85.4% (17 mm) in single support and 100% (105 mm) in double support. In mid-stance the failures are small and in the heel and toe edges; in the last 20% of stance, mostly double support, the measured CoP of the trailing foot is beyond the pitched box's polygon by tens of millimetres in essentially every frame. That is consistent with a missing toe joint: with the heel up, the rigid box rests on its toe edge (a segment), and the forefoot where the CoP actually is does not exist. The total CoP still passes the hull test in 94% of double-support frames because the leading foot's polygon covers it. This is an open item for you, not a change; no model change was made.

## T3c.5 where B's error comes from (commits 3f9bfcf and the ones above)

Order as the brief: swing-leg inertia, segment masses, foot lateral placement. Single support only, 1.4 m/s unless a speed is named, 5267 frames (5423 at 1.6). Offsets are from the stance ankle in millimetres (fore-aft x, lateral y).

**1. Swing-leg inertia (partition by group).** B's CoP is split exactly into where each group's mass sits and what its motion adds (identity tested to 1e-6 against the whole-body CoP; groups: stance leg, swing leg, pelvis with trunk, head and arms).

| group (mass share) | mass position, mean / rms | what its motion adds, mean / rms (rigid) | counter_rotate |
|---|---|---|---|
| stance leg (20.1%) | (15, 0) / (23, 4) | (-13, 0) / (35, 10) | same |
| swing leg (20.1%) | (27, 0) / (51, 38) | (15, 0) / (21, 15) | same |
| pelvis and trunk (59.8%) | (21, -4) / (92, 55) (counter_rotate: (21, -3) / (91, 48)) | (-16, 0) / (120, 192) | (-15, 0) / (124, 82) |

B's CoP minus the ankle: mean (49, -3) rigid, (50, -3) counter_rotate; the measured CoP minus the ankle: mean (116, 0). So B's CoP sits on average 66 mm behind the measured one (65 mm with counter_rotate), with rms error (105, 210) rigid and (102, 70) counter_rotate. The swing leg contributes little (motion rms 21 mm fore-aft and 15 lateral) and the stance leg less; the pelvis and trunk group dominates both the position term and the motion term, and the large lateral motion term (192 mm rms rigid) is the trunk that `counter_rotate` removes (82 mm). At 1.6 m/s the same: mean error -66 mm, rms (126, 254) rigid and (122, 81) counter_rotate.

**2. Segment masses (in-memory copies, never saved; `sim/scripts/datasetmass.py`, tests in `tests/test_partition.py`).** Mapping: pelvis to pelvis (mass fraction and centre of mass above the hip midpoint); thigh to femur and shank to tibia (mass fraction and centre of mass down the bone, scaled by the leg-length ratio); foot to talus plus calcaneus plus toes (mass fraction only); the trunk, head and arms group to the dataset's single torso body (group total takes its fraction, Freyja's split inside the group is kept). Masses are the dataset model's fractions times Freyja's total, so the total is unchanged; inertias scale with mass. B's CoP minus the measured CoP, rms (fore-aft, lateral) and mean fore-aft:

| | Freyja's masses | dataset masses |
|---|---|---|
| 1.4 rigid | (105, 210); mean -66 | (92, 210); mean -48 |
| 1.4 counter_rotate | (102, 70); mean -65 | (90, 68); mean -46 |
| 1.6 rigid | (126, 254); mean -66 | (114, 251); mean -47 |
| 1.6 counter_rotate | (122, 81); mean -66 | (110, 77); mean -46 |

Substituting the dataset's segment masses removes about 12 mm of the rms fore-aft error and about 18 mm of the 66 mm mean offset, and changes the lateral error by 2 to 4 mm. Mass distribution is a minor contributor.

**3. Foot lateral placement.** The stance foot's centre minus the measured CoP's lateral position (hip-referenced, so it measures where the foot is, not where the CoP is on it): -2 mm, sd 17 mm at 1.4 m/s and -2 mm, sd 18 mm at 1.6. The foot's lateral position agrees with the human CoP to within the foot's half width. B's CoP minus the stance foot centre, lateral: -2 +/- 199 mm rigid and -1 +/- 58 mm counter_rotate at 1.4 (+2 +/- 248 and 0 +/- 72 at 1.6). Freyja's ankle-to-ankle width in single support is 189 +/- 35 mm (185 +/- 37 at 1.6). Foot lateral placement is not the cause; what remains laterally with `counter_rotate` is the trunk's residual and the swing leg's lateral motion.

**Where that leaves B.** B remains infeasible by the distance metric (see T3c.4), with the fore-aft offset dominated by the pelvis-and-trunk group and not corrected by the masses. Per the brief, the baseline and envelope rows would be built on A and H, flagged provisional because they borrow the human CoP, and B's failure recorded as a finding: retargeted human kinematics are not dynamically consistent with Freyja's mass distribution and foot, which is a statement about the controller project and not a bug here. I have not written any of that into a record or the envelope.

## Where results sharpened or contradicted the brief's reasoning

- The brief's T3c.3 reasoning (over-constrained placement) is confirmed: the measured total CoP passes the hull test in about 94% of double-support frames, where a per-foot test fails it in 72% to 75%.
- The brief's expectation that a double-support bracket sizes the loads is not supported (bound within 3 N m of nominal).
- The brief's suspicion that the missing toe is a large part of the failure is supported by the push-off table, but it explains the late-stance failures; the early-stance failures (decile 0 to 10, 85%) happen with the heel on the ground and are not a toe effect (a rolled foot at heel strike).
- `pelvis_list` pitch during walking differs from its static value by -5.0 degrees (median) and the IK pitch disagrees with the ASIS/PSIS markers for AB12 and AB19 by about 12 degrees; this affects what "the standing pose" pitch means for a design value but not A, H or the measured-pitch B.
- The first T3c.3 run and an early T3c.4 polygon run contained defects of mine (the grid-miss rule, and an edit that had not applied); both are fixed, tested, and their figures are not used here.

## Tolerances and constants I chose

| constant | value | why |
|---|---|---|
| polygon band (`HULL_BAND_M`, = `SEGMENT_TOL_M`) | 25 mm | the decided definition; 10 and 40 mm as sensitivity |
| feasible-set grid | 21 splits, 5 points of the right-foot CoP | the brief's defaults |
| plane tolerance | 1e-9 m | round-off in hull membership, not a threshold |
| trunk-compensation test | 1e-9 at phase points, 0.02 degrees between | exact by construction at the grid; spline error between |
| IMU alignment filter | 6 Hz, quality cut 0.6 for the robustness row | same cut-off as the kinematics; the cut is a sensitivity row, not a selection |
| partition and body-acceleration step | 1e-6 s | central difference of exact Jacobians; identity tests pass to 1e-6 |
| first 4 strides per subject in diagnostics | cap 4 | speed; the gait record uses all strides |

## Questions for Joe

1. Trunk: which representation do you want if the rigid and perfectly counter-rotating modes are both unsupported? A `counter_rotation_fraction` per axis (yaw about 0.7, roll about 1.0, ignoring the 65 to 116 degree lags), a gain and lag per axis, or keep the two modes and show the spread between them as the uncertainty?
2. Pelvis pitch: the IK pitch and the pelvic markers disagree for some subjects, and walking pitch is 5 degrees below static. Is the IK pitch (what the dataset's own inverse dynamics used) the right reference for the headline B, as now?
3. Ankle inversion: the dataset's moment is about an oblique subtalar axis and Freyja's is about a pure anteroposterior axis, so no method agrees (correlation about -0.1). Do you want the dataset's moment projected onto Freyja's axis before comparison, or `ankle_ie` left out of the agreement table?
4. Foot: is a toe joint (a model change) to be proposed, given that late stance cannot be represented without one? I made no change.
5. The pending decision on envelope torque rows is untouched; with these results `A_filtered` still meets the proposed band (0.91 to 0.995, 10.9% to 14.7%) and B does not (hip and knee torques 2.4 to 3.5 times A's). I did not re-run H's sagittal agreement in this checkpoint.

## Commits (all tests first; one commit per task except where noted)

4bd2b15 T8; cf658f5 T3c.0; 19747da T3c.1; d876558 T3c.2; b047194 and 07a88b1 T3c.3 and its fix; 1fe549a T3c.4, f34cf90 its first fix (this commit also carried the T3c.5 files `partition.py`, `datasetmass.py` and `tests/test_partition.py`, added by mistake with `git add -A`), 285ea25 and f9049c7 (the second fix, after the first attempt had not applied); 3f9bfcf T3c.5. `docs/STATE.md` was generated on f9049c7 with `fy state` and is committed with this memo.
