# Memo 21: Stage 2f, level walking at 0.5 m/s (T0 to T2 done; stopped on a band failure)

STATE: base 3dbd9bc00df6 | brief architecture sha256:2ecf3ee5c019, ariadne sha256:1ac4d746673a | snapshot sha256:e5cc96ceed7e | tests 1340/1340 | dirty yes

## Decision summary

- **A_filtered fails the agreement band at 0.5 m/s, on the hip and the knee.** The brief says to stop on that, so I did. T3 (extract, envelope) and T4 (`lc.walk-0p5`) are not built. T0, T1 and T2 are done and committed (`4945491`, `3dbd9bc`).
- The numbers that matter (A_filtered, both limbs pooled, all subjects; band is corr >= 0.90 and RMS <= 15% of the dataset's peak-to-peak):

  | | 0.5 m/s | 1.4 m/s | 1.6 m/s |
  |---|---|---|---|
  | hip corr / RMS % | 0.861 / 20.1 | 0.915 / 14.2 | 0.927 / 13.2 |
  | knee corr / RMS % | 0.892 / 20.2 | 0.927 / 13.3 | 0.932 / 12.8 |
  | ankle corr / RMS % | 0.975 / 8.7 | 0.980 / 7.8 | 0.975 / 8.4 |
  | hip RMS in N m (of peak-to-peak) | 6.3 (33.7) | 13.6 (95.6) | 15.3 (116.0) |

- Your guess was half right: the absolute error is small and falls with speed (hip 6.3 N m against 13.6), so the percentage is inflated by the small moments. But the correlation also misses (0.861, 0.892 against 0.90), and that is not a normalisation effect. The hip and knee fail in all three exclusion sets (all, without offset subjects, without pitch-flagged).
- Data: 297 strides from all 17 subjects at 0.5 m/s (469 at 1.4, 519 at 1.6). Your availability thresholds (half the subjects, 100 strides) are cleared by a wide margin; I think they are fine.
- The 1.4 and 1.6 numbers did not move: 425 of 425 earlier arrays hash identically, and 6,248 result leaves at 1.4 and 1.6 reproduce the tracked extract with a worst relative difference of 0 (tolerance 1e-6).
- **No joint row peaks higher at 0.5 than at 1.4**: 0 of 36 A_filtered/rigid rows (torque, speed, positive power for 12 leg joints), and 0 of 30 B rows above the pelvis (5 joints x 3 metrics x 2 trunk modes). The highest 0.5/1.4 ratio is 0.84 (hip ab/adduction torque). Median ratios: torque 0.59, speed 0.61, power 0.26. So 0.5 m/s does not set any sizing row.
- Decisions for you:
  1. What a failed band means for `rm.v1-gait-0p5`. **Recommended:** create `lc.walk-0p5` anyway, as `proposed`, with the failed hip and knee band stated in its notes, and show the 0.5 sagittal rows in the envelope flagged "outside band, not for sizing", the treatment hip ab/adduction and rotation already get. 0.5 enters no sizing statistic, so nothing is sized on a row that missed. This needs a brief amendment, because T4 conditions the record on the band.
  2. GAIT.md for three speeds renders to 543 lines against a cap of 399. **Recommended:** keep the cap, split the file (GAIT.md with the header, subjects, a band table across speeds and the sensitivity section; one GAIT-<speed>.md per speed, each under the cap), and amend CONVENTIONS section 6 in the same commit.
  3. The `first_harmonic` trunk rows need a 0.5 m/s entry that does not exist (finding 3). **Recommended:** add one from the existing script (`gait_diag.py trunk-imu --speeds 0.5`), no tuning, one separate commit.
- What would change the conclusion: a different pitch or offset subject treatment at 0.5 (the three sets differ by at most 1.8 points of RMS and 0.026 of correlation at the hip and knee, so unlikely to flip either), or the BSIP and Stage 2 decisions you are re-verifying moving the snapshot (these outputs are interim, see the end).

## Findings

1. **Band failure at 0.5 m/s** (above). Full table below. I did not adjust the band, the cutoff or any subject list.
2. **GAIT.md overflows the cap.** The renderer writes 543 lines untruncated; the cap is `gait.MAX_LINES` = 399. The section sizes are 8 (subjects) + 138 per speed x 3 + 104 (sensitivity) + header. The file the run wrote is cut inside the 1.6 section and the sensitivity section is lost, with a "(truncated at 399 lines)" last line. I did not commit that file, and I did not raise the cap. The three-speed record is `sim/gait/20261019-1251-walk_treadmill/` (untracked, as today). A strict xfail test (`test_the_line_cap_is_not_what_hides_a_speed`) holds this on any machine with that record and fails loudly once the layout fits, so the marker gets removed.
3. **`retarget.FIRST_HARMONIC_DEFAULTS` is keyed by speed and has only "1.4" and "1.6".** `gait_extract._variant_kwargs` indexes it by speed, so `fy gait walk_treadmill --write-extract` raises KeyError at "0.5" in the lumbosacral rows. The table holds measured T3c.2 medians and quartiles from `gait_diag.py trunk-imu`. The brief's list of places did not name it; it blocks T3 regardless of the band. `gait_diag.py harmonic` prints from the same table. I have not measured or added a 0.5 entry, because it is a new measured constant in the trunk-mode area the brief puts out of scope.
4. **The stride-duration range does almost nothing at 0.5, and no acceptance filter has ever rejected a stride.** The manifest's rejection counts are empty for every subject at every speed, 1.4 and 1.6 included. The per-speed range I set rejects 0 of 297 at 0.5 (see T1). The old range would have rejected 99 (33%), all too long. So the range is a guard against a future mis-segmentation, and nothing tests its sensitivity.
5. **The manifest hash depends on the machine's line endings (pre-existing, not fixed).** `ingest_camargo.py` writes the manifest with `Path.write_text`, which on Windows writes CRLF. The committed blob is LF (`.gitattributes` has `eol=lf`). `gait.py` hashes the on-disk bytes (`dataset_manifest_sha256`). Before this work the disk file hashed to 0498fb7e4dd3 (the value in STATE and every gait record) and its committed blob to 7659...; now disk 4202e8b94f0f and committed blob 324f3869d89d. A clean clone therefore computes a different manifest hash than this machine records. Fixing it (write with `newline="\n"`) changes the hash recorded by every future run, so I left it for you.

## T0: baseline and inventory

- Baseline `fy test`: 1332 passed in 360.64 s (6 m 01 s wall). Snapshot e5cc96ceed7e, model c4d7757d45fe, manifest 0498fb7e4dd3 (before), all unchanged through the session (checked before each commit and at the end).
- Raw data reachable (`camargo_raw_dir`). Probe (read-only, existing ingestion with only 0.5 in the speed list and the duration range opened to 0..100 s): 297 strides, 17 of 17 subjects (15 to 20 each, one trial per subject), no rejections. Thresholds: half the 17 subjects is 9 (17 contribute), 100 strides (297). Strides at 1.4 and 1.6: 469 and 519, 17 subjects each.
- Stride durations at 0.5 m/s: min 1.285, p5 1.353, median 1.552, mean 1.551, p95 1.760, max 1.971 s. The 1.4 to 1.6 range [0.7, 1.6] would reject 99 of 297 (all above 1.6 s).

Everything that assumes the speed set (file, what, change needed, what I did):

| File | Assumes | Needed | Done |
|---|---|---|---|
| `data/camargo2021/ingest_spec.yaml` | `speeds_mps: [1.4, 1.6]`; `stride_s: [0.7, 1.6]` for all | add 0.5; per-speed range | yes (T1) |
| `analysis/ingest_camargo.py` | one `stride_s` pair | `stride_range(spec, speed)`, `range_around`, `relative_half_width` | yes (T1) |
| `sim/scenarios/gait/walk_treadmill.yaml` | `speeds_mps: [1.4, 1.6]` | add 0.5 | yes (T2) |
| `sim/scenarios/gait/camargo_mapping.yaml` | no speed or stride-duration range (T0 expected one here) | none | n/a |
| `sim/scripts/gait.py` | generic: loops over the spec's speeds, `str(speed)` keys, results sorted so "0.5" < "1.4" < "1.6" | none; `MAX_LINES` = 399 overflows | finding 2 |
| `sim/scripts/gait_extract.py` | generic over `rec["spec"]["speeds_mps"]`, except `FIRST_HARMONIC_DEFAULTS[speed]` | a 0.5 table entry | finding 3, not done |
| `sim/scripts/retarget.py` (lines 61 to 66) | `FIRST_HARMONIC_DEFAULTS` for "1.4", "1.6" | add "0.5" | finding 3, not done |
| `docs/schemas/gait-extract-1.schema.json` | `results` and the other speed maps take any key (`additionalProperties`), `spec.speeds_mps` is an array of numbers | none, stays `/1` | not touched |
| `sim/scripts/runs_report.py` | `gait_section` is per speed: `speeds = sorted(rec["results"], key=float)`; **no maximum across speeds exists**, so nothing needs to exclude 0.5 from a statistic. The header says "at 0.5 and 1.4 and 1.6 m/s" (wording to fix), and `_entering` omits all sagittal rows at a speed where the method's band is not met | label 0.5 as the acceptance speed; decide the outside-band treatment | not done (T3) |
| `sim/scripts/gait_diag.py`, `gait_force_report.py`, `retarget_report.py`, `knee_gain.py`, `ankle_gain.py`, `foot_pitch.py` | diagnostics with defaults `["1.4","1.6"]` or a fixed "1.4" | none: standalone, outside the pipeline; `ankle_gain.py` re-runs the ingestion's stride selection and now also does 0.5 (harmless) | left |
| tests | `test_camargo_ingest.py` (`SPEC["stride_s"]` pair, `0.9 < mean < 1.25` for every speed); `test_gait_extract.py:28,243` (`SPEEDS = ("1.4","1.6")`, 469 and 519 strides of the tracked extract); `test_runs_report.py` (fixtures at 1.4 and 1.6); `test_retarget.py:513` (the defaults at two speeds) | the ingestion tests changed in T1; the others describe the tracked extract or fixtures and stay true until T3 | T1 only |

## T1: ingest

- `speeds_mps: [0.5, 1.4, 1.6]`; `stride_s` keyed by speed. 1.4 and 1.6: [0.7, 1.6], unchanged. **0.5: [0.945, 2.159]**, the one tolerance I set: the relative half-width (1.6 - 0.7) / (1.6 + 0.7) = 0.391 around the pooled median 1.552 s (1.552 x (1 -/+ 0.391) = 0.9447 and 2.1593, rounded to three places). It rejects 0 below and 0 above out of 297 (shortest 1.285 s, longest 1.971 s). I set it by the brief's formula, not by looking at which strides it would drop.
- Ingest run: 27.4 s for all 17 subjects. Per-subject strides at 0.5: AB06 17, AB07 17, AB08 18, AB09 15, AB10 18, AB11 19, AB12 17, AB13 19, AB14 17, AB15 18, AB16 17, AB17 19, AB18 17, AB19 17, AB20 20, AB21 16, AB23 16.
- **1.4 and 1.6 byte-identical:** every array of every subject's npz hashed (dtype, shape, bytes) before and after: 425 of 425 identical, 187 new keys (17 subjects x 11 arrays, all prefixed `0.5_`). The manifest differs only in `spec_sha256`, 102 new trial files in `files_sha256` (17 trials x 6 sensors) and the new 0.5 entries; every existing entry is identical.
- Tests (red first: 6 failed, 21 passed): `steady_segments` at 0.5 on a synthetic trace; the per-speed range and that 1.4 and 1.6 keep the old one; `range_around` keeps the relative half-width; the 0.5 range is the formula around 1.552; the pooled median of the real 0.5 durations is 1.552; per-speed mean-duration asserts (0.5: 1.3 to 1.9 s, my choice from adult walking at ~0.8 m stride, not tuned; 1.4 and 1.6 keep 0.9 to 1.25) and 1.6 < 1.4 < 0.5; adding a speed leaves the other speeds byte-identical. Suite: 1338 passed, 340.50 s.

## T2: gait run

- Spec: only `speeds_mps` changed; a test pins the rest (methods, trunk modes, cutoff, offset and pitch-flag lists, sensitivity settings, band constants).
- `fy gait walk_treadmill --workers 6`: **25 m 08 s**, 1285 subject-strides (297 + 469 + 519), record `gait.20261019-1251-walk_treadmill` (untracked), snapshot e5cc96ceed7e, model c4d7757d45fe, dataset manifest 4202e8b94f0f (CRLF on this machine, finding 5), spec 0aff4e7cdffc, `git_dirty` true (the spec edit was uncommitted when it ran).
- **Reproduction:** the `results` section of the new record at 1.4 and 1.6 against `sim/benchmarks/gait_extract.json`: 6,248 leaves, worst relative difference 0, none beyond 1e-6 (`check.sim.walk_reference`'s tolerance). The other extract sections (lumbosacral, dataset-direct, hip demand) could not be regenerated (finding 3); they are computed from the processed arrays and the model, which are unchanged for 1.4 and 1.6, but I have not shown it.
- **Band, A_filtered, per sagittal joint** (`gait.BAND_STEMS`), corr / RMS % of peak-to-peak / RMS in N m (mean peak-to-peak in N m). The N m figures are my recomputation: per stride, RMS of (A's moment per kg minus the dataset's per kg) times Freyja's mass 65 kg, mean over strides and both limbs; it reproduces the record's corr and RMS % to 2e-6 and 2e-5, so it is the same quantity.

  | set | m/s | hip_fe | knee | ankle_pdflex |
  |---|---|---|---|---|
  | all | 0.5 | 0.861 / 20.1 / 6.25 (33.7) **fails** | 0.892 / 20.2 / 6.03 (32.3) **fails** | 0.975 / 8.7 / 6.94 (81.6) meets |
  | all | 1.4 | 0.915 / 14.2 / 13.56 (95.6) | 0.927 / 13.3 / 9.99 (76.7) | 0.980 / 7.8 / 8.98 (116.7) |
  | all | 1.6 | 0.927 / 13.2 / 15.28 (116.0) | 0.932 / 12.8 / 11.27 (90.0) | 0.975 / 8.4 / 9.80 (119.5) |
  | without offset | 0.5 | 0.874 / 19.2 / 6.32 (35.3) **fails** | 0.882 / 20.9 / 6.09 (31.6) **fails** | 0.977 / 8.5 / 6.92 (82.4) meets |
  | without pitch-flagged | 0.5 | 0.854 / 20.5 / 6.18 (33.1) **fails** | 0.908 / 19.1 / 5.80 (33.3) **fails** (RMS) | 0.975 / 8.8 / 6.87 (80.4) meets |

  At 1.4 and 1.6 the other two sets are in the same record and all meet. At 1.4 the hip's RMS (14.2%) is 0.8 points inside the band, so the band was already close at the hip; the 0.5 failure is a move of 6 points, not a knife edge. Method B, H and A_native at 0.5: not examined, they already failed the band at 1.4 and 1.6.
- **Non-monotonic rows (A_filtered, rigid, 95th percentile across subject-strides): none.** 12 leg joints x torque, speed and positive power = 36 rows, 0 with the 0.5 value above the 1.4 value. Ratios 0.5/1.4: torque 0.47 to 0.84 (median 0.59), speed 0.54 to 0.78 (0.61), positive power 0.18 to 0.51 (0.26). Largest: hip_aa_right torque 73.4 against 87.8 N m (0.84), hip_aa_left 72.3 against 88.8, ankle_pdflex_right torque 98.0 against 124.8 (0.79). Sagittal torque p95 at 0.5 / 1.4 / 1.6 (right side): hip 47.7 / 68.3 / 75.4, knee 46.1 / 87.0 / 109.0, ankle 98.0 / 124.8 / 132.7 N m. Method B above the pelvis: 5 joints x 3 metrics x 2 trunk modes = 30 rows, 0 higher at 0.5. The expectation that slow gait could peak higher did not materialise at p95; I did not check the maxima or the lumbosacral first-harmonic rows.
- Tests added (3, in `tests/test_gait.py`; red first for the spec test): the spec pin; a real-data record at 0.5 and 1.4 (finite, speed-ordered, under the cap); the strict xfail for the cap. Runtime of the two real-data tests, 22 s. Suite: 1340 passed, 1 xfailed, 363.66 s.

## Not done, and why

- **T3** (extract, `ENVELOPE.md`): stopped on the band failure (rule: report and stop). It is also blocked by finding 3, and the envelope would need your rule for a speed whose band is not met (the current code would print "no method meets the band at 0.5 m/s: the sagittal rows are not entered", which does not serve the acceptance-speed purpose of the brief). The schema needs no change (it takes any speed key).
- **T4** (`lc.walk-0p5`): the brief conditions it on the band. Not created.

## My own mistakes

- Two of my new tests were wrong first time: an `array_equal` that treated the force plates' NaN as unequal, and a record assertion that used the extract's `subjects.count` key and a manifest stride count where the record holds run rows. Both fixed before commit; no ingestion or pipeline behaviour was involved.
- A probe script I wrote printed the whole `sim/local_config.json` once (including the credential file path, not a key). Nothing was written anywhere; I mention it because it is a file you said only you edit.
- My first band script lacked a `__main__` guard and crashed the Windows process pool; nothing was written.

## Questions for Joe

1. Band at 0.5: create `lc.walk-0p5` anyway with the failure stated, and flag the 0.5 sagittal envelope rows "outside band"? Recommended: yes (decision summary). Alternative: leave the leaf open and take the 0.5 loads from the dataset-direct column only.
2. GAIT.md: split per speed (recommended) or raise the cap to about 560?
3. Add a 0.5 entry to `FIRST_HARMONIC_DEFAULTS` from `gait_diag.py trunk-imu --speeds 0.5` (recommended), or drop the first-harmonic rows at 0.5?
4. Write the manifest with LF (finding 5)? It changes the manifest hash recorded from now on.

## Interim status

These outputs are interim. The snapshot they carry is **sha256:e5cc96ceed7e** (model c4d7757d45fe), taken before your BSIP re-verification and the hip stop, pelvis pose, toe joint and trunk-mode decisions. The final regeneration of all three speeds is `rm.v1-stage2-closed`, not this brief. Nothing is stamped as final. The new record and its truncated GAIT.md are untracked; the processed arrays stay untracked.
