# Stage 2f brief (for Claude Code): level walking at 0.5 m/s

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`. This brief belongs to the Ariadne track and closes roadmap leaf `rm.v1-gait-0p5`.

## Purpose

v1's acceptance trial walks at 0.5 m/s. Stage 2 computed walking loads at 1.4 and 1.6 m/s only. Sizing stays on 1.4 and 1.6 (the hardware rule: v1 interfaces are final, so the hardware is sized for the full task set). The 0.5 m/s case does two other jobs: it is the condition the controller, the power budget and the trial itself run under, and it checks that no joint row peaks at low speed. Slow gait lengthens stance and double support, so peaks are not assumed to fall monotonically with speed.

This brief adds 0.5 m/s to the Camargo ingestion and the gait pipeline, re-checks method A's agreement band at that speed (the band was established at 1.4 and 1.6, not at 0.5), regenerates the tracked extract and the envelope, and adds the load case `lc.walk-0p5` to the thread as a proposed record.

The outputs are interim. Joe is re-verifying the BSIP rows in the sheet and several Stage 2 decisions (hip stop and pelvis pose, toe joint, trunk modes) will change the snapshot or the model. The final regeneration of all three speeds is `rm.v1-stage2-closed`, not this brief. Say so in the memo, and stamp nothing as final.

## Out of scope

- Any change to method A, B or H, the band constants (`gait.BAND_CORR`, `gait.BAND_RMS_PCT`, `gait.BAND_STEMS`), the filter cutoff, the offset and pitch-flag subject lists, the sensitivity settings, the trunk modes, the model, the template, `pre_processor` or the sheet.
- Any change to what the sizing statistic is computed over. It stays 1.4 and 1.6.
- Any speed other than 0.5 (no 1.0, no 0.8).
- Other thread records, and activating any record. `lc.walk-0p5` is created `proposed`.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, including rule 10 on coupled tasks.

- **The snapshot may move under you.** Joe is verifying BSIP rows in the sheet and might correct some and run `fy build`. Record `params/snapshot.csv`'s sha256 prefix at T0. If `params/` or `sim/models/freyja.xml` changes on disk or in git while you work, stop at the next commit boundary, write the memo with the new hash, and do not rerun anything. Never run `fy build` yourself.
- **Raw data.** The raw Camargo files are outside the repo (`CAMARGO_RAW_DIR`, or `camargo_raw_dir` in `sim/local_config.json`, which only Joe edits). If they are not reachable from this machine, stop at T0 and say so.
- **Findings stop the work.** A band failure at 0.5 m/s, a change in any existing 1.4 or 1.6 number, or a cap exceeded is a finding: report the measured number and stop. Do not adjust a tolerance, a band, a cutoff or a subject list to make it pass.
- **Determinism.** Same inputs, byte-identical outputs. No timestamps in tracked artifacts.

Stop and ask before:
- changing any constant or list named under Out of scope;
- raising `gait.MAX_LINES` or any other cap;
- changing a schema version other than as T3 describes;
- creating `lc.walk-0p5` if the band check at 0.5 m/s fails (T4);
- touching the processed 1.4 or 1.6 arrays.

## Tasks

**T0. Baseline and inventory (read-only; nothing is committed).** Run `fy test` and record its time and count. Record the snapshot, model and manifest hashes. Then:

1. **Dataset availability at 0.5 m/s.** From the manifest, the audit and the raw files: which subjects have treadmill segments at 0.5 m/s under the ingestion's existing steady-state rule (`steady_segments`, with the same tolerance and flatness settings as 1.4 and 1.6), and how many strides each would give. Report it beside the 1.4 and 1.6 counts (469 and 519 strides in the tracked extract). If fewer than half the subjects that contribute at 1.4 contribute at 0.5, or fewer than 100 strides in total, stop and report. Both thresholds are mine, chosen so that a p95 over the strides means something; say if you think they are wrong.
2. **Everything that assumes the speed set.** A table of file, line, what it assumes and the change it needs: the gait spec and `camargo_mapping.yaml` (`speeds_mps`, the stride-duration plausibility range), `ingest_camargo.py`, `gait.py`, `gait_extract.py` and the `gait-extract/1` schema (does it enumerate speeds or accept any key?), `runs_report.py` (how the envelope aggregates across speeds today: per-speed rows, or a maximum), and every test that hard-codes `("1.4", "1.6")`, a stride count or a stride-duration range. No edits.
3. **The stride-duration range.** The spec's plausibility range rejects mis-segmented strides and was set for 1.4 to 1.6. Stride duration rises as speed falls, so it will reject legitimate 0.5 m/s strides. Report the range, and how many 0.5 m/s strides it would reject.

**T1. Ingest 0.5 m/s.** Tests first, then code.

- Add 0.5 to the ingestion's speed list. Generalise the stride-duration range to a per-speed range. For 1.4 and 1.6 it is the existing range, unchanged. For 0.5, the existing range's relative half-width, `(hi - lo) / (hi + lo)`, applied around the median stride duration measured at 0.5 m/s across the data. This is the one tolerance this brief lets you set. State the measured median, the bounds and the number of strides each bound rejects.
- Tests: `steady_segments` at target 0.5 on a synthetic speed trace, as the existing test does for 1.6; the per-speed range; the strides at 0.5 are longer than at 1.4; the per-speed stride-count and duration asserts no longer assume `0.9 < mean < 1.25` for every speed.
- Run the ingestion for all subjects. The processed arrays and the manifest change. **The 1.4 and 1.6 entries must be byte-identical to before** (hash each speed's arrays before and after, per subject). Any difference stops the work.
- Commit the code, the spec and the updated manifest. The processed arrays stay untracked, as today.

**T2. Run the gait pipeline at 0.5 m/s.** Tests first for every hard-coded speed T0 found; then add 0.5 to the walk_treadmill spec's speeds and run `fy gait walk_treadmill` with everything else as it is: the same methods, trunk modes, sensitivity settings and subject lists.

- **Reproduction.** The 1.4 and 1.6 cells of the new record must reproduce the tracked extract's numbers to the existing reproduction check's tolerance (the snapshot has not changed). If they do not, stop: the generalisation changed something.
- **The band at 0.5.** Report A_filtered's verdict at 0.5 m/s for the three sets the band is reported on (all, without offset, without pitch-flagged) and per sagittal joint (`gait.BAND_STEMS`): the correlation, the RMS as a percentage of peak-to-peak, and the RMS in N m. Moments are smaller at 0.5, so a percentage of peak-to-peak can fail where the absolute error is small. Report both and let the verdict stand as measured.
- `GAIT.md` has a line cap (`gait.MAX_LINES`). If three speeds exceed it, report the measured line count and propose a layout; do not raise the cap.
- Commit the code and the spec. The gait record itself stays untracked, as today.

**T3. Extract and envelope.** Tests first.

- If the `gait-extract/1` schema enumerates speeds, change it to accept the new key. Keep the version `/1` only if every document that validated before still validates; otherwise bump to `/2`, read `/1` documents or regenerate them, and amend `CONVENTIONS.md` in the same commit (rule 7).
- Regenerate the tracked extract (`fy gait walk_treadmill --write-extract`) and the envelope (`fy runs envelope`). `ENVELOPE.md` gains 0.5 rows, labelled as the acceptance speed. Wherever the envelope takes a maximum across speeds (T0.2 says whether it does), it takes it over 1.4 and 1.6 only, as today, with the 0.5 rows shown beside. Every existing worst-case row must be unchanged (diff them). Mutation test: change one 0.5 value in a fixture extract and the envelope text changes.
- Commit the code, the regenerated extract and `ENVELOPE.md`.

**T4. The load case.** Do this last, and only if T2's band check at 0.5 passes for A_filtered. If it fails, do not create the record: the leaf's pass criterion is the record's existence, and Joe decides what a failed band means for it.

Write `thread/records/lc.walk-0p5.yaml` as `proposed`, modelled on `lc.walk-1p4`: `source` is the walk_treadmill gait spec with the condition 0.5 m/s, `independent_source_required: false`, and notes with the same reasons (inverse dynamics with the ground reaction supplied explicitly, no contact solver; provisional trust stays on the envelope rows). Its purpose says it is v1's acceptance speed, not a sizing speed. The record restates no number. Run `fy thread build`, `fy thread validate` and `fy check`, and commit the record and the regenerated outputs.

**T5. Checkpoint.** Write the memo per `CLAUDE.md` rule 6, numbered one above the highest in `docs/memos/`. Findings first. Include:

- the T0 inventory and what changed;
- the strides per speed and the subjects contributing at 0.5, and the T1 stride-duration bounds;
- the band table at 0.5 beside 1.4 and 1.6;
- **non-monotonic rows.** Every joint row (A_filtered, rigid) whose 0.5 m/s p95 torque, speed or power exceeds its 1.4 m/s value. Say plainly if there are none;
- the reproduction result, the timings (ingest, the full gait run), the tests added and their runtime;
- that the outputs are interim and the snapshot hash they carry.

Run `fy state` and stop.

## Decisions this brief makes (Joe approves them by committing it)

1. The 0.5 rows are shown in the envelope but do not enter any sizing statistic.
2. The stride-duration range becomes per-speed; 0.5's is the existing relative width around the measured 0.5 median.
3. The availability thresholds: half the subjects and 100 strides.
4. `lc.walk-0p5` is created `proposed` with `independent_source_required: false`, like the other walking cases, and only if the band check passes.
5. These outputs are interim; the final regeneration is `rm.v1-stage2-closed`.

## Prerequisite for Joe

Commit this brief and point the "Current Ariadne brief" line in `CLAUDE.md` at it. Do not run `fy build` while the session is running; do the BSIP verification in the sheet and the notebook, and hold any correction until Code stops.
