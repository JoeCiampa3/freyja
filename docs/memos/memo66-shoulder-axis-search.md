STATE: base 485b68b790aa | brief architecture sha256:bd2d997fe5e8, ariadne sha256:389d99bf7d96 | snapshot sha256:492fe816e6d8 | tests 2476/2551 | dirty yes (the one uncommitted file is this memo; 2 failed, both the absent Camargo processed arrays, finding 6; 73 skipped, 26 `inputs` tests not run again; reported by `fy state` from the full run on this tree, key 6c12dc2af680)

# Memo 66: shoulder axis search (where the gimbal's fixed axis points)

Brief: `docs/briefs/ariadne/shoulder-axis-search-brief.md`. Its sha256 prefix `389d99bf7d96` matched the prompt's 389D99BF7D96 (LF, no mismatch). One group, one checkpoint, reached. Commits: dcc7a1f (T1), 957763b (T2 and T3), b3e1cee (T4), 485b68b (the full-suite timing figures in `CLAUDE.md`), then this memo with `docs/STATE.md`. Nothing in the model, template, `pre_processor`, sheet, decision records, roadmap nodes or thread records changed. Nothing stamped, nothing pushed.

## Decision summary

- **What this means for Freyja:** a fixed-centre gimbal can keep its singular line at least **28.9 deg** from every required humeral direction. The model's current chain manages **0**: its axis 1 points straight out sideways, onto the abduction arc. The best axis 1 runs from **up, forward and out** to **down, back and in**. The upper end is plane 45 deg, 137 deg elevation: between the raised-forward and raised-sideways arm, above the ADL box. The lower end points into the back of the thorax. **That is the front-to-back mirror of the chat hypothesis** (up-back-out / down-forward-in). The hypothesis region is the second basin, 2.9 deg worse.
- **The numbers that matter**, each beside its reference:
  - Floor at the optimum: **28.894 deg**, sigma_min 0.3528, rate gain 2.83. Baseline, the model's chain: 0 deg, gain infinite, at abduction 90 (V2). The brief's finding line is 15 deg (sigma 0.18): cleared.
  - Hypothesis basin (up-back-out: plane -37.5, elevation 134.0): **25.982 deg**, sigma 0.3179, gain 3.15. It is 55.2 deg from the optimum.
  - q1 (axis 1) span over the basis: **353.5 deg** at the optimum, against **232.6 deg** at the hypothesis basin. For scale, the model's flexion-extension range is 229.3 deg. q2 span: 122.2 and 128.0 deg.
  - S1, the high shelf in the scapular plane, at the optimum: **10.19 deg** from the singular line (gain 7.96), below the 15 deg line. At the hypothesis basin it is 41.7 deg (gain 1.99). S3, hand behind head: 25.7 and 47.0 deg. S2, cross-body: 86.6 and 45.4 deg.
  - Adding S1 to the basis, alone or with S2 and S3, moves the optimum to the hypothesis basin (25.982 deg). Adding S3 alone moves it 3.2 deg (27.41 deg). S2 changes nothing.
- **Decisions for Joe (inputs to adr-0025):**
  1. Which axis. Recommended: **the hypothesis basin, up-back-out**. It costs 2.9 deg of floor (gain 2.83 to 3.15). It buys S1 (10.2 to 41.7 deg), S3 (25.7 to 47.0 deg) and a q1 span of 233 deg instead of 354 deg. Take the basis optimum only if the high shelf in the scapular plane is not a requirement.
  2. Source S1 to S3; all three are from memory. S1 alone decides question 1.
  3. Each choice puts a singular end into the torso: down-back-in (the optimum) or down-forward-in (the hypothesis basin). Torso collision is not modelled, and neither end is credited (brief, Decisions 5).
  4. Re-chain the sim to the hardware axes or map between the chains: open (brief, Decisions 4).
