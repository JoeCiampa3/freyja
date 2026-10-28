STATE: base 2df6592f37c2 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2030/2033 | dirty yes (this task's files, uncommitted when generated)

# Memo 46: the rerun plan, the xfail convention, `fy state` lists xfails

## Decision summary

- **Nothing long was run.** This memo is the plan for your reruns. The tree is clean, the HEAD is `2df6592` (memo 45), the model is `1ceee2452e18`, the snapshot `492fe816e6d8`.
- **What is stale:** exactly four things, all recorded for model `cfa2e0743e83` (snapshot `cf4fdfe08804`): `hold_pose`, `stand_static`, `rom_sweep` (run ids `20261021-1548/1548/1549`) and the gait `20261021-1445-walk_treadmill`. A digest built in a scratch copy flags those three scenarios and nothing else. No other scenario has a record.
- **Time:** the gait took 62 min 49 s with 6 workers at 2g T8 (commit message of `8bc6c11`). This machine reports 6 CPUs and `fy gait` defaults to 5 workers, so expect about 75 min (62.8 x 6/5; an estimate, not a measurement). The scenario wall times were not recorded: the `540 s` in `rom_sweep`'s record is simulated time, not wall time. Treat the three scenarios as "minutes, unmeasured" and watch the first one.
- **Convention added:** CONVENTIONS section 7, after the waivers paragraph, verbatim as you gave it. The existing strict xfail's reason now names the owner, the removal condition and a review date (it previously pointed at a waiver entry that does not exist).
- **`fy state` lists every xfail:** a small change (one function, one section). Cost: `docs/STATE.md` was already at its 119-line cap and truncated (finding below), so the section costs the end of the briefs list five more lines.
- **Full suite once on the final tree (via `fy state`):** 2030 passed, 0 failed, 3 skipped.

## The rerun plan

Run from the repo root in PowerShell, with Fusion not needed. Before launching: commit or stash `data/falls/sources.md` if the other session still has it modified (run records carry `git_dirty` from `git diff HEAD` of tracked files, so a modified tracked file makes every record `git_dirty: true`). The Camargo raw dataset must be reachable (`CAMARGO_RAW_DIR` or `camargo_raw_dir` in `sim/local_config.json`), because `fy gait` reads it.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\Joe\Desktop\freyja     # adjust if the repo lives elsewhere

function Step([string]$label, [scriptblock]$cmd) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $label)
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "FAILED: $label (exit $LASTEXITCODE)" }
}

# 0. the tree must be clean (tracked files) and the model must be the one recorded here
if (git diff HEAD --name-only) { throw "tracked files are modified; commit or stash them first" }
$meta = Get-Content params/snapshot.meta.json | ConvertFrom-Json
if (-not $meta.model_sha256.StartsWith('1ceee2452e18')) { throw "model is $($meta.model_sha256), expected 1ceee2452e18" }
git rev-parse --short HEAD

# 1. scenarios on the current model
Step 'stand_static' { python tools/fy run stand_static }
Step 'hold_pose'    { python tools/fy run hold_pose }
Step 'rom_sweep'    { python tools/fy run rom_sweep }

# 2. the three-speed gait (0.5, 1.4, 1.6 m/s), writes the tracked extract the envelope reads (about 75 min)
Step 'gait walk_treadmill' { python tools/fy gait walk_treadmill --write-extract }

# 3. the two generated files
Step 'runs digest'   { python tools/fy runs digest }
Step 'runs envelope' { python tools/fy runs envelope }

Write-Host "done: now tell Claude, who removes the xfail and runs the suite"
```

Order and why: the scenarios first, so a failure shows in minutes and not after the gait; the gait before the digest and the envelope, because the envelope reads the gait extract. `--write-baseline` is deliberately not in the block: it would overwrite `sim/benchmarks/walk_reference.json`, the reference of `check.sim.walk_reference`, and that is a decision, not a rerun.

**What invalidates the runs while they go:** any change to the sheet, `params/snapshot.*`, `sim/models/freyja.xml`, `pre_processor.py` or the scenario and gait specs (a `fy build`, the watcher, an edit of a spec). Do not leave `fy watch` running. A change to a tracked file after a record is written makes later records `git_dirty: true` and, if it changes the model, makes the earlier ones stale again. Edits that do not touch the model are harmless to the numbers (the record carries `diff_sha256`), but keep the tree still anyway.

**After the block (Claude, next session):** read `sim/runs/DIGEST.md` and `ENVELOPE.md` and report the changes against the committed ones (a decision summary of the load changes per joint); the strict xfail on `test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce` will now fail the suite, so remove the marker; fix the test pins in `tests/test_gait_extract.py` that are re-recorded from the extract (as at 2g T8); full suite; commit the records.

## `fy state` and xfails

`tools/state` reads the `xfail` markers from `tests/test_*.py` and `checks/test_*.py` by AST (no run needed, deterministic) and writes `## Known failing (xfail)` between Waivers and Latest run per scenario: `path::test | strict | reason`, or `none`. Tests written first (two, in `tests/test_state.py`) and seen failing. Today's entry is the one stale test with its reason.

## Findings

- **`docs/STATE.md` is already truncated at its 119-line cap** (it ends "(truncated at 119 lines)" in the middle of the briefs list: the stage1 to stage3b briefs do not appear). The cause is the 47 memo names; each memo adds a line. The cap is pinned by `tests/test_state.py` (`< 120`). I did not change it. Recommend listing only the newest 5 memos and the current brief per track, or raising the cap; your call.
- The previous memo's xfail reason pointed at a waiver that was never added; fixed above.

## Questions for Joe

1. STATE.md: cap fix as recommended (newest memos only), or raise the cap?
2. Run `--write-baseline` after the rerun, to refresh `walk_reference.json`? It currently says its baseline is superseded by a design change. Recommended: yes, as a separate step after you have read the new envelope.

## Tests

Between changes: `fy test --quick` 904 passed (268 s); `tests/test_state.py` 22 passed (two new, seen failing first). Final tree through `fy state`: 2030 passed, 0 failed, 3 skipped (the strict xfail is not counted as a failure), 28 deselected.
