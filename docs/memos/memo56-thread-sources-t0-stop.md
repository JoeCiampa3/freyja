STATE: base 9dcc0b0c9579 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:3fdf8856ae62 | snapshot sha256:492fe816e6d8 | tests not run | dirty no (before this memo)

# Memo 56: thread sources brief stopped at T0; the test-run waiver has a hole

Brief: `docs/briefs/ariadne/thread-sources-brief.md`, hash confirmed as 3fdf8856ae62 (LF, no CRLF).

## Decision summary

- **T0's stop condition fired, so T1 did not start.** No code, record or schema changed. `rm.v1-thread-sources` is where it was.
- **What this means for Freyja: nothing yet.** This is a test-coverage gap in the brief's process, not a problem with the design. The repo is healthy and the design needs no change.
- **The hole:** `checks/test_thread_checks.py` reads `thread/records` and imports `tools/thread`, and neither `fy test --quick` nor the waiver's third command runs it.
- **The third command tests nothing:** `python -m pytest checks/thread_checks.py` collects 0 tests and exits 5, against the 8 tests the brief means it to cover. As written, every commit message would report a check that did not happen.
- **Quick suite 904 passed, 28 deselected, 307 s**, against CLAUDE.md's "about 4 minutes".
- **`checks/test_thread_checks.py` 8 passed, 1.44 s**, so adding it costs almost nothing.
- **Thread build warm 0.64 s** against G8's 2 s. **27 records, 0 errors, 0 warnings**, as G6 expects.
- **Sources table 34 rows, 0 duplicates**, matching 0037's 34. Neither row-level stop in the brief fires.
- **Decision for Joe:** change the third command to `python -m pytest checks/test_thread_checks.py`. Recommended; it is what the brief's own sentence intends.
- **Alternative:** add that file to `QUICK_GLOBS`. Not recommended: `tools/fy` is outside the waiver's change set, so that commit needs a full-suite run of about an hour.
- **I did not apply either fix.** The brief says to stop, I may not edit it, and the waiver is an override only you can change.
- **What would change this:** nothing else in T0 blocks T1. After the fix, a re-run needs only T1 onward. T0's numbers stand while commit 9dcc0b0's code is unchanged.

## Finding 1: the stop

T0 says any test that `fy test --quick` does not collect, and that imports `tools/thread` or reads `thread/`, means the waiver does not cover the brief, and to stop before T1.

`QUICK_GLOBS` (`tools/fy/cli.py:67`) looks only in `tests/`, so nothing under `checks/` is collected. I searched `tests/` and `checks/` for every file outside the quick set.

| File | Touches the thread? | Result |
|---|---|---|
| `checks/test_thread_checks.py` | Yes: imports `thread_checks`, which imports `thread.build` and `thread.store`; reads `thread/records` | **Hit**, 8 tests |
| `tests/test_state.py` | Imports `tools/state`, whose `thread_line` calls the thread build, but its temporary repo has no `thread/`, so that returns early | Not a hit |
| `tests/test_gate.py`, `test_scenarios.py`, `test_template.py` | Use `checklib` only | Not a hit |

Finding 2 is why this hit matters more than a formality. The waiver names exactly this check as the reason for its third command.

Risk if ignored: low for T1. `coverage_problems` reads `kind`, `status`, `id`, `body`, `also_bodies` and `hinges` and never `schema`, so I expect these tests to pass after migration. That is from reading the code; I have not run it on /2 records.

## Finding 2: the waiver's third command is empty

`checks/thread_checks.py` defines `check.thread.coverage` but no `test_` function, and `pytest.ini` sets no `python_functions`. The tests live in `checks/test_thread_checks.py`.

```
$ python -m pytest checks/thread_checks.py -q
no tests ran in 0.17s
exit 5
```

Exit 5 would also stop any `&&` chain, so the brief's sequence cannot be reported as passed.

## T0 baseline

Run on 9dcc0b0, clean tree, repo `.venv`.

| Item | Result |
|---|---|
| `fy thread build`, first and warm | 0.68 s, 0.64 s, no generated file changed |
| Store | 27 records: 10 segments, 10 joints, 5 load cases, 1 part, 1 work item |
| Rework, errors, warnings | 0, 0, 0 |
| `fy test --quick` | 904 passed, 28 deselected, 307 s |
| Waiver's third command | 0 tests, exit 5 |
| `checks/test_thread_checks.py` | 8 passed, 1.44 s |
| Full suite | Not run; the brief reserves it for the checkpoint |

## T0 inventory

**`thread-record/1` and its schema file:**

- Library: `tools/thread/build.py:213` (loads the schema), `tools/thread/fixture.py:67` (writes the id).
- Tests: `tests/thread_help.py:32`, `tests/test_thread_toe.py:25`, `tests/test_thread_schema.py:22,32`, `tests/test_cad_schema.py:179,180`.
- Fixtures: all 32 YAML files under `tests/fixtures/thread/`.
- Real store: all 27 records.
- `CONVENTIONS.md`: 1 place. `tools/cad/` and `checks/`: none.

**`data/falls/sources.md`:**

- 4 tables. 3 qualify (forward 10 rows, backward 9, sideways 15); Gaps does not (first cell `Region`, no Status column).
- 34 row ids, all unique: F1 to F10, B1 to B9, S1 to S15.
- Status prefixes: 14 `Verified`, 20 `Unverified`. One Verified row is written `Verified\[12\]` (F9), which the starts-with rule accepts.
- Every row's cell count equals its header's, so no cell holds an unescaped `|`.

**G6 precheck.** The one real stamp, `work.upper-arm-cad` 20261027-2231, consumes snapshot addresses only, so T1's schema-line change cannot move its status. All 5 load cases are unflagged.

**Prediction for T1, unmeasured.** Each record's outputs hash its whole record, `schema` included, so I expect every derived file, dossier, `graph.json` and `STATUS.md` to change, in their banner hash only.

**Decisions.** 10 records with front matter, all `accepted`. No real superseded status exists yet, so the quoted form is exercised only by the T4 fixture. `0037` carries the labels D1 to D7.

## Observations, not fixed

- `CLAUDE.md` is out of date on timings: quick is about 5 minutes (it says 4), and the full suite was 3424 s at memo 55 (it says about 18 minutes).
- `docs/STATE.md` was far behind at session start (base 5c96635, Ariadne brief stage3b). It is refreshed here with `--no-run`, so it says tests not run, to keep the brief's one full-suite run for the checkpoint.

## My mistakes

None that affected a result. The third baseline command ran in a background chain, which is why the task reported failure; I re-ran it alone to confirm the exit code.

## Questions for Joe

1. Change the waiver's third command to `python -m pytest checks/test_thread_checks.py`? Recommended yes. Overwriting the brief changes its hash, so give the new prefix in the next prompt.
2. Should that change also state that `checks/test_thread_checks.py` is accepted as outside `--quick`? Recommended yes. Otherwise T0's stop condition still fires on a re-read.