- **What would change this:** a sourced S1 plane or elevation other than 30 deg / 172 deg. Or B1's plane bounds: the hypothesis basin's lower end binds on Gates' 105 deg edge, a left-limb mean, and widening the bounds by 10 deg drops that basin to 23.7 deg while leaving the optimum unchanged. Or a shoulder-girdle DOF: the centre is fixed here.

## Gates

| Gate | Result | Numbers |
|---|---|---|
| V1 conditioning formula | pass | 10 000 random (u1, d) pairs through the gimbal's own IK and FK; worst \|SVD sigma_min - sqrt(1 - \|u1.d\|)\| = 8.5e-15 (tolerance 1e-9) |
| V2 baseline | pass | u1 = (0, -1, 0): floor 0 (sigma 0, bound sqrt(1 - cos 0.5 deg) = 0.00617) at A3 alpha = 90 and B1 (0, 90) |
| V3 round trip | pass | 19 814 directions (R, S1 to S3), 0 within 1 deg of +/-u1; max \|FK(IK(d)) - d\| = 1.3e-15 |
| V4 mirror | pass | left optimum (0.48320, +0.48320, 0.73010) is the y-mirror of the right: difference 0, floors equal (difference 0) |
| V5 convergence | pass | 20 000 seeds (39 refined) and 80 000 seeds (40) reach the same vertex: 0 deg apart, sigma difference 0. Grid-only best: 28.7116 and 28.6833 deg |
| V6 determinism | pass | an in-process build equals the committed file a separate run wrote, byte for byte |
| V7 conventions vs model | pass | mujoco FK of the elbow-ward axis in the thorax frame equals d(phi, theta) to 8.7e-17 in the four poses, right and left. Abduction sign read from `checks/joint_polarity.yaml` (shoulder_aa positive = adduction, so abduction is -90). Left arm is the y-mirror |

## The optimum and the basins

The right arm, thorax frame. Each basin's u1 is given at its upper end. Active points are the directions at exactly the floor, which make the local-maximum certificate. The certificate checks that the largest gap between the active points' tangent directions is below 180 deg, so no move increases every distance.

| # | u1 | upper end (phi, theta) | lower end | floor deg | sigma | gain | from optimum | active | q1 span | q2 span | neutral q2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | (0.4832, -0.4832, 0.7301) | (45.0, 136.89) up, anterior, lateral | (-135.0, 43.11) down, posterior, medial | 28.894 | 0.3528 | 2.83 | 0 | A1 beta 146.5, A3 alpha 146.5, B1 (45, 108) at the upper end; A2 beta 33.5 at the lower; gap 126.1 | 353.5 | 122.2 | 46.89 |
| 2 | (-0.4381, -0.5709, 0.6944) | (-37.5, 133.98) up, posterior, lateral | (142.5, 46.02) down, anterior, medial | 25.982 | 0.3179 | 3.15 | 55.2 | A3 alpha 140.5, B1 (-38, 108) upper; B1 (105, 39) lower; gap 123.1 | 232.6 | 128.0 | 43.98 |
| 3 | (0.8545, 0.1895, 0.4835) | (102.51, 118.92) up, anterior, medial | (-77.49, 61.08) down, posterior, lateral | 10.927 | 0.1346 | 7.43 | 47.6 | A1 beta 119.5, B1 (103, 108) upper; B1 (-65, 60) lower; gap 165.2 | 250.5 | 158.1 | 28.92 |

The optimum is symmetric: u1 has x = -y exactly, so it lies in the plane phi = 45 that swaps the flexion and abduction arcs. It is held by the tops of both arcs and B1's top edge above, and by the extension arc at 33.5 deg below. Binding directions within 0.5 deg of the floor: A1 beta 141 to 152 (23 points), A3 alpha 141 to 152 (23), B1 theta 108 at phi 39 to 51 (13), and A2 beta 28 to 39 (23) at the lower end. All 82 are listed in `data/shoulder/axis_search.json`.

