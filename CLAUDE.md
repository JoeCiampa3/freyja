Read `CONVENTIONS.md` first; it is the contract for this repo.
Current brief: `docs/briefs/stage1b-brief.md`.
Run records: `sim/runs/DIGEST.md` (latest run per scenario) and `sim/runs/ENVELOPE.md` (worst case per joint); regenerate with `python tools/fy runs digest` and `python tools/fy runs envelope`; run a scenario with `python tools/fy run <scenario>`. Standing loads come from `stand_static` (gain-independent), not `hold_pose`. Posture sweeps: `python tools/fy sweep <spec>` writes `sim/sweeps/<id>/SWEEP.md`.
Test command: `python tools/fy test` (same as `python -m pytest` from the repo root); `python tools/fy check` runs the model checks.
