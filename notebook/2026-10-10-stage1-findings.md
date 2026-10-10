---
origin: claude
---
# Stage 1 findings and open questions

Records: `sim/runs/20261010-1712-hold_pose/`, `sim/runs/20261010-1712-rom_sweep/`. Digest and envelope: `sim/runs/`.

## 1. The neutral standing pose has no static equilibrium (hold_pose falls at 1.355 s)

- The whole-body CoM is at x = +0.0167 m. The hip joint centres, knees and ankles all sit at x = +0.0566 m (the
  leg chain is vertical below the hip centre), so the CoM is 39.9 mm behind the ankle line.
- The foot box spans x = 0.0154 to 0.1804 m. The CoM is therefore 1.287 mm in front of the heel edge
  (`support_margin_first_step_m`), and any sag of the ankles moves it behind the heel.
- The trunk, head and arms are placed from the pelvis frame origin (x = 0), not from the hip joint centres
  (x = +0.0566). Whether that offset is in the sheet's `MuJoCo Positions` data or a template/pre_processor convention
  was not investigated; no geometry was changed.
- PD gains 2000 N m/rad (capped by inertia), dt 0.0002 s. Stiffer gains (20000 N m/rad) went numerically unstable.
- Open: is the pelvis-origin versus hip-centre offset intended? A standing hold, and every ground scenario, needs it
  settled first. Stage 2 needs a balance strategy either way.

## 2. Seven sheet ROM values are still missing

Unlimited joints (13): lsj_fe, lsj_lat, lsj_ax, shoulder_aa and shoulder_ier (both sides), and tj_* and cj_* (the
template has no range placeholders for them). They are skipped by rom_sweep and have no envelope row.

## 3. Interpretation to confirm: mirror-pair torques

The brief says mirror joints carry "equal and opposite-sign (per the mirror rule)" torques. With the model's axes
`(ax, ay, az) -> (-ax, ay, -az)` a mirror-symmetric load gives the SAME scalar joint torque on both sides; the
world-frame torque vectors are the mirror images. The test (xfail, as hold_pose falls) and the rom_sweep test
(which passes: left and right curves agree to 1e-9) use the same-sign reading.
