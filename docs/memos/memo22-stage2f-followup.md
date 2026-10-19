# Memo 22: Stage 2f follow-up to memo 21 (D1 to D4 done)

STATE: base 28acae918ac6 | brief architecture sha256:2ecf3ee5c019, ariadne sha256:1ac4d746673a | snapshot sha256:e5cc96ceed7e | tests 1353/1353 | dirty yes

## Decision summary

- All four of your decisions are done, one commit each, in your order: D4 `e642e92`, D3 `3a73375`, D2 `e231760`, T3 `848dff9`, T4 `28acae9`. Full suite before each commit; no `fy build`; snapshot e5cc96ceed7e and model c4d7757d45fe unchanged throughout.
- The 0.5 m/s rows are in the extract and `ENVELOPE.md`, labelled `acceptance speed, not for sizing`. Hip and knee carry `outside band` (corr 0.861 / RMS 20.1% and 0.892 / 20.2%, band 0.90 / 15%); the ankle carries `within band` (0.975 / 8.7%). The per-row flag you pointed to can express a per-speed verdict; it needed one small extension (below).
- The 1.4 and 1.6 numbers did not move through any of it: 6,772 leaves of the extract (results, lumbosacral, dataset-direct, hip demand) match the previous extract with a worst relative difference of 0; in `ENVELOPE.md` 3 lines were removed (the gait record id twice and the intro sentence) and 38 added, all for 0.5.
- **A correction to memo 21.** I said no row peaks higher at 0.5 than at 1.4. That held for the 95th percentile of the leg rows and the rows above the pelvis. At the **maximum**, 36 of 636 cells of the results section are higher at 0.5 (method B 21, H 11, A_filtered 2, A_native 2), and in the lumbosacral rows 32 cells are, among them rigid lateral torque (maximum 139.2 N m against 112.3 at 1.4; p95 59.2 against 92.7) and a few p95 cells of the first-harmonic quartile corners (angle 12.9 against 7.8 deg, power 20.0 against 13.8 W). The sizing statistic is the p95 and 0.5 is outside it, so nothing is sized on these, but the claim "none" was only true of p95.
- Decisions for you: (1) the 0.5 first-harmonic rows rest on a thin table (15 of 17 subjects, roll gain 1.68 with quartiles 0.69 to 2.14): keep them in the envelope with their label (recommended), or drop them at 0.5? (2) `rm.v1-gait-0p5` now evaluates `done` (its criterion is the record's existence); sign-off is yours. (3) The old record directory `sim/gait/20261019-1251-walk_treadmill/` (truncated GAIT.md, CRLF manifest hash) is untracked and superseded; delete it? (I did not.)
- What would change the conclusion: the BSIP and Stage 2 decisions you are re-verifying moving the snapshot; these outputs are interim (end of memo).

## Findings

1. **The "does the extract carry a per-stride RMS torque per joint" answer: no.** Per joint, method and exclusion set it holds the 95th percentile and maximum of peak torque, peak speed, positive power and regeneration (`JOINT_METRICS`); the lumbosacral rows hold peak angle, torque, speed, power and regeneration as median, p95 and maximum. The only RMS in it is the agreement's `rms_pct_ptp` (the RMS of the moment difference as a percentage of the dataset's peak-to-peak, pooled over limbs), and the RMS in N m I quoted in memo 21 came from my recomputation, not from the extract. I added nothing.
2. **Maxima and the lumbosacral rows at 0.5** (correction above). Full list is reproducible from `sim/benchmarks/gait_extract.json`; the p95 exceedances are all in lumbosacral first-harmonic corners (5 cells).
3. **The first-harmonic table at 0.5 is the weakest number in the set.** Same command, 15 of 17 subjects (the default `--min-quality 0` drops two with a negative accelerometer alignment correlation; worst 0.06 / -0.20 / -0.15 on the pelvis axes at 0.5, against worst 0.64 / 0.95 / 0.10 at 1.4 and 1.6), and the alignment was fitted on the 0.5 strides only (at 1.4 and 1.6 both speeds are pooled). Roll: pelvis amplitude 1.7 deg, trunk 2.7 deg, gain 1.68 [0.69, 2.14], lag -24 [-118, 84] deg. Yaw is tighter: 1.25 [1.01, 1.40], 29 [21, 52] deg. Added as measured; no other change in the trunk-mode area.
4. **Method A_native, B and H at 0.5**, from the shared band table (corr / RMS %): A_native hip 0.84 / 19, knee 0.89 / 20, ankle 0.98 / 9; B hip 0.45 / 129, knee 0.07 / 144, ankle -0.04 / 53; H hip 0.64 / 57, knee 0.62 / 36, ankle 0.97 / 9. A_native also misses the band at 0.5 (it already missed it at 1.4 for the hip, 0.83 / 17).
5. **The record `gait.20261019-1424-walk_treadmill` says `git_dirty` true** with a `diff_sha256`: I was editing `runs_report.py` and tests while it ran. The pipeline code it ran (`gait.py`, `retarget.py`, `ingest_camargo.py`) was committed (`e231760`); the dirty diff is the envelope work in progress. Its results equal the earlier run's (`1251`, CRLF manifest) in every value: results, sensitivity, subjects, trunk, assumptions.
6. **The pre-commit hook staged `roadmap/state.json` and `roadmap/STATUS.md` into the T4 commit** (it rebuilt them because the leaf `rm.v1-gait-0p5` turned `done`; frontier 26 to 25). My commit message does not list them. Not a defect, but my `git diff --cached --stat` before committing did not show them.
7. **`git status` keeps listing `data/camargo2021/manifest.json` as modified with no content difference** (`git diff` is empty, `git hash-object` equals HEAD's blob). It is a stat-cache artefact after the file was rewritten with LF; `git update-index --refresh` would clear it. I did not run it.

## D4: manifest with LF (`e642e92`)

- `ingest_camargo.py` opens the manifest with `newline="\n"`. `dataset_manifest_sha256` (12 hex): old 4202e8b94f0f (CRLF, on record `1251`), new **324f3869d89d** (LF; equal to the committed blob and what a clean clone computes). Before the Stage 2f ingest: 0498fb7e4dd3 against a committed blob of 76594c761005. Every earlier gait record carries a CRLF hash.
- Re-ingest: manifest content unchanged (no git diff), all 612 arrays hash identically. Tests (2, red first): no CR in the file on disk; the ingest opens it with an LF newline. Suite 1342 passed, 1 xfailed, 388.67 s.
- Rerun of the three-speed gait run: **25 m 36 s** (earlier 25 m 08 s), 1285 subject-strides, manifest 324f3869d89d. Reproduction check repeated: the 1.4 and 1.6 `results` cells equal the committed extract, 6,248 leaves, worst relative difference 0 (tolerance 1e-6).

## D3: first harmonic (`3a73375`)

- `gait_diag.py trunk-imu --speeds 1.4 1.6` (29 s) reproduced all 24 existing `FIRST_HARMONIC_DEFAULTS` values (roll and yaw, median and both quartiles, gain and lag, two speeds). So it was safe to go on.
- `trunk-imu --speeds 0.5`: roll median (1.68, -24), q1 (0.69, -118), q3 (2.14, 84); yaw median (1.25, 29), q1 (1.01, 21), q3 (1.40, 52). Added as `FIRST_HARMONIC_DEFAULTS["0.5"]` with a comment naming the command and the 15-subject caveat; the command output is in the commit message. Tests (red first): the 0.5 entries, and every `walk_treadmill` speed has an entry. Suite 1343 passed, 1 xfailed, 370.27 s.

## D2: layout (`e231760`) and T3 (`848dff9`)

- `GAIT.md` is now shared: header, assumptions, subjects, the files by speed, a band table for every speed and method with the verdict per exclusion set, the sensitivity runs (**154 lines**). `GAIT-0p5.md`, `GAIT-1p4.md`, `GAIT-1p6.md` hold one speed each (**147 lines** each); cap 399 untouched. `CONVENTIONS` sections 2 and 6 amended in the same commit. The strict xfail became a passing per-file cap test (every rendered file of the newest three-speed record under the cap, no truncation marker), plus a real-data three-speed run that checks the file set, the pointers and the band table. Suite 1344 passed, 389.97 s.
- Extract: `fy gait walk_treadmill --extract-only --workers 6`, **6 m 47 s**; `gait-extract/1` unchanged (the schema takes any speed key). It carries the three speeds, 297 strides at 0.5, and the LF manifest hash.
- Envelope: `runs_report.py` gets `GAIT_ACCEPTANCE_SPEEDS = ("0.5",)`. Every 0.5 row (leg, dataset-direct, ankle inversion, above the pelvis, lumbosacral, and the functional-demand lines) carries `acceptance speed, not for sizing`. **The existing mechanism and where I extended it:** the per-row verdict (`within band` / `outside band`, from the row's own corr and RMS against the band constants) already existed for hip ab/adduction and rotation and is computed per speed, so it can express a per-speed flag. What was missing is that the sagittal rows were entered only when a method met the band as a whole, so at 0.5 the envelope would have printed "no method meets the band: not entered". At an acceptance speed with no method meeting the band, A_filtered's sagittal rows are now listed with that per-row verdict. **At a sizing speed that misses the band nothing changes** (rows still dropped; tested), so this cannot let a failed 1.4 or 1.6 row into the sizing set. The envelope takes no maximum across speeds anywhere (T0.2), so nothing needed excluding.
- Tests (8 added, red first): schema accepts 0.5 without a version bump; 0.5 rows labelled and per-row flagged; every table labelled; the 1.4 and 1.6 rows and everything above the gait section unchanged by the presence of 0.5; the header; mutation (one 0.5 value changed, the text changes); a missing band at a sizing speed still drops its rows; the tracked extract. Suite 1352 passed, 372.63 s.
- Existing worst-case rows: the part of `ENVELOPE.md` above the gait section differs by one line only (the "scenario classes included" line names the new gait id).

## T4: the load case (`28acae9`)

- `thread/records/lc.walk-0p5.yaml`: `proposed`, `independent_source_required: false`, source `walk_treadmill`, condition `0.5 m/s level treadmill walking`. Purpose: "Level walking at 0.5 m/s, v1's acceptance speed and not a sizing speed." Notes: the reasons of the other walking cases (inverse dynamics, ground reaction supplied explicitly, no contact solver), that this is the acceptance speed and not a sizing speed, and that trust here is carried by the band flags on the envelope rows. No verdict and no number; a test checks the notes contain no digit and none of meets, misses, fails, passes, outside, within, correlation.
- `fy thread build`, `fy thread validate`: 24 records, 0 work items, rework 0, errors 0, warnings 0. `fy check`: all PASS but the one confirmed waiver. Tests: the real-store expectations, the wording test, the hook's record count 23 to 24. Suite **1353 passed, 379.65 s** (this is the count `fy state` reports).

## My own mistakes

- The shell turned `\n` inside my heredoc-fed Python strings into real newlines again, three times (two test files and a patch script); each time I saw the syntax error or the failed match, and redid the edit with the editor tool or a file written by it. The first D4 attempt also left a test that matched my own source text weakly; I replaced it with one that finds the write call.
- A fixture bug of mine hid the 0.5 agreement numbers behind a default loop; the test caught it.
- I wrote memo 21's "none" for non-monotonic rows without checking the maxima, and said so in the memo; this memo checks them.

## Questions for Joe

1. Keep the 0.5 first-harmonic lumbosacral rows in the envelope with the acceptance label (recommended: they are labelled and not for sizing), or drop them at 0.5 until the IMU alignment at slow speed is better?
2. Sign off `rm.v1-gait-0p5`? It evaluates `done` on the record's existence; the band failure is carried by the flags, as you decided.
3. Delete the superseded untracked record `sim/gait/20261019-1251-walk_treadmill/`?
4. Should `fy gait` refuse or warn when it runs with a dirty tracked tree? The record stamps it (`git_dirty`, `diff_sha256`) but nothing surfaces it; this run's stamp is dirty for a reason that does not touch the pipeline.

## Interim status

These outputs are interim. They carry snapshot **sha256:e5cc96ceed7e** (model c4d7757d45fe), taken before your BSIP re-verification and the hip stop, pelvis pose, toe joint and trunk-mode decisions. The final regeneration of all three speeds is `rm.v1-stage2-closed`, not this brief. Nothing is stamped as final. The gait records' `gait.json` and the processed arrays stay untracked.
