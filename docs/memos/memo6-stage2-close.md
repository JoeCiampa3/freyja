STATE: base c651bccdddd2 | brief sha256:3903f300f9e8 | snapshot sha256:4db751576eb9 | tests 560/560 | dirty no

# Stage 2 close: baseline, envelope rows, and the four T9 diagnostics

Brief hash checked first: `sha256sum docs/briefs/stage2-brief.md` starts with `3903f300f9e8` (no CRLF issue; it was already committed as `1941973`). Order followed: T6, T7, T9.1 to T9.4, then this memo. Every figure comes from a clean commit unless stated. Two records exist: `gait.20261011-2232-walk_treadmill` (T6, commit `2e54d18`, the baseline's source) and `gait.20261011-2317-walk_treadmill` (T9.3, commit `b99a5ba`, the one the envelope reads); their `all` statistics are identical, the second adds the without-pitch-flagged set. Both: 17 subjects, 469 strides at 1.4 m/s and 519 at 1.6, B, H, `A_native`, `A_filtered`, `trunk` in both modes, `pitch_mean: measured`. Report subcommands are in `sim/scripts/gait_diag.py` (`harmonic`, `pitch`, `trunkcom`, `standing`, `toe`), so each number can be regenerated.

## Findings

1. **Only `A_filtered` meets the band, so only it is baselined and only it enters the sagittal envelope rows.** Correlation / RMS % of peak-to-peak, both limbs pooled, mean over subject-strides (T6 record, identical in both trunk modes for A):

| 1.4 m/s | hip | knee | ankle | meets |
|---|---|---|---|---|
| `A_filtered` | 0.914 / 14.5 | 0.915 / 12.3 | 0.994 / 10.9 | yes |
| `A_native` | 0.832 / 17.0 | 0.898 / 13.3 | 0.993 / 11.5 | no (hip both, knee correlation) |
| H rigid / counter_rotate | 0.725 / 37.2, 0.725 / 37.1 | 0.692 / 26.7, 0.715 / 26.0 | 0.979 / 12.7, 0.980 / 12.6 | no (hip, knee) |
| B rigid / counter_rotate | 0.775 / 58.7, 0.776 / 59.1 | 0.231 / 67.6, 0.210 / 64.8 | 0.243 / 40.6, 0.329 / 37.8 | no (all three) |

   At 1.6 m/s: `A_filtered` 0.926 / 13.3, 0.922 / 11.7, 0.994 / 11.1 (meets); `A_native` 0.844 / 16.0, 0.902 / 12.8, 0.992 / 11.8 (no: hip); H 0.726 / 36.1, 0.692 / 26.6, 0.973 / 14.0 rigid and 0.728 / 35.9, 0.715 / 25.9, 0.974 / 13.9 counter_rotate (no: hip, knee); B 0.794 / 51.8, 0.274 / 64.4, 0.205 / 46.5 rigid and 0.794 / 52.3, 0.253 / 61.5, 0.284 / 43.2 counter_rotate (no). **H's sagittal agreement, which T3c did not re-run:** its ankle meets the band (0.98 / 12.6 and 0.974 / 13.9 at counter_rotate) but its hip and knee do not, because H uses Freyja's own total force at the human CoP and inherits the force error. Without the offset subjects, and without the pitch-flagged subjects, every verdict is the same.
2. **B stays infeasible and does not agree with the dataset; its failure is recorded, not worked around.** 25 mm band, single / double support, outside rate: B rigid 88.9% / 72.9% (1.4) and 93.9% / 73.8% (1.6); B counter_rotate 57.3% / 25.4% and 70.7% / 28.2%; the measured CoP on Freyja's feet 31.7% / 6.3% and 41.6% / 9.3%. Friction above mu: 0.0% everywhere. B's 95th-percentile hip and knee torques are 2.1 to 2.9 times `A_filtered`'s at both speeds (hip flexion right 191 and 194 N m against 70 at 1.4, 220 and 226 against 77 at 1.6; knee right 166 and 151 against 72, 212 and 193 against 93).
3. **T7's stop condition did not trigger.** The torques of `lsj_fe`, `lsj_lat`, `lsj_ax`, `tj_fe` and `cj_fe` are identical across `A_native`, `A_filtered`, H and B to 1e-9 per frame in both trunk modes (two subjects, both speeds, all 100 frames); the envelope has the bracket rows.
4. **T9.2 contradicts the brief's reasoning.** Freyja's trunk group is 45.1% of the body and its centre of mass is 48.0 mm behind the hip-centre midpoint, which confirms memo3's "about 50 mm". The dataset's torso (45.5%) is 56.0 mm behind it (median of 17 subjects, scaled by leg-length ratio; 58.1 mm unscaled). Moving Freyja's trunk group to the dataset's offset makes B worse, not better. The ramrod placement is not what puts B 66 mm behind. Stopped there, as the brief asks.
5. **T9.4 contradicts the brief's premise: the dataset's toe is locked.** `mtp_angle` is exactly 0.0 degrees in all 1976 stride-feet and each subject's largest `mtp` inverse-dynamics moment is 0.13 to 0.30 N m. There is no toe angle, moment or power to report, so `decisions/0001-toe-joint.md` carries no toe load and says so.
6. **A human-like trunk is nearer `counter_rotate` than `rigid` for the lateral lumbosacral torque (T9.1).** At the T3c.2 medians the lateral torque 95th percentile is 32.1 N m (1.4) and 40.7 N m (1.6), against 23.5 and 27.6 for `counter_rotate` and 93.0 and 110.4 for `rigid`; the joint angle needed is larger than `counter_rotate`'s (8.9 and 10.2 degrees against 7.8 and 8.6; `rigid` holds the joint at 0).
7. **4 of 17 subjects are pitch-flagged (T9.3): AB07, AB12, AB18, AB19.** They change nothing in the band verdicts and at most 3.9 to 5.3 N m in a leg joint's 95th-percentile peak torque for `A_filtered` (B 9.0 to 15.0).

## T6 baseline (commits `2e54d18`, `db1b9d8`)

- `trunk` accepts a name or a list; every result and sensitivity table is keyed by mode (`results[speed][mode]`). `GAIT.md` was compacted to fit two modes under 400 lines (371). `gait-summary/1` is amended in place (see question 7).
- The band is two named constants (`BAND_CORR = 0.9`, `BAND_RMS_PCT = 15.0`, from your Decisions block), a verdict per method, speed and mode, and per exclusion set. `baseline_methods` baselines a method only if it meets the band at every speed and mode: `A_filtered`. `sim/benchmarks/walk_reference.json` holds the band verdicts of every method, the reproducible subset (AB06, 1.4 m/s, first 3 strides, both trunk modes) at full precision, and the snapshot, model, spec and commit it was taken at.
- `check.sim.walk_reference` (advisory): same snapshot and model, the metrics must reproduce within 1e-6 relative; otherwise the baseline is superseded by a design change and the check reports the current agreement and never fails; no baseline, no dataset, or a build candidate: skip. Seven tests including mutations (a metric moved by 1e-3 fails; 1e-8 passes; a design change never fails).
- **Two defects of mine, both found by running the thing.** (a) The baseline stored the reproduction metrics rounded to 6 decimals against a 1e-6 relative tolerance, so `fy check` failed on its own baseline for 14 metrics (e.g. -0.04273 against -0.0427303489). Now stored unrounded, with a test. (b) `fy gait` raised a `KeyError` printing its stride count after writing the record. The record and `GAIT.md` were not affected. Added `stride_count`, with a test. Both fixed in `db1b9d8`, which is why that commit follows the run; the baseline was regenerated from the existing record, not by re-running.

## T7 envelope (commit `b8bfdfc`)

`sim/runs/ENVELOPE.md` (114 lines) now has a gait section after the run table, from the latest `gait.json`: 95th percentile with the maximum beside it, offset subjects included. It is a separate section, not merged into the worst-case table, because it is a different statistic. Sagittal hip, knee and ankle from `A_filtered` only (the others miss the band), flagged `provisional`, naming method and trunk mode (A's leg rows do not depend on the mode: tested equal), with `A_native`'s maximum beside it as the with-impact bound. Hip ab/adduction and hip rotation are listed with their agreement numbers and flagged `outside band` (`A_filtered` 0.97 / 18% and 0.97 / 17%, 0.86 / 17% and 0.88 / 16%; the band was not widened). Ankle inversion is a load from `A_filtered`, B and H, flagged `unverified` and `not comparable with the dataset`. Joints above the pelvis are the bracket across modes. All joint speeds, the lumbosacral excursions and the hip-extension finding are in. Scenario classes: `walk_treadmill` covered; stairs, sit-to-stand, overground walking and ramps not.

`A_filtered` rows, right side, 95th percentile / maximum torque N m, with `A_native` maximum and positive / regeneration power 95th percentile W:

| joint | 1.4 m/s torque | `A_native` max | power | 1.6 m/s torque | `A_native` max | power |
|---|---|---|---|---|---|---|
| hip flexion | 70.2 / 111.7 | 237.5 | 151 / 50 | 77.4 / 98.1 | 232.5 | 228 / 75 |
| knee | 71.9 / 118.7 | 101.8 | 121 / 199 | 92.6 / 115.1 | 132.4 | 155 / 283 |
| ankle plantarflexion | 149.3 / 162.9 | 165.3 | 505 / 150 | 157.6 / 172.6 | 176.8 | 582 / 147 |

Left side and the other joints are in `ENVELOPE.md`. Joint speeds, 95th percentile / maximum rad/s: hip 4.50 / 4.88 (right, 1.4), knee 7.01 / 7.83, ankle 6.38 / 7.57; at 1.6 5.10 / 6.19, 7.42 / 8.75, 6.11 / 6.70.

**Functional-demand findings for the Joint ROM sheet (not clipped, your decision).** Peak hip extension: median 23.1, 95th percentile 36.8, maximum 39.5 degrees at 1.4 m/s and 24.2, 36.2, 41.4 at 1.6, against the model's 18.1 degree stop; 85% and 98% of strides go beyond it. Lumbosacral lateral bending peak angle, `counter_rotate`, mean / 95th / max: 5.8 / 7.8 / 8.9 degrees (1.4) and 6.1 / 8.6 / 10.7 (1.6); axial rotation 7.9 / 12.7 / 16.4 and 8.4 / 13.6 / 20.7.

## T9.1 the human-like trunk reference (commits `0147b0a`, `d6d1abd`)

`Cycle(trunk="first_harmonic", trunk_gain=(roll, yaw), trunk_lag_deg=(roll, yaw))`: the trunk's world roll and yaw are the standing values plus gain times the pelvis's stride-frequency first harmonic delayed by the lag, nothing else, and `lsj_lat` and `lsj_ax` supply the difference (the decomposition `Rp^T Rt = Rx Rz Ry` with the pitch term dropped: 0.23 degrees on a 4 and 5 degree synthetic pelvis; roll and yaw of the target are exact to 1e-9). It is not in `gait.TRUNK_MODES`, so no gait record can carry it. Defaults are the T3c.2 medians per speed, with the quartiles for the spread, in `retarget.FIRST_HARMONIC_DEFAULTS`; `gait_diag.py trunk-imu` reproduces the T3c.2 table (one cell differs in rounding: the 1.6 m/s roll ratio's upper quartile prints 0.79, memo5 says 0.80).

**The brief's arithmetic holds.** `|1 - r e^(-i phi)|`: 1.4 m/s roll 1.24, yaw 1.11; 1.6 m/s roll 1.40, yaw 0.97 (quartile corners 0.80 to 1.58): 1.2 to 1.4 in roll and 1.0 to 1.1 in yaw, as you wrote.

Lumbosacral rows over every subject-stride (988), median / 95th percentile / maximum:

| 1.4 m/s `lsj_lat` | peak angle deg | peak torque N m | peak speed rad/s | power+ / regen p95 W |
|---|---|---|---|---|
| rigid | 0 | 69.9 / 93.0 / 112.9 | 0 | 0 / 0 |
| counter_rotate | 5.7 / 7.8 / 8.9 | 16.2 / 23.5 / 31.9 | 1.17 / 1.43 / 1.75 | 16 / 16 |
| first_harmonic, medians | 6.7 / 8.9 / 10.4 | 21.1 / 32.1 / 38.9 | 1.20 / 1.55 / 1.83 | 16 / 31 |
| quartile corners (p95, min to max) | 7.2 to 10.0 | 26.1 to 36.1 | 1.3 to 1.7 | 12.8 to 17.9 / 21.6 to 38.0 |

| 1.6 m/s `lsj_lat` | peak angle deg | peak torque N m | peak speed rad/s | power+ / regen p95 W |
|---|---|---|---|---|
| rigid | 0 | 82.4 / 110.4 / 176.3 | 0 | 0 / 0 |
| counter_rotate | 6.0 / 8.6 / 10.7 | 16.8 / 27.6 / 83.3 | 1.28 / 1.62 / 2.68 | 12 / 29 |
| first_harmonic, medians | 7.6 / 10.2 / 12.6 | 25.0 / 40.7 / 90.7 | 1.41 / 1.87 / 2.70 | 20 / 52 |
| quartile corners (p95, min to max) | 8.7 to 11.1 | 35.8 to 44.8 | 1.5 to 2.0 | 15.2 to 23.2 / 41.1 to 60.0 |

`lsj_ax`: peak angle 95th percentile 12.7 (counter_rotate), 13.9 (first_harmonic median), corners 11.8 to 17.0 degrees at 1.4; torque 95th percentile 0.6, 2.4, corners 1.7 to 3.7 N m, rigid 8.2; at 1.6 13.6, 14.3, corners 13.0 to 18.8 degrees; 0.7, 2.3, corners 2.0 to 4.4 N m, rigid 14.0. (Full rows with speeds and powers: `python sim/scripts/gait_diag.py harmonic`.) The axial torque is small in every mode that moves the joint, so the lateral row is the one that sizes the lumbosacral lateral actuator, and the reference point puts it at about 1.4 times `counter_rotate` and a third of `rigid`.

**How far the quartile spread is the subjects and how far the estimate.** The estimate's own noise is the within-subject stride IQR, the subjects' spread is the IQR across 17 subjects' medians: roll ratio 0.16 within against 0.31 across (1.4) and 0.19 against 0.23 (1.6); roll lag 18 against 70 degrees and 17 against 55; yaw ratio 0.22 against 0.75 and 0.22 against 0.68; yaw lag 15 against 22 degrees and 17 against 27. Restricting to the 11 subjects whose IMU alignment correlation is at least 0.6 on every axis does not shrink the roll spread (ratio IQR 0.31 to 0.36 at 1.4, 0.23 to 0.20 at 1.6; lag 70 to 57 and 55 to 51 degrees) but halves the yaw ratio's at 1.6 (0.68 to 0.40, and the yaw lag 27 to 14 degrees). The Spearman correlation of a subject's ratio with the forward alignment quality is -0.05 and -0.13 for roll and -0.49 and -0.38 for yaw, and with the lateral alignment quality -0.22 and 0.00 for roll, -0.36 and -0.25 for yaw. So: the roll spread is mostly between subjects (about twice the stride noise at 1.4, about the same at 1.6, where the evidence is thin) and not explained by alignment quality, and the yaw ratio spread at 1.6 m/s is partly alignment (it falls with the alignment subset and correlates with it; at 1.4 m/s it barely falls, 0.75 to 0.69). I cannot separate a true subject difference from a fixed per-subject error in sensor placement or alignment: the within-subject IQR bounds only the random part. Treat the corner rows as a spread of a poorly constrained estimate, not as a population distribution.

## T9.2 where B's 66 mm backward offset does not come from (commit `b0c63f4`)

| 1.4 m/s, single support, 5267 frames | rigid: fore-aft mean / rms mm | counter_rotate: fore-aft mean / rms mm |
|---|---|---|
| Freyja's masses | -66.2 / 104.5 | -65.2 / 102.3 |
| trunk centre of mass moved to the dataset's | -70.6 / 120.5 | -69.4 / 118.9 |
| dataset masses | -47.5 / 92.2 | -46.5 / 90.2 |
| dataset masses and the trunk move | -52.0 / 109.3 | -50.8 / 108.1 |

At 1.6 m/s (5423 frames) the same ordering: rigid -66.3 / 126.0, -69.7 / 145.5, -47.0 / 114.1, -50.6 / 134.9; counter_rotate -65.8 / 121.9, -69.2 / 141.6, -46.4 / 110.3, -50.1 / 131.6. Lateral rms moves by at most 1 mm with `counter_rotate` and rises by 46 to 59 mm with `rigid` (210.1 to 256.3 at 1.4 m/s).

The move is in-memory only (`sim/scripts/trunkcom.py`, tested: the group's centre of mass moves by exactly the requested vector to 1e-12, masses and inertias unchanged, only the nine group bodies change, nothing saved). The dataset's torso is the same set of bodies as Freyja's group (trunk, head, arms). The shift is the median over subjects of the leg-length-scaled offset, -7.9 mm in x and +65.2 mm up. The upward shift is large (Freyja's group is 383 mm above the hip midpoint, the dataset's 449 scaled) and the dataset's torso is also further back, so both moves hurt: the backward 8 mm accounts for about the 4 mm worse mean (0.45 times 8 mm is 3.6 mm), and the rms worsens by 16 mm, which I read as the higher centre of mass amplifying its own fore-aft motion (not tested). Moving the trunk group is not the missing 66 mm. I did not look for the cause further, per the brief. What the numbers leave open: the 66 mm is a whole-body quantity that the segment masses explain 18 mm of and the trunk placement none of; the measured CoP is 116 mm ahead of the ankle on average against B's 49 mm.

**(b) The standing CoP.** No subject's static trial has force-plate data: the static folder holds `ik`, `ik_offset` and `markers` for all 17 subjects, so there is no quiet-standing CoP relative to the ankle and `pose.com_x_rel_ankle_m` (default 0.0, in `sim/scenarios/stand_static.yaml` and `hold_pose.yaml`, not in the sheet) stays uncited. Nothing was changed. Which cells would change if a cited standing position were adopted: none in the sheet by itself, since that parameter is a scenario input that the lean-pose solver turns into joint angles. If instead the trunk's own placement were to be changed, the cells are the segment centre-of-mass x values `'MuJoCo Reference'!D15` (head and neck), `D16` (thorax), `D17` (abdomen), `D18` (pelvis) and `D19` to `D21` (upper arm, forearm, hand). T9.2 gives no reason to change them.

## T9.3 pitch flags (commits `b99a5ba`, `90d7d8a`)

`gait_diag.py pitch` compares, for every subject, the static-to-walking change of the IK pelvis pitch (minus `pelvis_list`) with that of the ASIS/PSIS marker tilt, flagging a difference above `gait.PITCH_FLAG_DEG` = 5 degrees at either speed (my choice of rule: either speed, so the flag does not depend on which speed is looked at; AB07, AB12 and AB19 exceed it at both speeds, AB18 only at 1.6 m/s). Differences of changes (IK minus markers, degrees) at 1.4 / 1.6 m/s: AB07 -5.7 / -6.1, AB12 -12.1 / -12.1, AB18 -4.9 / -5.2, AB19 -10.0 / -10.3; the rest -0.9 to -4.5 (AB16 -4.1 / -4.5). Over 34 subject-speeds the median is -2.4 and the range -12.1 to -0.9, all negative: the IK pitch falls more from static to walking than the markers' do for every subject. AB18 is borderline (4.9 at 1.4 m/s); it is flagged because of the 1.6 m/s value. AB16 is the nearest unflagged. Flagged subjects are kept and listed in the spec (`pitch_flag_subjects`); the record gives every aggregate, the band verdict and the stride count without them (363 of 469 and 402 of 519 strides remain); `GAIT.md` has a third band verdict and one line with the largest change.

**Without the flagged subjects,** `A_filtered` 1.4 m/s hip 0.912 / 14.7, knee 0.922 / 11.8, ankle 0.994 / 11.2; 1.6 m/s 0.924 / 13.4, 0.930 / 11.0, 0.993 / 11.4: still meets. Largest change of a leg joint's 95th-percentile peak torque by dropping them, N m (1.4 / 1.6): `A_filtered` 3.9 (ankle left) / 5.3 (hip flexion left); `A_native` 9.5 / 10.5; B rigid 9.0 / 14.0, counter_rotate 10.9 / 15.0 (hip flexion left); H 5.6 / 10.1 rigid (hip ab/adduction left), 5.1 / 8.0 counter_rotate.

**A mistake of mine here.** The first version of the marker tilt took forward as the lab's -z axis, and gave static tilts of 40 to 100 degrees for most subjects: the static trials are recorded facing another way than the treadmill trials. The tilt now takes forward from the pelvis (the vertical crossed with the left-to-right ASIS line), with a test that rotates the markers about the vertical by 30, 90, 180 and -75 degrees (it failed first). The result reproduces memo5's AB12 and AB19 findings; its marker changes there are -2.6 and -3.1 degrees against memo5's -2.0 and -2.6 (a different averaging window: here each stride's own).

## T9.4 toe evidence (commit `c651bcc`)

The measured numbers are in finding 5. `decisions/0001-toe-joint.md` (`adr-0001`, `status: proposed`) carries the evidence that does exist: memo5's push-off table (last decile of stance, measured CoP outside the box in 66% of single-support and 99.7% of double-support frames at 1.4 m/s, 85% and 100% at 1.6), the T3b estimate that a toeless box caps the ankle near 140 N m against `A_filtered`'s 95th-percentile ankle torque of 149 to 169 N m (7% to 21% above; that cap was not recomputed), and the three consequences. Its rejected-options section is left for you. A toe-load module written before I looked at the data was deleted unused.

## What the brief's final message asks for (the numbers are in `GAIT.md`, `ENVELOPE.md` and above)

- **B, A and H per joint, 95th-percentile peak torque, N m, right side** (`B` rigid / counter_rotate, `A_native`, `A_filtered`, H rigid / counter_rotate):

| joint | 1.4 m/s | 1.6 m/s |
|---|---|---|
| hip flexion | 191 / 194, 168, 70, 172 / 174 | 220 / 226, 192, 77, 225 / 225 |
| hip ab/adduction | 179 / 92, 120, 87, 150 / 117 | 205 / 98, 142, 87, 186 / 128 |
| hip rotation | 57 / 30, 26, 21, 21 / 25 | 75 / 39, 32, 25, 32 / 30 |
| knee | 166 / 151, 84, 72, 81 / 82 | 212 / 193, 102, 93, 107 / 105 |
| ankle plantarflexion | 209 / 211, 151, 149, 161 / 160 | 282 / 281, 162, 158, 177 / 176 |
| ankle inversion (unverified) | 312 / 137, 55, 56, 48 / 56 | 364 / 181, 60, 58, 53 / 61 |

  Maxima and powers for every joint, both sides: `GAIT.md` and `ENVELOPE.md`. H's hip flexion maximum at 1.6 m/s is 553 N m (right): a few frames, not the 95th percentile.
- **CoP outside the box or friction exceeded, by phase** (B, 25 mm band, 1.4 m/s, % of stance-foot frames in ten bins of phase): rigid 71.6, 92.5, 86.2, 80.3, 97.9, 71.7, 94.5, 82.9, 77.6, 98.4; counter_rotate 31.2, 46.6, 47.5, 51.3, 68.6, 27.2, 49.0, 52.9, 52.9, 75.2; friction above mu 0.0% in every bin and speed. At 1.6 m/s counter_rotate 30.6 to 90.5%. Rates by support type and band are in finding 2 and `GAIT.md`.
- **Residual magnitudes** (mean over strides, 1.4 m/s; force rms % BW, horizontal moment rms N m; rigid / counter_rotate): B 0 and 0 (vertical-axis moment 14.1 / 11.1 N m); `A_native` 19.2 / 14.0 and 71.1 / 58.8; `A_filtered` 17.1 / 11.3 and 66.7 / 52.6; H 0 and 138.5 / 73.2. At 1.6 m/s `A_filtered` 20.9 / 14.0 and 74.2 / 56.0, H 0 and 167.3 / 88.1, B vertical-axis moment 17.3 / 13.2.
- **Force against the measured one, like for like (mean over strides):** vertical peak ratio 0.97 (correlation 0.97) both speeds; fore-aft peak-to-peak ratio 0.99 (0.87) rigid and 1.05 (0.89) counter_rotate at 1.4, 1.10 (0.84) and 1.15 (0.87) at 1.6; lateral 1.87 (0.06) and 1.31 (0.86) at 1.4, 2.21 (-0.06) and 1.34 (0.80) at 1.6.
- **Smoothing sensitivity** (B, 95th-percentile peak torque, 4 strides per subject, cutoff 4 to 15 Hz, rigid / counter_rotate): knee right 150 to 205 / 137 to 170 at 1.4 m/s and 161 to 272 / 157 to 261 at 1.6; hip flexion right 191 to 199 / 193 to 201 and 207 to 275 / 211 to 270; hip ab/adduction right 141 to 215 / 83 to 101 and 155 to 360 / 87 to 111; ankle 219 to 216 (flat) and 259 to 291 (+12%) rigid. The pitch-offset sensitivity (-5 to +5 degrees, 1.4 m/s rigid): knee right 191 to 131, ankle 171 to 262, hip flexion 206 to 174. The leg torques depend strongly on the cutoff above 6 Hz at the hip and knee and on the pelvis pitch at the knee and ankle.
- **Agreement with the dataset's moments:** finding 1 and the stem table in `GAIT.md` (hip ab/adduction `A_filtered` 0.97 / 18%, hip rotation 0.86 / 17% at 1.4 m/s; ankle inversion -0.10 / 105% for every method, not comparable).
- **Subjects and strides:** AB06 to AB21 and AB23 (17), 55 to 96 kg, 1.52 to 1.80 m, 50 to 60 strides each at 1.4 m/s and 54 to 66 at 1.6, 469 and 519 in all. Offset subjects (AB13, AB15) and pitch-flagged subjects (AB07, AB12, AB18, AB19) kept, with statistics also without them. Wrap gap above 10 degrees: 11 strides at 1.4 m/s and 27 at 1.6, flagged and kept.

## Tolerances and constants

| constant | value | why |
|---|---|---|
| `BAND_CORR`, `BAND_RMS_PCT` | 0.9, 15% of peak-to-peak | yours (Decisions block); not widened |
| `PITCH_FLAG_DEG` | 5 degrees | yours (T9.3); the either-speed rule is mine |
| `REFERENCE_TOL`, subset | 1e-6 relative; AB06, 1.4 m/s, 3 strides | existing; deterministic code, the tolerance only absorbs round-off; metrics stored unrounded |
| above-the-pelvis identity test | 1e-9 relative to max(1, peak torque) | round-off of a rotation-free sum |
| `first_harmonic` target and zero-gain tests | 1e-9 and 1e-12 | exact algebra |
| `first_harmonic` world amplitude / lag | 2% and 1 degree; pitch term below 0.5 degrees | the dropped pitch term is second order (0.23 degrees measured); the world angles are measured about the standing pelvis's axes |
| quartile corners | each gain quartile with each lag quartile, roll and yaw together | my pairing: a corner is the extreme of one quartile choice applied to both axes |
| "well-aligned" subset | IMU alignment correlation at least 0.6 on every axis | T3c.2's cut, a sensitivity row not a selection |
| dataset trunk offset scaling | leg-length ratio, median over subjects | as the legs are scaled in `datasetmass`; unscaled it is 2 mm further back (58.1 against 56.0 mm), which does not change the conclusion |
| `GAIT.md` and `ENVELOPE.md` | 399 lines | unchanged; 371 and 114 |

## My own mistakes, stated plainly

- The baseline's rounding and the `fy gait` stride-count crash (T6, above), the first marker-tilt forward axis (T9.3, above).
- Tests first was not followed for `trunkcom.py`: I wrote it in the same step as its tests, so they never failed first. I then showed they fail under two mutations (a flipped shift sign, and the wrong body set: three failures each).
- The `gait_diag` report subcommands have no tests of their own (they print and write nothing; their pure helpers do).
- Several multi-line Python edits were first sent through a shell heredoc that the tool dropped silently; each time I confirmed from the file that the edit had applied before committing (a count of the new function, then the tests).
- `CONVENTIONS.md` was CRLF in the working tree; my edit left it LF, as `CLAUDE.md` requires; the diff is 7 lines.

## Questions for Joe

1. **B.** B fails the band, the polygon test and the dataset's moments, and T9.2 removes the trunk placement as the cause. By the brief the baseline and envelope rows rest on `A_filtered`, flagged provisional because A borrows the human CoP, and B's failure stands as a finding about the controller project. Is that how Stage 2 closes, or do you want the 66 mm pursued (it is a whole-body quantity; segment masses explain 18 mm, the trunk placement none)?
2. **Toe (adr-0001).** The dataset has no toe loads. Do you want a proxy from the force plate and the heel and toe-tip markers (the force's lever about an assumed joint position; an assumption I would flag), a different source with a cited licence, or a decision on no toe or a passive toe without loads?
3. **`first_harmonic` in the envelope.** The brief's Decisions say the lumbosacral rows are the bracket plus one human-like reference point; T7's task lists the bracket only. The reference point exists only as a diagnostic (`gait_diag.py harmonic`), because it is deliberately not a record mode. Do you want it in `ENVELOPE.md` (it needs a third trunk mode in the record, or a separate small generated file)?
4. **Hip ab/adduction and hip rotation.** `A_filtered` is 0.97 / 18% and 0.86 to 0.88 / 16 to 17%: they miss on RMS (and hip rotation on correlation) by a few points. Not admitted; the band stands. Say if you want that as a new decision.
5. **Joint ROM sheet.** Peak hip extension beyond the 18.1 degree stop in 85% and 98% of strides (95th percentile 36.8 and 36.2 degrees), lumbosacral lateral bending 7.8 and 8.6 degrees and axial rotation 12.7 and 13.6 degrees at the 95th percentile with a counter-rotating trunk (higher with the human-like reference: 8.9 to 10.2 and 13.9 to 14.3). They are findings; nothing was clipped or changed.
6. **Pitch flags.** AB18 is flagged on one speed's 5.2 and is borderline; AB16 sits at 4.5. Keep 5 degrees and the either-speed rule?
7. **Schema and tracking.** I amended `gait-summary/1` in place (trunk list, results by speed then mode, band, a third exclusion set) because no `gait.json` is tracked; if you want that treated like a run record, it should be `gait-summary/2`. Also `ENVELOPE.md`'s gait section reads an untracked `gait.json`, so it cannot be regenerated from a clean clone (the file says which gait id it was built from). A small tracked gait extract would fix that.
8. **Standing CoP.** No dataset carries a quiet-standing CoP relative to the ankle (no force plate in any static trial), so `pose.com_x_rel_ankle_m` stays 0.0 and uncited; a source is needed.

## Commits

`2e54d18` T6.0 (trunk list, band, baseline writer, `check.sim.walk_reference`); `db1b9d8` T6 (the full run's `GAIT.md`, baseline, the two fixes); `b8bfdfc` T7; `0147b0a` T9.1a (`first_harmonic`); `d6d1abd` T9.1b (`gait_diag harmonic`); `b99a5ba` T9.3 (pitch flags, spec key, third exclusion set); `90d7d8a` T9.3 record and envelope; `b0c63f4` T9.2 and T9.4 (trunk-group offset, standing and toe evidence); `c651bcc` the toe decision record. `docs/STATE.md` was generated on `c651bcc` with `fy state` and is committed with this memo, so it names that commit as its base.
