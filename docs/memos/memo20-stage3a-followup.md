# Memo 20: Stage 3a follow-up to memo 19

STATE: (filled in by the commit that regenerates docs/STATE.md)

## Decision summary

- All three items are done, one commit each, the full suite before each. Editing a memo, note or log no longer makes a committed thread output stale; the freshness test is unchanged and still passes.
- Numbers:
  - dossier section 7 now reads `roadmap/nodes/` only (cap 20 unchanged); a prose edit changes 0 generated files (tested), a roadmap-node edit changes 3 (that dossier, `graph.json`, `STATUS.md`);
  - `fy thread refs <id>` on the real store runs live over `docs/memos/`, `notebook/`, `log/`, uncapped;
  - suite 1326 -> 1332 passed, 345 to 349 s per run (about six minutes, matching `CLAUDE.md`).
- Decisions for Joe: none. After this commit you activate the four load cases; they are still `proposed`.
- What would change the conclusion: nothing outstanding.

## Items

1. `5fc150c` Q1 and Q4. `tools/thread/refs.py`: `scan` (build, `roadmap/nodes` only) and `live` (memos, notebook, log; whole-token rule; newest file first by modification time, then path). The dossier's section 7 ends with ``Mentions in memos, notebook and log are not part of this file: run `python tools/fy thread refs <id>`.`` and says `None in roadmap/nodes/.` when empty. `fy thread refs <query>` takes the usual query rules and `--json`, writes nothing. Regenerated outputs are in the commit (25 files changed). The freshness test needed no change.
2. `eb4d361` Q3. `lc.gravity-hold-rom` has the purpose and notes you gave; status `proposed`. The notes state 13 unlimited hinges: lumbosacral (3), shoulder abduction-adduction (2) and shoulder rotation (2), which lack sheet ROM values, plus the thoracolumbar (3) and cervicothoracic (3) bare joints. A test counts them from the model (31 hinges, 18 with a range).
3. `97433d6` `sim/scripts/state.py` says about six minutes; a test keeps it equal to `CLAUDE.md`.

## Findings

- In item 1 I changed the code before the tests, so those tests have no recorded red run; they were run against the finished code. Items 2 and 3 had a red run.
- A shell here turns `\n` inside heredoc-fed Python strings into real newlines; it broke two test files again. I restored them from git and applied the patch from a file written with the editor tool.
- Prose mentions of a record id no longer appear in dossiers at all, so a memo that defines a record is not visible from its dossier except through `fy thread refs`. That is the intended trade.
- The `CLAUDE.md` line I proposed ("run `fy thread build` before `fy test` after editing a memo") is no longer needed; for roadmap-node edits it still applies.
