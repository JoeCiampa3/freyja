# sim/sweeps/

One directory per sweep, named from the sweep id without `sweep.` (`20261012-1430-posture_sensitivity/`):

- `sweep.json` the sweep record (`sweep-summary/1`, schema in `docs/schemas/`): every grid point with its parameters, feasibility,
  reasons, support margin and static joint torques, plus per-joint ranges over the feasible points. Tracked in git.
- `SWEEP.md` the readable summary, generated; do not edit.

Made by `fy sweep <spec>` from `sim/scenarios/sweeps/<spec>.yaml`. A sweep creates no run directory per point. The sum of squared
torques is unnormalised and a minimum is a property of the model, not a recommended posture.
