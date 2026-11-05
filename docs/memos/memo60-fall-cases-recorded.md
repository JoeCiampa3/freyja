STATE: base 05fd86cd94d3 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:adfaf460f660 | snapshot sha256:492fe816e6d8 | tests not run (`fy state --no-run`; full suite run before commit 05fd86c: 2215 passed, 3 failed, 1 error, none from this change) | dirty no at T1 commit

# Memo 60: fall cases recorded (rm.v1-fall-cases-recorded)

Brief: `docs/briefs/ariadne/fall-cases-brief.md` (sha256 prefix `adfaf460f660`, matched). Commit 05fd86c. Checkpoint reached; stopped.

## Decision summary

- **What this means for Freyja:** the thread now holds the seven fall cases, each a zone, a direction, an energy and an accepted decision behind it. `seg.thorax`, `seg.pelvis`, `seg.thigh` and `seg.upper_arm` list their cases, so the segment characterization steps have fall loads to read. No case carries a force, a cap or a stroke.
- **"Sourced" is weak.** It means the cited decision exists and is accepted. It does not mean the number is validated. The knee's 260 J rests on a 0.40 m drop tagged [design]; the arm's 430 J on a friction cone with no source (mu = 1.0). Each record's `notes` says so.
- **Numbers:** build 34 records (27 before), 0 errors, 0 warnings. 7 of 7 cases `sourced`, every entry resolved and admissible. Energies: 540 J (five zones, E_max band 473 to 537 J), 260 J knee (about 360 J at a 0.55 m drop), 430 J arm (band 378 to 422 J forward). 27 existing records byte-identical.
- **Gates:** G1 to G5 all pass (table below).
- **Decisions for Joe:**
  1. Sign off `rm.v1-fall-cases-recorded` (`signed_off: true`) if you accept the gates. I recommend yes.
  2. The brief's test-run waiver was lost for the T1 commit (I edited five existing tests, see finding 1). Four full-suite failures are not from this change (finding 3). I recommend fixing them in separate commits, in this order: `test_state` wording, `test_fall_room` hash, then the Camargo data question.
  3. Whether the arm's evidence should cite the Revisions entry rather than D3 (finding 4). I recommend leaving it as the brief wrote it.
- **What would change the conclusion:** a cited decision losing `accepted` status or a label (the build then errors, mutation-checked), or Joe changing a clause number: a case then moves with the decision (CONVENTIONS section 8).

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G1 clean build | Pass | `fy thread build`: 34 records, 1 work item, rework 0, errors 0, warnings 0 (27 records at baseline) |
| G2 all sourced | Pass | 7 of 7 `sourced`; 12 evidence entries across the seven, all `resolved` and `admissible`, read from `thread/derived/lc.fall-*.json` by `tests/test_fall_cases.py` |
| G3 segments see them | Pass | `seg.thorax` 3, `seg.pelvis` 2, `seg.thigh` 1, `seg.upper_arm` 1, each exactly the set named in the brief; every other segment 0; no other load case has `zone_in` |
| G4 nothing else moved | Pass | no `thread/records/` file other than the seven new ones differs; `work.upper-arm-cad` still `current`; no `unsourced-consumption` warning; changed generated files listed below |
| G5 numbers match clauses | Pass, 7 of 7 | table below |

### G5

| Case | `energy_j` recorded | Number in the cited clause (decision file) | Equal |
|---|---|---|---|
| lc.fall-hip-lateral | 540 | adr-0037 D3 row "hip": `540 J` | yes |
| lc.fall-shoulder-lateral | 540 | D3 row "shoulder": `540 J` | yes |
| lc.fall-buttock-backward | 540 | D3 row "buttock": `540 J` | yes |
| lc.fall-back-backward | 540 | D3 row "back": `540 J` | yes |
| lc.fall-chest-forward | 540 | adr-0044 D1 row "chest": `540 J` | yes |
| lc.fall-knee-forward | 260 | D3 row "knee": `260 J` | yes |
| lc.fall-hand-arm | 430 | adr-0037 Revisions 2026-10-31 (first entry): "The design energy is 430 J"; adr-0008 D5 line 97 table: `430 J`. D3's table cell still reads `320 J`, left as history by that entry | yes, to the Revisions entry |

The five E_max rows also agree with D1(b): upper edge 537 J after the 2026-10-31 Revisions, rounded up to 540 J.

## Changed generated files

All from the new records or from the roadmap node `rm.v1-fall-cases-recorded` having changed after the last build.

