Read `CONVENTIONS.md` first; it is the contract for this repo.
Current brief: `docs/briefs/stage1-brief.md`.
Run records: `sim/runs/DIGEST.md` (latest run per scenario) and `sim/runs/ENVELOPE.md` (worst case per joint); regenerate with `python tools/fy runs digest` and `python tools/fy runs envelope`; run a scenario with `python tools/fy run <scenario>`.
Test command: `python tools/fy test` (same as `python -m pytest` from the repo root); `python tools/fy check` runs the model checks.
