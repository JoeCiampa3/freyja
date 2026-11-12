STATE: base ff7563bf5672 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:adfaf460f660 | snapshot sha256:492fe816e6d8 | tests 2330/2333 | dirty no (2305 run and passed, 25 not run again on unchanged inputs, 3 skipped, 0 failed; reported by `fy state` from the full run on this tree, key 6b4aa3b91763)

# Memo 61: repo review fixes, and the test suite from 54 minutes to 8

No brief. Joe asked in chat on 2026-11-11 for a review of the repo, accepted its recommendations and said to fix what could be fixed. Commits 683c877, 91597b6, 8b822f7, ff7563b, then this memo. Nothing was pushed.

## Decision summary

- **What this means for Freyja:** nothing about the robot changed. The full test suite, which had grown to 54 minutes and was being waived at checkpoints (memos 59 and 60 both read "tests not run"), now takes about 8 minutes, so it can gate every commit again. Main is green: the three failures that stood at ed8293d are fixed.
- **Full suite: 488 s**, against 3250 s at memo 58. This is on 6 logical CPUs in parallel with the 25 slowest test cases skipped because their inputs are unchanged. When those 25 run: 2870 s, measured once with another job on the machine.
- **Quick suite: 174 s**, against 320 s at memo 57.
- **Suite result: 2305 passed, 25 skipped on unchanged inputs, 3 skipped, 0 failed.** Serial baseline at ed8293d: 2270 passed, 3 failed, 18 skipped. No test passed serially and failed in parallel, over four parallel full runs.
- **`fy state` at a checkpoint: 8 s when the tree is unchanged since the last full run**, against 3257 s at memo 58. `fy state --help` no longer runs the suite.
- **Git store: 68 MB**, against 1.7 GB. 1.0 GB was eleven orphaned temporary objects from 2026-10-09.
- **Session-start reading did not get shorter.** CONVENTIONS.md went from 51.5 to 49.3 KB, but CLAUDE.md and OVERVIEW.md each grew by corrections, so the total moved by under 1 KB. A real cut means restructuring CONVENTIONS.md, which I did not do.
- **Decisions for Joe:**
  1. Find where commits are made without the pre-commit hook and install it there (finding 1). Recommended: yes, and make the GitHub workflow fail, not warn, on stale generated files.
  2. Split `tests/test_gait.py` into three files (finding 4). Recommended: yes. It alone now sets the 8-minute floor, and the 16-core machine will not get under it otherwise.
  3. Check whether the GitHub repo is public (finding 3). If it is, the literature PDFs in its history need removing, which is a history rewrite and a force-push. Recommended: check now.
  4. Drop the line numbers from the dossiers' references (finding 2). Recommended: yes, cite the file only.
  5. Run `fy state --rerun` on a schedule, to catch a test whose input list is incomplete. Recommended: weekly, or nightly on the new machine.
  6. Four small ones I left alone (finding 9). Each has a recommendation there.
- **What would change the conclusion:** a marked test reading a file outside its input list. It would keep reporting an old pass after that file changed. The lists are whole directories to make this unlikely, and decision 5 is the check. A race between parallel tests that four runs did not happen to hit would also change it.

## What was done

| Commit | What |
|---|---|
| 683c877 | Thread and roadmap generated files rebuilt (stale since ed8293d). 15 files |
| 91597b6 | `tools/testkit/`, parallel `fy test`, the `inputs` marker on 25 slow cases, `fy state` argument guard and reuse, pytest-xdist 3.8.0 and execnet 2.1.2 in `requirements.txt`, the CONVENTIONS row and section 7 paragraph. 18 files |
| 8b822f7 | `data/falls/room.json` regenerated. One line: the inputs hash |
| ff7563b | CLAUDE.md, CONVENTIONS.md, OVERVIEW.md, README.md corrected; `tools/envelope/README.md` and `data/envelope/README.md` written from two CONVENTIONS table cells; a duplicate `.gitattributes` line removed. 7 files |

Outside git: `git gc --prune=now` (Joe approved). `pytest-xdist` installed into `.venv`.

## Findings

