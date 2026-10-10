# Stage 1b brief (for Claude Code): a standing equilibrium

Read `CONVENTIONS.md`, the Stage 1 brief and `notebook/2026-10-10-stage1-findings.md` first.

Stage 1 found that the neutral pose has no static equilibrium: the whole-body CoM is at x = +0.0167 m, the ankle is at +0.0566 m, the foot box spans 0.0154 to 0.1804 m, and `hold_pose` topples backward at 1.355 s. The cause is in the sheet data and the documented ramrod assumption: the hip joint centres sit 56.6 mm anterior of the lumbosacral joint, while the trunk, head and arms stack vertically from the pelvis origin. Do not change the sheet, the template or `pre_processor`. The fix is a pose, and a pose is a scenario input.

## Ground rules

CONVENTIONS section 9 applies. No new dependencies. Tests first, one commit per task. Stop and ask before changing a geometry value, a check tolerance, or the foot box.

## Decisions for Joe (settle before T2)

The default CoM target, `pose.com_x_rel_ankle_m`. Proposed 0.0, directly over the ankle: ankle torque is near zero and the heel edge is 41 mm behind. Real quiet standing sits forward of this, but any literature value must be cited before it becomes the default. This is a design parameter, so the standing ankle torque is a function of it, not a measurement.

The foot box forward extent. The box reaches 123.75 mm ahead of the ankle; the sheet's foot length is 165 mm from the ankle to the midpoint of the metatarsal heads. T0 reports the numbers; Joe decides whether to change the derived keys.

## T0. Housekeeping and report

Replace the mirror-torque sentence in the committed `docs/briefs/stage1-brief.md` with: "carry the same scalar torque within 2% (the mirror rule's axis flips already encode the sign; only the world-frame torque vectors are mirror images)". Run `fy test`. Report the foot box x-extent relative to the ankle against the sheet's foot length, and stop on that item.

## T1. Lean-pose solver

Given the model and a target `com_x_rel_ankle_m`, find the rigid lean about the ankle: every joint neutral except ankle dorsiflexion (both sides) equal to the lean angle, with the root pitch and position solved so that both soles lie flat on z = 0 with no penetration. Solve numerically with forward kinematics (bisection or Newton) rather than assuming sign conventions. Assert the ankle limit is respected. Record the lean angle and the achieved CoM offset in `diagnostics`.

Tests first:
- On a two-link fixture with a known CoM, the solver reproduces the analytic angle.
- On Freyja, it returns a target-0 lean near 2.6 degrees (an estimate from a 39.9 mm offset at 0.87 m CoM height; report the actual) and the achieved offset within 0.1 mm of the target.
- Both soles are flat within 0.1 mm; no joint outside its limits.
- An unreachable target fails with a clear message, not a clipped pose.

## T2. Use it in `hold_pose`

`hold_pose` sets the solved pose at reset; `pd_hold` already holds whatever angles it finds at reset. Add `pose: {com_x_rel_ankle_m: 0.0}` to the scenario and a `fy run <scenario> --set key=value` override that is recorded in the summary's scenario params. Add the window-mean CoM offset to `diagnostics`.

Update the two xfail tests: they should now pass, and the strict xfail will fail loudly if they do. Add one independent check: with `--set pose.com_x_rel_ankle_m=0.02`, the summed ankle torque equals body weight times the measured window-mean CoM offset within 5% (floor 0.2 N m). The measured offset comes from kinematics, the torque from the applied torques, so the two paths are independent.

If it still falls or fails force closure, keep the xfail with a new reason and report the numbers.

## T3. Wiring

The digest shows the pose parameters, the lean angle, the CoM offset and the sag. Update the comment in `hold_pose.yaml`.

## Done when

All suites green offline, `git status` clean. The final message reports: the lean angle, the sag of the window-mean CoM from the commanded value, the support margin, the standing torque per joint for the legs and trunk, any joint near a limit, and the force closure ratio.

One caveat to carry forward, not to fix here: the upper body's CoM sits about 50 mm behind the hip centres in this stack (estimated from the findings' numbers), so standing hip torques include roughly 10 N m of extension per side that comes from the ramrod placement. Do not size hip actuators from standing loads until that is settled.