Spans. q1 is lifted continuously from the neutral arm (q1 = 0 straight down): along each arc in its parameter's order, and over B1 column by column. The lifts agree where A1 and A3 overlap B1's columns (disagreement 0). R does not encircle u1 at any basin. At the optimum the 353.5 deg is A1 from 0 to +170.8 and A3 from 0 to -182.7: the two arcs pass on opposite sides of u1's upper end and nearly meet overhead. A1 stops at 172, 8 deg short of vertical, and A3 runs through vertical to 182.7. So reaching full flexion and then full abduction takes nearly a full turn of axis 1. At the hypothesis basin both arcs pass the same side (A1 0 to 171.9, A3 0 to 182.2, B1 -50.4 to 142.2).

The axis-3 span is not computed. It needs a definition of the gimbal's induced axial offset against ISB axial rotation, which is adr-0025's to choose (brief T2). Open.

Map (T3; matplotlib is pinned): `data/shoulder/map/floor_map.png` (gitignored; `python analysis/shoulder_axis_search.py --map`). It shows the floor over u1 in the right arm's (phi, theta), with R overlaid. Two bright caps sit above B1: one between A3 and A1, the optimum's upper end, and one behind A3, the hypothesis basin. The S1 line at phi = 30 cuts through the first.

Discretisation. Evaluated at the fixed u1 against arcs at 0.01 deg and B1's edges at 0.01 deg (interior at 0.25 deg), the floor at the optimum is unchanged (difference 6e-12 deg; its active points lie on the 0.5 deg grid). At the hypothesis basin it is 0.0034 deg lower. The brief's grid costs nothing that matters.

## Sensitivity (T4)

Each case was searched as the basis was (80 000 seeds, refined, certified). "From basis" is the angle from the basis optimum.

| Case | floor deg | sigma | gain | from basis deg | upper end | binds | q1 span | q2 span |
|---|---|---|---|---|---|---|---|---|
| R (basis) | 28.894 | 0.3528 | 2.83 | 0 | (45.0, 136.9) up, ant, lat | A1, A2, A3, B1 | 353.5 | 122.2 |
| R + S1 | 25.982 | 0.3179 | 3.15 | 55.17 | (-37.5, 134.0) up, post, lat | A3 alpha 140.5; B1 (-38, 108) and (105, 39) | 232.6 | 128.0 |
| R + S2 | 28.894 | 0.3528 | 2.83 | 0 | unchanged | unchanged | 353.5 | 122.2 |
| R + S3 | 27.412 | 0.3351 | 2.98 | 3.15 | (49.0, 135.4) up, ant, lat | A1 143.5, A2 36.5, B1 (49, 108), **S3** | 354.4 | 125.2 |
| R + S1 + S2 + S3 | 25.982 | 0.3179 | 3.15 | 55.17 | as R + S1 | as R + S1 | 232.6 | 128.0 |
| R without B1 | 45.000 | 0.5412 | 1.85 | 46.72 | (45.0, 90.2) up, ant, lat | A1 and A3 at 90 and 90.5 | 356.2 | 81.6 |
| R, B1 plane +/-10 | 28.894 | 0.3528 | 2.83 | 0 | unchanged | unchanged | 353.5 | 122.2 |

S1 to S3 at a fixed axis, not re-optimised (angle from the singular line, gain, where):

| Axis | S1 (phi 30, theta 0 to 172) | S2 (130, 90) | S3 (20, 120) |
|---|---|---|---|
| Basis optimum | **10.19 deg**, gain 7.96, at theta 138 | 86.59, 1.03 | 25.66, 3.18 |
| Hypothesis basin | 41.67, 1.99, at theta 158.5 | 45.37, 1.83 | 47.00, 1.77 |
| Third basin | 56.60, 1.49 | 39.06, 2.12 | 70.09, 1.23 |

