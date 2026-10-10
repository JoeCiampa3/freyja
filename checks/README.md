# checks/

Executable checks (CONVENTIONS section 7). `python -m pytest checks` runs them and their mutation tests.

- `checklib.py` registry, model context, waivers and `run_checks`
- `mjcf_checks.py` the `check.mjcf.*` checks
- `sim_checks.py` the `check.sim.*` checks, which read run summaries (`check.sim.rom_reachable`)
- `joint_polarity.yaml` expected sign of every hinge (DRAFT until Joe approves it)
- `waivers.yaml` known deviations; `confirmed: false` entries are proposals and do nothing
