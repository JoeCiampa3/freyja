STATE: base 752354f7a0da | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2035/2038 | dirty yes (this task's files, uncommitted when generated)

# Memo 49: baseline rule C implemented, walk_reference.json re-recorded

## Decision summary

- **Done as approved (option C).** `gait.baseline_methods` now decides on the sizing speeds only. The 0.5 m/s acceptance speed (`ACCEPTANCE_SPEEDS = ("0.5",)`, tied by a test to `runs_report.GAIT_ACCEPTANCE_SPEEDS`) no longer blocks a method; its misses stay in `band_verdicts_full_run` as findings. The band (corr >= 0.9, RMS <= 15%) is untouched. A sizing-speed miss still blocks a method; with no sizing-speed verdict nothing is baselined. The new file records `acceptance_speeds_not_deciding: ["0.5"]`.
- **The baseline is re-recorded** from `gait.20261028-1654-walk_treadmill` (commit `98be2bc`, `git_dirty` false, model `1ceee2452e18`): `baselined_methods = ['A_filtered']`, not baselined `A_native, B, H`, and the reproduction subset (AB06, 1.4 m/s, 3 strides) holds 2 entries (`rigid/A_filtered`, `counter_rotate/A_filtered`). I reached this by calling `write_baseline` on the existing record (no hour-long rerun; same function the flag calls).
- **`check.sim.walk_reference` is PASS** (it was SKIP, "superseded by a design change"): the baseline reproduces on the current model.
- **A consequence I handled and you should know about:** `tests/test_foot_split.py::test_with_the_old_box_...` compared an old-box model with the tracked `walk_reference.json` to prove the foot-split change altered nothing else. With the baseline re-recorded on the current model that premise is gone (72 metrics differ, for example ankle_ie_left corr 0.547 baseline against 0.600), so the test failed. I did not touch its tolerance or its assertion: I froze the old file as `tests/fixtures/walk_reference_pre_foot_split.json` (gait.20261014-1929, snapshot `e5cc96ceed7e`) and pointed the test at it. It passes as before, so the old box still reproduces the old reference. If you would rather retire that regression, say so.
- **Decisions for Joe:** none forced. Retire or keep the frozen-fixture regression: recommend keep (it costs one 4 s test).
- **What would change the conclusion:** if the sizing-speed rows of A_filtered ever miss the band, `baselined_methods` becomes empty again and the check FAILs; that is intended.

## Tests

Tests first: two new in `tests/test_gait.py` (acceptance speed does not decide; constants agree), seen failing. Then: `tests/test_gait.py` 27 passed (151 s), `checks` + `test_foot_split` + `test_roadmap_schema` + `test_gait_extract` all passed after the fixture repoint. Full suite, once, through `fy state`: 2035 passed, 0 failed, 3 skipped.
