# Stage 1, 1b and 1c recap

Date: 2026-10-10. Briefs: `docs/briefs/stage1-brief.md`, `docs/briefs/stage1b-brief.md`, `docs/briefs/stage1c-brief.md`. Contract: `CONVENTIONS.md`.

Stage 1 made every simulation run leave a stamped, comparable, machine-readable record and built the two generated files
Claude reads instead of Joe measuring and reporting. Stage 1 also found that the neutral pose has no static equilibrium; Stage
1b added a solved standing pose so the first ground scenario works. Stage 1c then replaced the PD hold's standing loads with a gain-independent static solve and added posture sweeps. All three briefs are complete. The pipeline, template, sheet
reader and every placeholder are unchanged; the only model change is the foot box (below).

## What exists now

| Piece | Where | What it does |
|---|---|---|
| Run record | `docs/schemas/run-summary-1.schema.json`, `sim/scripts/runrecord.py` | `run-summary/1`: ids, git state (commit, dirty, hash of `git diff HEAD`), snapshot and model hashes, seed, environment, scenario, window, per-joint metrics, contacts, balance, check status. Validated on every write, deterministic JSON. `summary.json` is tracked, `raw.npz` is not. |
| Metrics | `sim/scripts/metrics.py` | Peak/RMS torque, speed, power, ROM used, limit hits, foot forces and friction ratio, support margin (hand-written convex hull). |
| Runner | `sim/scripts/simrun.py`, `fy run <scenario> [--set k=v]` | Refuses to run (creating nothing) if `freyja.xml` or `snapshot.csv` no longer hash to `snapshot.meta.json`. Gantry: inverse dynamics. Ground: forward dynamics with ideal torque on `qfrc_applied`. Detects `fell` and `diverged`. |
| Controllers | `sim/controllers/pd_hold.py`, `rom_sweep.py` | PD hold at the reset pose with inertia-scaled, capped gains; 99% range sweep per joint. |
| Lean pose | `sim/scripts/leanpose.py` | Rigid lean about the ankle that puts the CoM a chosen distance in front of the ankle, found by forward kinematics and bisection. An unreachable target is an error. |
| Query | `fy runs list/show/compare` | `compare` names exactly the inputs that differ, then the metric deltas, then the changed snapshot rows via `git show` when both commits are clean. |
| Digest, envelope | `sim/runs/DIGEST.md`, `sim/runs/ENVELOPE.md` (`fy runs digest/envelope`) | Latest run per scenario with deltas; worst case per joint across scenarios with the driving run. Deterministic, capped at 399 lines. The envelope says what it does not cover (gait, stairs, sit-to-stand) and excludes stale or unfinished runs. |
| Viewer | `fy view <scenario>` | Watch a scenario live in the MuJoCo viewer, set up exactly as the runner sets it up. No record is written. |
| Statics | `sim/scripts/statics.py`, scenario `stand_static` (`drive: static_equilibrium`, `support: ground_wrench`) | The torques that hold a pose, with no controller: `mj_inverse` at zero velocity and acceleration with contacts disabled, the ground reaction supplied explicitly through the foot Jacobians (body weight at the CoM's ground projection, split between the feet). Reports the CoP, force split, signed support margin, minimum limit margin (naming the joint) and the equilibrium residual. |
| Pose parameters | `pose` block, `sim/scripts/leanpose.py` | `com_x_rel_ankle_m` plus `lsj_fe_deg`, `tj_fe_deg`, `cj_fe_deg`, `pelvic_tilt_deg` (default 0, positive in the polarity file's flexion direction, signs found by kinematics). Used by `hold_pose`, `stand_static` and the sweeps. |
| Posture sweep | `sim/scripts/sweep.py`, `fy sweep <spec>`, `sim/scenarios/sweeps/` | A grid of up to three pose parameters (cap 2000 points), each a pose solve and a static solve; writes `sim/sweeps/<id>/sweep.json` (`sweep-summary/1`) and `SWEEP.md`. 43 ms per point. |
| Checks | `checks/sim_checks.py` | `check.sim.rom_reachable` (advisory): every limited joint's sweep reaches 99% of the sheet value in the snapshot. Check reports now carry the model hash; a full `fy check` writes `checks/last_run.json`. |

Test command: `python tools/fy test` (offline, about a minute and a half). `python tools/fy check`: all pass except
`check.mjcf.com_pct_stature` (known, waiver unconfirmed).

## Findings

**The neutral pose does not stand.** Hip joint centres, knees and ankles are at x = +0.0566 m; the whole-body CoM is at
x = +0.0167 m, 39.9 mm behind the ankle. The old foot box reached only 41 mm behind the ankle, so the CoM was 1.287 mm in front
of the heel edge and the first PD hold toppled backward at 1.355 s. The cause is the pelvis origin versus hip centre offset
(sheet data plus the ramrod assumption). Nothing in the sheet or template was changed. The fix is the pose
`pose.com_x_rel_ankle_m` (decision recorded in `notebook/2026-10-10-pose-com-x-rel-ankle.md`; default 0.0).

**Foot box (the one model change).** Now from L/4 behind the ankle to L ahead (L = 0.165 m, edges -41.25 mm and +165 mm; centre
3L/8, half 5L/8), through `derive_keys` with the rear fraction `FOOT_REAR_FRACTION = 0.25` as a named design constant. The sole
is still at z = 0 and `floor_contact` passes.

**`hold_pose` now stands (8 s: 7 s settle, 1 s window).**

| Measure | Result |
|---|---|
| Lean angle (ankle dorsiflexion) | 2.6077 deg |
| Window-mean CoM offset from the ankle | -10.9 mm (commanded 0.0; sag -10.9 mm) |
| Support margin, minimum | +29.5 mm |
| Force closure (mean vertical force / weight) | 1.000005 |
| Max penetration | 2.24 mm |
| Mirror-pair torques (same scalar, 2%) | pass |

Standing torque, rms in N m, each side: hip flexion 7.8, knee 7.5, ankle dorsiflexion 3.8, hip ab/adduction 0.6; trunk lumbosacral
flexion 5.0, thoracic flexion 3.2, cervical flexion 0.4. No joint is near a limit. Do not size hip actuators from these: the upper
body's CoM sits about 50 mm behind the hip centres in this stack, so part of the standing hip torque is the ramrod placement.

**Independent statics check.** With `--set pose.com_x_rel_ankle_m=0.02` the summed ankle torque is 10.485 N m (applied torque)
against 10.532 N m from kinematics (0.4%). The plain "body weight times CoM offset" is 5.5% off (0.6 N m of 11.1) because it
leaves out the weight of the two feet, so the expected value includes it. This is why the brief's 5% tolerance needed that term.

**`rom_sweep`.** 18 limited joints each swept across 99% of the model range at about 36 deg/s peak; 13 unlimited joints are recorded
as skipped with reason `unlimited` (lumbosacral x3, thoracic x3, cervical x3, shoulder abduction/adduction and rotation both
sides). Left and right curves agree to 1e-9. Hip flexion peaks at 35.5 N m, consistent with a roughly 13 kg leg.

**Mirror torques.** With the model's axes `(ax, ay, az) -> (-ax, ay, -az)` a mirror-symmetric load gives the same scalar torque on
both sides; only the world-frame vectors are mirror images. The Stage 1 brief was corrected to say so.

## Stage 1c: standing loads without gains

**The PD hold's standing loads are biased by its sag.** `hold_pose` reports `kp` times a sag angle, at an equilibrium behind the
commanded pose. Against `stand_static` on the same pose (rms torque, N m, right side; CoM over the ankle):

| Joint | Static | Held, kp 1000 | Held, kp 2000 | Bias at 1000 | Bias at 2000 |
|---|---|---|---|---|---|
| Ankle dorsiflexion | 0.28 | 5.27 | 3.79 | +4.99 N m | +3.50 N m |
| Knee | 5.29 | 8.77 | 7.54 | +66% | +43% |
| Hip flexion | 6.94 | 8.36 | 7.83 | +20% | +13% |
| Lumbosacral | 6.21 | 4.36 | 5.04 | -30% | -19% |
| Thoracic | 3.80 | 2.81 | 3.17 | -26% | -17% |

The CoM sags 17.3 mm behind the command at kp 1000 and 10.9 mm at 2000; kp 4000 falls. The bias runs both ways: the hold
overstates the ankle and knee and understates the trunk. `hold_pose` is now `envelope: false` (verification only); the load envelope
takes standing loads from `stand_static`, which also gives the unlimited joints their rows.

The prediction held in part. Static ankle torque is near zero (feet only): yes. Held ankle torque about twice as large at 1000
as at 2000: no, 1.39 times, because every joint sags and not only the ankle. Hip and knee change little with kp: the hip yes
(7%), the knee 16%. Every held torque approaches its static value as kp rises: yes, apart from elbow noise below 0.02 N m. A slow
test (`tests/test_bias.py`) asserts only the qualitative claims.

**The solver is sound.** Its joint torques agree with an independent subtree-moment formula (no `mj_inverse`) to 1e-9 relative on
every hinge and with the analytic pendulum; the root residual is 1.1e-13 N (limit 1e-9 times body weight); flipping the sign of the
ground force breaks the residual, as the mutation test requires. With the CoM over the ankle the support margin is 41.25 mm (the
distance to the heel edge), the force split is 319.1 N right and 317.9 N left (the CoM is 0.16 mm right of centre), and the lean
angle is 2.60769 deg.

**The knee is 1.6 deg from its extension stop at neutral.** So every standing pose has a minimum limit margin of at most 1.6 deg,
and a 2.0 deg default for the sweep's `min_limit_margin_deg` made 0 of 392 points feasible. Decision (Joe): the default is 1.0 deg and
the limit, which is sourced from biomechanics literature, is unchanged. The knee is the only joint within 2 deg of a limit, at
every feasible point.

**`posture_sensitivity`** (placeholder ranges, no cited source: CoM -0.02 to 0.05 m, lumbosacral and thoracic flexion -10 to 20 deg,
392 points). All points are feasible, so no corner is infeasible. Spread of each sagittal-chain torque across the grid (N m):

| Joint | Min | Max | Spread |
|---|---|---|---|
| Hip flexion | -12.79 | 17.16 | 29.9 |
| Knee | -13.79 | 12.75 | 26.5 |
| Ankle | -15.67 | 6.67 | 22.3 |
| Lumbosacral | -46.20 | 14.80 | 61.0 |
| Thoracic | -32.50 | 11.69 | 44.2 |
| Cervical | -4.47 | 1.67 | 6.1 |

The lowest sum of squared torques (173.6 N2 m2, unnormalised) is at CoM +0.01 m, lumbosacral +5 deg, thoracic -10 deg. That is a property
of the model, not a recommended posture. Posture moves the trunk and hip torques by tens of N m, far more than the gain bias above.

**Other 1c points.** Infeasible static poses are recorded with outcome `fell` and the reasons in a new optional `findings` list
(`run-summary/1` amended additively; Joe accepted). `SWEEP.md` lists every point up to 250; above that it lists the infeasible
reasons and the 15 lowest and highest points, with the full list in `sweep.json` (690 KB for 392 points). The pose solver now uses
regula falsi: 44 ms per pose instead of 550 ms, with its lean angle within 2e-8 deg of the earlier value.

## Choices that were mine, and why

- Inverse-dynamics closure on a forward run must be within 1e-9 of the peak torque. Measured 1.1e-13 N m (pendulum) and 6.6e-13 N m
  (the model with contacts): round-off only. Inverse dynamics is used only in gantry mode.
- `hold_pose` runs at dt 0.0002 s (not 0.002): the explicit PD on `qfrc_applied` diverged at 0.002 and 0.0005. Gains are
  `kp = min(2000, I (0.25/dt)^2)` per joint and a damping ratio of 1.5, all recorded in the scenario. At 1.0 the whole body sways
  about the ankles with almost no damping and outlives any settle time; 2.0 and 3.0 diverged.
- 99% of a limit under 10 degrees is closer than the 0.1 degree "limit hit" tolerance (the knee's -1.6 deg), so the knee counts as
  touching its limit in `rom_sweep`; that is by definition, not a fault.
- Static solve: the CoP is placed at the CoM's ground projection (no horizontal forces in statics); feasibility needs it inside the hull of the foot-box sole corners within 1 mm of the floor.
- Mirror pairs in the static solve agree within 2% (not tighter) because of the 0.16 mm lateral CoM offset.
- Dependency added: `jsonschema` 4.26.0 (pre-approved).

## Still open

- A cited standing CoM position relative to the ankle, and whether the pelvis-origin versus hip-centre offset should be fixed in the
  sheet (then the neutral pose would stand).
- The standing hip torque still includes the ramrod placement of the upper body (CoM about 50 mm behind the hip centres); `stand_static` removes the gain bias, not that one.
- Seven sheet ROM values (lumbosacral x4, shoulder adduction and rotation) and ranges for the thoracic and cervical joints; until
  then those joints have no sweep and the envelope has no row for them.
- Gait, stairs and sit-to-stand are Stage 2: they need reference kinematics with citable provenance, and a balance strategy.
- `com_pct_stature` waiver is still `confirmed: false`.
- Housekeeping from `notebook/2026-10-10-stage0-loose-ends.md` is unchanged.

## Using it

`python tools/fy run hold_pose`, `python tools/fy runs digest`, `python tools/fy view hold_pose`, `python tools/fy run stand_static`, `python tools/fy sweep posture_sensitivity`. Run records are stamped with
the commit; commit your work first, or the record says `git_dirty`.
