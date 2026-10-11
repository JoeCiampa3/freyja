# sim/scenarios/

One authored `<name>.yaml` per scenario; `fy run <name>` runs it. The file name must equal its `name:` key.

Keys: `model`, `seed`, `support` (`ground` or `gantry`), `drive` (`inverse_dynamics_playback`, gantry only, or
`controller`, forward dynamics), `controller` (`name` of a module in `sim/controllers/`, `version`), `duration_s`,
`window` (`start_s`, `end_s`: the measurement window), `options` (`timestep_s`, `integrator`, `verify_inverse`),
`fall` (thresholds, defaults: pelvis height below 60% of initial, trunk tilt beyond 45 degrees) and `params`
(handed to the controller). Everything in the file, PD gains and any timestep or integrator override included, is copied
into the run record.

- `rom_sweep.yaml` each limited joint across 99% of its model range, gantry, inverse dynamics
- `hold_pose.yaml` ideal-torque PD holds a standing pose, forward dynamics, applied torque. Verification only
  (`envelope: false`): its torques are kp times a sag angle, so they depend on the gains
- `stand_static.yaml` the gain-independent static solve for the same pose (`drive: static_equilibrium`,
  `support: ground_wrench`, zero-width window): contacts disabled, ground reaction supplied explicitly. Use this for standing loads
- `sweeps/*.yaml` posture sweeps for `fy sweep`: a base scenario, a grid of up to three pose parameters and constraints

`pose` block (hold_pose, stand_static): `com_x_rel_ankle_m` (required) and sagittal offsets `lsj_fe_deg`, `tj_fe_deg`,
`cj_fe_deg`, `pelvic_tilt_deg` (default 0, positive in the model's flexion direction), solved by `sim/scripts/leanpose.py`.
`envelope: false` marks a verification-only scenario: the load envelope lists it as excluded and it never drives a row.
`fy run <name> --set key.sub=value` overrides a value and records it.

Joint torque is about the model's own hinge axes (the decoupled hip architecture), not actuator torque.
