STATE: base 98be2bcae0ee | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2031/2034 | dirty yes (this task's files, uncommitted when generated)

# Memo 47: the reruns on the current model changed no load

## Decision summary

- **The load envelope did not change.** `ENVELOPE.md` (191 lines) is identical to the committed one once run ids and model, snapshot and commit hashes are replaced by placeholders: the `diff` is empty. That covers every worst-case torque, speed and power and every gait cell. `gait_extract.json` differs in exactly four fields (`git_commit`, `snapshot_sha256`, `model_sha256`, `gait_id`) and in no number: 0 numeric differences, compared at full float precision.
- **So the sheet rebuild moved the model hash but not the dynamics that the loads read.** Reference value: the rerun was needed for provenance (the committed records named the old model, `cfa2e0743e83`), not because a load moved. That is a result I did not expect and did not tune toward: I changed no input.
- **One number changed, and by code, not by model:** `stand_static` `limit_margin_min_deg` 0.0 to 1.6 (smallest margin among non-zero-width stops, now knee_left; the old digest text said 1.74 knee_right). Commit `a025cf9` (memo 26 Q4/Q5, after the previous rerun) made the margin exclude the zero-width stops; the old record predates it.
- **No stale flags remain:** `DIGEST.md` has 0 STALE lines (it had 3). All four new records are `git_dirty: false`, commit `98be2bc`, model `1ceee2452e18`, snapshot `492fe816e6d8`.
- **The xfail is removed and the test passes** (`tests/test_gait_extract.py`: 20 passed). No pin needed re-recording, which agrees with the numbers above.
- **No accepted record, requirement, thread record or doc cites an old number or hash by value** outside memos and run records: nothing to list, nothing edited.
- **Decisions for Joe:** none forced. One recommendation: run `--write-baseline` (memo 46 question 2) only if you want `walk_reference.json` re-recorded against the new model hash; given the numbers are identical it would change only provenance.
- **What would change the conclusion:** a sub-precision shift in the worst-case file, which is compared at printed precision (0.01 Nm); the gait extract is compared at full float equality.

## 1. Digest and envelope

`fy runs digest` and `fy runs envelope` rerun on the final records (176 and 191 lines). Envelope: scenario classes rom_sweep (`run.20261028-1654-rom_sweep`), stand_static (`run.20261028-1653-stand_static`), walk_treadmill (`gait.20261028-1654-walk_treadmill`); hold_pose excluded as verification only. STALE count in DIGEST.md: 0.

## 2. The xfail

Removed. `python -m pytest tests/test_gait_extract.py`: 20 passed.

## 3. Before and after

Old = committed `ENVELOPE.md` at `98be2bc`; new = regenerated. A joint pair (left/right) is shown once where the file shows identical rows (the worst-case file does; the gait rows are shown per side).

Worst case per joint (peak torque Nm, peak speed rad/s, peak power W), all `rom_sweep` or `stand_static` drivers, unchanged drivers:

| joint | torque | speed | power | change |
|---|---|---|---|---|
| lsj_fe | 77.75 | 0.298 | 17.22 | 0.0% |
| lsj_lat | 48.47 | 0.197 | 6.37 | 0.0% |
| hip_fe | 35.50 | 0.447 | 15.05 | 0.0% |
| hip_aa | 23.33 | 0.179 | 2.85 | 0.0% |
| toe | 19.81 | 0.217 | 2.80 | 0.0% |
| knee | 7.56 | 0.389 | 2.89 | 0.0% |
| shoulder_fe / aa | 6.45 | 0.623 / 0.496 | 4.00 / 3.20 | 0.0% |
| tj_fe | 3.12 | 0.000 | 0.00 | 0.0% |
| elbow | 1.89 | 0.420 | 0.79 | 0.0% |
| cj_fe | 0.39 | 0.000 | 0.00 | 0.0% |
| ankle_pdflex | 0.37 | 0.236 | 0.08 | 0.0% |
| wrist, ankle_ie, lsj_ax, hip_ier, cj_lat, tj_lat, cj_ax, tj_ax, shoulder_ier | at most 0.18 | | | 0.0% |

Gait, method A_filtered, trunk rigid, 95th percentile across subject-strides (torque p95 Nm / torque max Nm / power+ p95 W / speed p95 rad/s). Old equals new in every cell:

| joint | 1.4 m/s right | 1.4 m/s left | 1.6 m/s right | 1.6 m/s left |
|---|---|---|---|---|
| hip_fe | 66.4 / 114.1 / 156 / 4.50 | 74.3 / 138.2 / 202 / 4.68 | 73.0 / 99.2 / 225 / 5.10 | 85.2 / 124.7 / 210 / 5.06 |
| knee | 89.9 / 120.7 / 118 / 7.01 | 106.4 / 158.4 / 130 / 7.28 | 112.3 / 134.8 / 170 / 7.42 | 116.9 / 175.1 / 168 / 7.57 |
| ankle_pdflex | 127.3 / 141.8 / 432 / 6.38 | 141.8 / 181.4 / 430 / 6.33 | 135.4 / 150.7 / 501 / 6.11 | 147.3 / 176.6 / 501 / 6.17 |
| hip_aa | 90.4 / 108.3 / 112 / 2.46 | 91.1 / 126.1 / 118 / 2.51 | 89.2 / 111.3 / 113 / 2.50 | 93.1 / 119.5 / 124 / 2.47 |
| hip_ier | 25.0 / 56.7 / 15 / 2.75 | 23.5 / 51.0 / 11 / 3.07 | 28.8 / 45.6 / 18 / 2.86 | 26.5 / 39.3 / 15 / 3.12 |

The 0.5 m/s acceptance-speed rows (10) are also identical. Run summaries, old against new, field by field: `hold_pose` and `rom_sweep` differ only in `checks/status_model_sha256`; `stand_static` differs in that field and `diagnostics/limit_margin_min_deg` (0.0 to 1.6, above). The digest's other differences are run ids, commit hashes, the run count in each window line (4, 5 and 6 runs recorded) and the "smallest margin" text.

## 4. Citations of old numbers

Searched tracked files outside `docs/memos/`, `sim/runs/`, `sim/gait/` and `docs/STATE.md` (so decisions, requirements, thread records and docs, CLAUDE.md, CONVENTIONS, roadmap nodes, catalog):

| What | Result |
|---|---|
| old model `cfa2e0743e83`, old snapshot `cf4fdfe08804`, old run ids `20261021-154x`, old gait id `20261021-1445`, old commit `fb60b38`/`8bc6c11` | no hit |
| load values that appear in `ENVELOPE.md` (77.75, 35.50, 48.47, 19.81, 7.56, 1.89) | no hit in decisions, requirements, thread records, catalog or docs |
| the one changed value (`limit_margin_min_deg`, "smallest margin 1.74 deg") | cited only by code, schema and the memo-26 era briefs as a field name, never as a value |

Nothing to amend, so no accepted record was edited. Memos cite the old hashes as history and were left alone.

## Mistakes and caveats

- `ENVELOPE.md` is compared at its printed precision (torques 0.01 Nm, gait 0.1 Nm); `gait_extract.json` at full precision. I did not diff the raw timeseries.
- I did not explain why the model hash moved without moving the loads (sheet rebuild `96e3670` and the snapshot change `d379525` landed in between); I only show it did not.

## Tests

Between changes: `tests/test_gait_extract.py` 20 passed. Full suite, once, through `fy state`: 2031 passed, 0 failed, 3 skipped (2028 + the two xfail-listing tests + the formerly xfailed test).
