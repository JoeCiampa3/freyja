STATE: base 9efaa3d428a5 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2033/2036 | dirty yes (this task's files, uncommitted when generated)

# Memo 48: the baseline rerun is a finding, not a commit; STATE.md no longer truncates

## Decision summary

- **I ran the baseline write and did not commit it.** `walk_reference.json` written from `gait.20261028-1654-walk_treadmill` (model `1ceee2452e18`, `git_dirty` false) baselines no method: `baselined_methods` is `[]` (the committed one has `['A_filtered']`). With that file in place `check.sim.walk_reference` goes from SKIP (baseline superseded) to **FAIL**: "288 metrics differ ... missing in baseline". I restored the committed file; the new one is in my scratch area, not in the repo. Per CLAUDE.md rule 4 I report the number and stop.
- **Why nothing is baselined:** `baseline_methods` baselines a method only if it meets the band (corr >= 0.9, RMS <= 15% of peak-to-peak) at every speed and trunk mode. The spec now carries 0.5 m/s (v1's acceptance speed, added at 2f), and A_filtered misses the band there: hip_fe corr 0.853, RMS 20.5%; knee 0.889, 20.9%. At 1.4 and 1.6 m/s it meets it: hip_fe 0.915 / 14.7% and 0.927 / 13.6%; knee 0.921 / 14.3% and 0.925 / 13.8%; ankle_pdflex 0.976 / 8.5% and 0.970 / 9.3%. The committed baseline predates 0.5 m/s (its speeds are 1.4 and 1.6), so it is not comparable with a three-speed run. `ENVELOPE.md` already marks the 0.5 rows "outside band".
- **Not a model effect:** memo 47 showed the model hash change moved no load. The committed baseline file is from a different gait design and snapshot (`e5cc96ceed7e`; speeds 1.4 and 1.6 only), so it is not a before/after of this rerun. Of its 111 differing fields, 6 are provenance and 105 are verdict numbers, among them the whole new 0.5 m/s block and small moves at 1.4 m/s (for example A_native knee corr 0.909 to 0.901, which flips that cell from meeting the band to missing it).
- **Decision for Joe (recommend C):**
  - A. Leave the committed baseline. The check stays SKIP, "superseded by a design change", and has no regression reference for the current gait.
  - B. Commit what the tool wrote. The check FAILs (advisory) and the file baselines nothing. Not recommended.
  - **C.** Change the rule so a method is baselined when it meets the band at the sizing speeds (1.4 and 1.6) only, leaving the 0.5 acceptance rows as findings, as `ENVELOPE.md` already does; then write the baseline. This is a rule change (the band itself is not touched or widened), so it needs your approval; I have not made it. It would baseline A_filtered at 1.4 and 1.6 (I have not run it).
- **STATE.md cap (your approval of my recommendation):** done. `docs/STATE.md` lists the newest 5 memos by number and counts the older ones; the briefs list is complete. It is 86 lines, not truncated (it was cut at 119 before). Two tests added, seen failing first.
- **What would change the conclusion:** if you want the 0.5 m/s rows inside the baseline requirement, option A or B is the honest state; C is wrong.

## STATE.md

`tools/state` `_memo_lines`: newest `MEMOS_LISTED = 5` memos sorted by memo number (not alphabetically: memo10 follows memo9), then "(N older memos not listed)". Tests: the newest-five ordering and the count, and the real tree's generated file contains no "(truncated at". The 119-line cap and its test are unchanged.

## Mistakes and caveats

- To get the baseline from an existing record without an hour-long run I called `gait.write_baseline` on the newest record, which is exactly what `--write-baseline` does at the end of a run; no input was changed. The command-line flag would have rerun the gait first.
- `check.sim.walk_reference` FAIL is advisory, so it did not break the suite; I did not run the suite with the new file.

## Questions for Joe

1. Baseline: A, B or C?

## Tests

Between changes: `tests/test_state.py` 24 passed. Full suite, once, through `fy state`: 2033 passed, 0 failed, 3 skipped.