1. **Commits reach main without the hook.** At ed8293d the roadmap's generated files still showed 188 nodes with `rm.v1-fall-cases-recorded` on the frontier (a fresh build: 189 nodes, done 24, frontier 25), and 13 thread files did not match a fresh build. This clone has `core.hooksPath` set, so those commits were made somewhere else or through a client that skips hooks. Memo 60 finding 2 saw the same thing at its start. The GitHub workflow reports this as a warning annotation, which nobody reads.
2. **Dossiers cite files by line number, so unrelated edits make them stale.** ed8293d added one line (`signed_off: true`) to a roadmap node file. Every dossier reference to that file moved down one line: eleven dossiers, `STATUS.md` and `graph.json` changed, with no record, number or status different. Any memo, note or node edit that shifts lines above a citation does this.
3. **Literature PDFs are in the pushed history.** `data/literature` was untracked on 2026-10-30 but four commits on `origin/main` still hold about 66 MB of it, including Grood and Suntay 1983 and the ANSUR II report. `gh` is not installed here, so I could not read the repo's visibility.
4. **One module now sets the suite's floor.** With one file per worker, the wall time is the longest file. `tests/test_gait.py` took about 500 s serially in the baseline; the parallel runs finish at 488 to 493 s. More cores will not shorten that.
5. **Tests that depend on gitignored files cannot be skipped on unchanged inputs.** The input key covers only files git tracks or would track. That excludes the gait tests (processed Camargo arrays) and the tests that read the envelope's voxel cache: `test_envelope_foreign` 158 s, one `test_envelope_occupancy_cli` case 115 s, `test_envelope_reserve` about 200 s. Recording the processed arrays' hashes in the tracked manifest and verifying them at load would make the gait tests eligible.
6. **A reused `fy state` result has not seen one thing.** `docs/memos/` is outside the tree key, because the memo is written after the run it reports. A memo that cites a record id changes dossier line references at the next thread build. The hook rebuilds them in the memo's commit and that commit's quick suite covers the thread tests. CONVENTIONS section 7 says this.
7. **Main was red at ed8293d: three failures, all fixed.** `test_fall_room` (stale `room.json`, as memo 60 predicted, new hash d4e6ad415fb6), `test_state::test_the_documented_suite_time_matches_claude_md` (a test that pinned prose; removed), `test_thread_real` (finding 1). The two Camargo failures in memo 60 do not occur on this machine: the processed arrays are here.
8. **The baseline's wall time is unusable.** The machine slept during it (one test reads 7344 s). Its pass and fail list and its ranking of slow tests are sound; the "3250 s" reference is memo 58's.
9. **Left alone, for Joe:**
   - `sim/archive/` is gitignored but nine parameter CSVs from before the snapshot are tracked there. Recommended: untrack them; history keeps them.
   - README says v1 defers "unlocked spine during gait"; `roadmap/README.md` says the lumbosacral joint is unlocked and actuated in gait (confirmed 2026-10-17). Recommended: align README to the roadmap if that decision still stands.
   - CLAUDE.md's architecture brief line names `volume-extractor-brief14.md`, a five-minute docs brief; briefs 15 to 18 came after it. Recommended: point it at the brief you consider current.
   - Twenty tracked README files are empty.
10. **Not built: an open-items list.** The review suggested generating open findings into `docs/STATE.md` under the unused `oi-NNN` identifier, so that a finding like the stale timings (reported in memos 56 to 60) cannot sit unactioned. It needs a format decision first. CLAUDE.md now lets Code fix the two things that kept recurring (brief lines and timings).
11. **On the 32-thread machine, watch memory.** `fy test` uses `-n auto`, one worker per logical CPU. I did not measure memory per worker. If it swaps, `fy test -n 16`.

## How the two reuse mechanisms decide

- **Skip on unchanged inputs.** A test marked `@pytest.mark.inputs(...)` is keyed on the sha256 of every file under its listed paths, its own file, `requirements.txt`, `pytest.ini`, both conftests, `tools/testkit/` and the Python version. Same key as its last pass: skipped, with the key in the reason. A failure is never skipped and erases the stored pass. Lists are in `tests/input_sets.py`: `ENVELOPE` (11 directories) and `SIM` (3).
- **`fy state` reuse.** The tree key is the sha256 of every file git tracks or would track, less `docs/STATE.md` and `docs/memos/`. A full run writes its counts beside that key only if the key is the same before and after the run. `fy state` reports that record while the key still matches, and the Tests section says it did.
- Both records are in `.fy-cache/`, gitignored and per clone. Neither uses time.

## Choices I made, and why

No numeric tolerance was chosen. These are the judgment calls.

- **`--dist loadfile`**, not the default: module-scoped fixtures build whole bodies (one takes 440 s) and the default would rebuild them on every worker.
- **Parallel only when `fy` picks the files** (whole suite or `--quick`). A named file runs serially, because worker start-up costs more than a single file saves.
- **Skips on unchanged inputs count as passed in the STATE line**, with the count shown in the Tests section. They passed on byte-identical inputs. Counting them as skipped would make 2305/2333 look like a regression from 2256/2259.
- **Only the 25 `slow` cases are marked.** Heavier unmarked tests exist (finding 5) but read gitignored files, which the marker's own rule forbids.
- **Input lists are whole directories**, wider than any test needs. Soundness over hit rate.
- **The four tooling changes are one commit** (rule 10): `tools/state` and `tools/fy` import `tools/testkit` and the conftests register it.

## My mistakes

- **I told Joe in chat that the 13 stale thread files differed "in the banner only, no content change". Wrong.** The reference line numbers had moved. My check filtered diff lines with a pattern that dropped Markdown bullets. The commit message and finding 2 have it right.
- **The first commit's message named 13 files; the hook added two roadmap files.** I read the staged list before the hook ran. Amended (unpushed) to name them.
- **The full run I cited for that commit predated the hook's roadmap rebuild.** The tree key showed the mismatch. I ran the suite again (488 s) and corrected the message.
- **Per-commit gating was one run per tree, not one per commit.** 683c877, 91597b6 and 8b822f7 rest on one full run of the tree that holds all three (key 4736df4990f9); ff7563b has its own (key 6b4aa3b91763). I did not run the quick suite separately before each, since the full suite contains it.
- **I wrote a test that pinned prose, having just criticised one**, and deleted it before committing.
- **I told Joe the two new READMEs would force a 40-minute rerun of the slow tests.** They did not: I had written them before the first recorded pass.
- **`git gc --prune=now` also removed ten dropped stashes** (2026-10-12 to 2026-11-01). Joe approved the command; I am naming what it took.

## Questions for Joe

1. Where were ed8293d and the node edits before it committed from?
2. Is the GitHub repo public?
3. Split `test_gait.py` now, or wait for the new machine's numbers?
4. Should the dossiers keep line numbers?
5. The four items in finding 9.
