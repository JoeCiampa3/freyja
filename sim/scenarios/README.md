# sim/scenarios/

One authored `<name>.yaml` per scenario; `fy run <name>` runs it. The file name must equal its `name:` key.

Keys: `model`, `seed`, `support` (`ground` or `gantry`), `drive` (`inverse_dynamics_playback`, gantry only, or
`controller`, forward dynamics), `controller` (`name` of a module in `sim/controllers/`, `version`), `duration_s`,
`window` (`start_s`, `end_s`: the measurement window), `options` (`timestep_s`, `integrator`, `verify_inverse`),
`fall` (thresholds, defaults: pelvis height below 60% of initial, trunk tilt beyond 45 degrees) and `params`
(handed to the controller). Everything in the file, PD gains and any timestep or integrator override included, is copied
into the run record.

- `rom_sweep.yaml` each limited joint across 99% of its model range, gantry, inverse dynamics
- `hold_pose.yaml` ideal-torque PD holds the neutral standing pose, forward dynamics, applied torque

Joint torque is about the model's own hinge axes (the decoupled hip architecture), not actuator torque.