So:
- Joe's hand-behind-head pose (S3) survives either axis: 25.7 deg at the optimum, 47.0 at the hypothesis basin.
- The high-shelf reach in the scapular plane (S1) does not survive the basis optimum: at 138 deg of elevation it passes 10.2 deg from the singular end, with a rate gain of 8.
- Widening B1's plane bounds by 10 deg leaves the optimum alone. It drops the hypothesis basin from 25.98 to 23.67 deg, because that basin's lower end binds on B1's phi = 105 edge.
- Without B1 the three arcs alone allow 45 deg. B1 is what costs 16 deg of floor.

## B1's convention

Confirmed, not provisional. Gates et al. 2016 (PMC4690598), Data Analysis: the humerus relative to the trunk by a Y'-X-Y'' Euler sequence on the basis of ISB (Wu et al. 2005): plane of elevation, elevation, axial rotation. The Figure 1 caption gives elevation in the frontal plane (pure abduction) as plane angle 0, pure flexion as 90, pure extension as about -90, and the arm at the side as elevation 0. That is the brief's d(phi, theta).

Three cautions, recorded in the inputs file:
- The box overstates the requirement (the brief's own caution).
- The extremes are task means across participants (Table 1, Mean column), not individual extremes.
- The 105 deg is the contralateral limb (perineal care), which the paper names as the left arm, although it says only right-arm data are presented. No mirroring is described.

The third bears on the hypothesis basin, which binds on that edge. The paper was read through a fetch of the PMC page; the supplemental appendices were not read.

## Findings

1. **The optimum is not in the hypothesis region** (brief, "Report as a finding"). Its upper end is up-anterior-lateral and its lower end down-posterior-medial. The hypothesis region (up-posterior-lateral / down-anterior-medial) is the second basin: 25.98 deg, 2.91 deg worse, 55.2 deg away.
2. **S1 lies 10.19 deg from the basis optimum's singular line** (gain 7.96), below the brief's 15 deg line. That line is written for the basis floor, which clears it at 28.9 deg. S1 is a sensitivity entry, so this is reported, not a gate. Adding S1 moves the optimum to the hypothesis basin.
3. **q1 span 353.5 deg at the optimum.** R does not encircle u1, but the flexion and abduction arcs nearly close around its upper end. The hypothesis basin needs 232.6 deg.
4. **The brief's "so the neutral arm is q = 0" holds only when u1 is horizontal.** With d0 the projection of straight down, the neutral arm is q1 = 0 and q2 = asin(u1_z): 46.89 deg at the optimum, 43.98 deg at the hypothesis basin. The brief's chain gives R(u2, q2) d0 = cos q2 d0 - sin q2 u1, so positive q2 tilts the arm toward -u1 (q2 = -asin(d . u1)). I followed the brief's formulas literally; the output says so.
5. **`fy test` falls back to serial silently** (CONVENTIONS 9.9). The repo `.venv` had neither pytest-xdist nor execnet, both pinned in `requirements.txt`, and `tools/fy/cli.py` `run_tests` drops `testkit.PARALLEL` without a message when xdist is missing. The quick suite took 177 s serially at T0, and a serial full run had reached 22% in about 55 min. Joe approved installing the pinned versions (3.8.0, 2.1.2) this session. Recommended: have `fy test` print a line when it falls back.
6. **Two tests fail on this clone because the gitignored processed gait arrays are absent.** `tests/test_foot_split.py::test_with_the_old_box_a_negligible_toe_and_the_toe_welded_the_tracked_a_filtered_reference_is_reproduced` fails and `tests/test_retarget.py::test_held_joints_stay_at_the_standing_pose` errors at setup, both on `data/camargo2021/processed/AB06.npz`. This clone has no `sim/local_config.json` and no `CAMARGO_RAW_DIR`. Each test reads a gitignored file and fails instead of skipping. `docs/STATE.md` at memo 65 had 0 failures, so that run had the arrays.
7. **The headless-browser timeout recurred under load.** On the T1 run, which executed every `inputs` test because this clone (14 logical CPUs) had no pass records for them, `test_roadmap_viewer.py::test_the_harness_detects_a_wrong_answer` and `test_landmark_picker.py::test_only_faces_whose_vertices_are_all_in_the_body_are_kept` hit the 180 s timeout. Both passed alone (2 passed in 20.65 s) and on the T2 and T4 runs. This is the condition in Joe's memo 65 ruling ("add a serial phase only if the test fails again under the inputs load").

## Tolerances and parameters I chose, and why

Fixed by the brief, not chosen by me:
- Arc step 0.5 deg.
- B1 1 deg grid.
- Seeds 20 000 and 80 000.
- Basins more than 20 deg apart.
- Binding band 0.5 deg.
- V3 exclusion 1 deg.
- Every gate tolerance.

Where the brief was silent:
- S1's elevation step is the arcs' 0.5 deg.
- Arc ends off the step (57.3, 182.7) are appended.
- The reported optimum is the 80 000-seeded one.
- The sensitivity cases use 80 000 seeds.

Chosen by me:
- **Pattern search: 16 compass directions, first step 1 deg, stop at 1e-10 rad.** The first step is the 20 000 grid's spacing, 1.01 deg; the stop is 6e-9 deg, far below V5's 0.1 deg. Chosen before any run.
- **Vertex polish: the 12 nearest directions (220 triples), circumcentres within 1 deg.** The local maximum of a max-min distance to a finite set is a cap whose rim passes through three points, and the polish lands on it exactly. That is why V4 and V5 agree to 0, not to a tolerance.
- **ACTIVE_TOL 1e-12** in |u1.d|, for the certificate.
- **IMPROVE_TOL 1e-15**, the least gain in max |u1.d| that counts as an improvement. Float noise is about 1e-16; V5's floor tolerance corresponds to about 7e-7 in g. Chosen after the refinement cycled on 1-ulp differences between products over a subset and over all of D (mistake 1).
- **POLISH_SWITCH_RAD 1e-6** and **PATTERN_MAX_ITER 20 000.** Below that step the polish takes over from the pattern search. Chosen after the coordinate-axes test stalled at 1.3e-7 rad (mistake 2). Neither was tuned toward a result: the basis output is byte-identical before and after.
- **Output 12 significant digits.** Finer than every gate's tolerance (1e-9), coarser than float noise.
- **`unique_dirs` rounds directions to 13 decimals** to drop repeats (B1's theta = 0 row, the arcs' shared start). Reported floors are computed on all labelled points.

## My mistakes

1. My first refinement compared values computed over different subsets and cycled on 1-ulp "improvements". It hit its round limit, which in the prototype I had capped silently at 100. Fixed by re-evaluating on all of D and requiring IMPROVE_TOL.
2. My compass search had no step expansion and no ridge directions, so it crawled at 1e-6 rad along the A1/A3 ridge in the R-without-B1 case. With those added, it still stalled 1.3e-7 rad from the vertex in the coordinate-axes test. Fixed with ridge directions (each nearby point's own direction and pair-equal directions), step doubling, and an earlier hand-over to the vertex polish. Each has a regression test. The T2 basis result was unchanged byte for byte by the last fix.
3. A T4 test compared line angles with acos near 1, which is ill-conditioned: 12-digit rounding read as 8e-5 deg. `line_angle_deg` now uses atan2(\|a x b\|, \|a . b\|). The committed T2 values did not change at 12 digits.

## Questions for Joe

1. Axis: the hypothesis basin (recommended) or the basis optimum (decision summary, item 1)?
2. S1 to S3 sources: the scapular-plane angle and the high-shelf elevation decide item 1.
3. B1's 105 deg edge is a left-limb mean in Gates 2016. Keep it as the right arm's requirement? The hypothesis basin binds on it.
4. `fy test`'s silent serial fallback (finding 5): add a warning line?
5. The headless-browser timeout under the `inputs` load (finding 7): add the serial phase your memo 65 ruling named?
6. The two Camargo tests that fail without the processed arrays (finding 6): make them skip when the arrays are absent, or is this clone meant to have them?