- New, 14: `thread/derived/lc.fall-*.json` (7) and `thread/dossiers/lc.fall-*.md` (7). Reason: the new cases.
- Four segments, 8 files: `thread/derived/seg.{thorax,pelvis,thigh,upper_arm}.json` and the same four dossiers. Reason: `fall_cases` now lists the cases. `seg.upper_arm`'s dossier also has reference lines that moved because the roadmap nodes `rm.v1-fall-case-arm-backward` and `rm.v1-fall-cases-recorded` changed after the last build (visible in T0, before any record existed).
- `thread/graph.json` and `thread/STATUS.md`: the new nodes and edges, the record count and the inputs hash. STATUS.md also lists the new cases.
- Nothing else.

## Findings

1. **Waiver lost; five existing tests edited.** The brief expected one new test and no edits to existing tests, but five existing tests encoded "no fall cases exist" or a typed count. All five were necessary for the build to pass with the records:
   - `tests/test_thread_validate.py`: `len(decisions) == 10` was already stale at 11 (baseline failure). It now counts the files in `decisions/`.
   - `tests/test_thread_hook.py`: `Thread: 27 records` now counts `thread/records/*.yaml`.
   - `tests/test_thread_real.py` and `tests/test_thread_evidence.py`: the "all load cases are unflagged and not required" assertions now exclude the energy-defined cases, which `tests/test_fall_cases.py` covers.
   - `tests/test_thread_toe.py` and the fixture test in `tests/test_thread_real.py`: they copy only `thread/records`, so the cases' evidence did not resolve; they now copy `decisions/` too.
   These are coupled to the records, so they are in one commit (rule 10). The full suite ran because of it.
2. **Baseline `fy test --quick` failed at T0** on the stale decision count (above), and the build's generated files were stale against a committed roadmap node. Nothing was committed at T0; Joe cleared the count and approved including the generated files.
3. **Four full-suite failures, none from this change** (2215 passed, 72 skipped, 3 failed, 1 error, 58m12s):
   - `tests/test_foot_split.py::test_with_the_old_box_...a_filtered_reference_is_reproduced` and the error in `tests/test_retarget.py::test_held_joints_stay_at_the_standing_pose`: `data/camargo2021/processed/AB06.npz` does not exist on this machine. The processed arrays are gitignored (CONVENTIONS section 2), so this is an environment gap, not a code fault. Not touched.
   - `tests/test_state.py::test_the_documented_suite_time_matches_claude_md`: it looks for "full suite (about 18 minutes" in CLAUDE.md, which now says about 54 minutes. Memo 59 finding 12 already flagged the stale text; `tools/state` still has the old figure. I did not edit `CLAUDE.md` or `tools/state`.
   - `tests/test_fall_room.py::test_g3_the_committed_output_is_a_fresh_build`: `data/falls/room.json` inputs hash `bbc78518b5f3` against a fresh build's `d4e6ad415fb6`. Its inputs include `decisions/0037-fall-design-basis.md`, which was amended on 2026-11-01 after memo 59's build. This change touches no input of it. The numbers in `room.json` are not shown to be wrong; the file is stale against the decision's text. Regenerating it is the fix, and it is outside this brief. I did not run the baseline commit to confirm the four failures there; I read each cause from its assertion.
4. **Arm evidence cites D3, which still says 320 J.** The brief's table gives `adr-0037 D3; adr-0008 D5`. D3's table cell still reads 320 J (history), and the 430 J is in the Revisions entry and adr-0008 D5. The label resolves, so "sourced" holds, but a reader following D3 alone finds 320 J. I followed the brief. The record's `notes` states 430 J and its basis.
5. **Hip notes carry S1 and S11 as calibration**, as the brief requires, outside `evidence`. No Unverified row and no adr-0036 citation appears anywhere in the records.

## Timings

- `fy thread build`: 1.4 s.
- `fy test --quick`: 532 s at baseline (1075 passed, 1 failed); 256 s and 392 s on the two later runs (1076 passed on the last; the 392 s run had 4 errors in the toe fixture before I fixed my `decisions/` copy).
- `tests/test_fall_cases.py`: 0.4 s.
- Full suite: 58 min 12 s (3491.59 s).

## Tolerances and choices

No tolerance was chosen or changed. The records' `energy_j` values are typed from the decisions, as the brief says. Test choice: `tests/test_fall_cases.py` asserts no energy, per the brief; it reads the derived JSON for sourcing and the real build for the segment sets.

## My mistakes

- I stashed the working tree once to compare against the baseline, then popped it at once. Nothing was lost (37 files restored), but it was not needed and the baseline comparison I wanted was skipped.
- My first edit to `test_thread_evidence.py` was a garbled expression, replaced before any run.
- The first `decisions/` copy in `test_thread_toe.py` collided with an existing `mkdir()` and made four tests error; fixed by `exist_ok`.

## Questions for Joe

1. Sign off `rm.v1-fall-cases-recorded`?
2. Regenerate `data/falls/room.json` and fix the `CLAUDE.md` and `tools/state` suite-time text, as separate tasks?
3. Is the Camargo processed data meant to exist on this machine? Two full-suite tests depend on it.
