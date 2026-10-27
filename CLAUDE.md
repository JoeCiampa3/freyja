# CLAUDE.md

Read in this order at the start of a session: `CONVENTIONS.md` (the contract for this repo), `docs/STATE.md` (where the repo is now), `docs/OVERVIEW.md` (what the project is, once per fresh account or session), the newest file in `docs/memos/`, then the current brief. You have no memory of earlier sessions; the repo is all there is. If something is not in a file, ask Joe; do not guess.

Tracks. **Ariadne** is the digital thread: the pipeline from the sheet to the model, sims, load envelopes and later CAD and FEA (Stages 2, 3 and on), with the system model in `thread/` as its data layer. **Architecture** is repo tooling, such as the roadmap.

Current Ariadne brief: `docs/briefs/ariadne/stage2g-brief.md`.
Current architecture brief: `docs/briefs/architecture/volume-extractor-brief8.md`.

The prompt names which brief to execute; if it does not, ask. If the prompt gives a hash prefix, check `sha256sum` of the brief against it before starting; on a mismatch look for CRLF line endings, report the actual hash, and stop if it still differs. Never edit a brief; Joe overwrites them.

## Commands

Run everything as `python tools/fy <command>` from anywhere in the repo.

- Test: `python tools/fy test` (offline, same as `python -m pytest` from the root). Model checks: `python tools/fy check`.
- Build and sheet: `python tools/fy build [--dry-run | --xlsx FILE]`.
- Runs: `python tools/fy run <scenario>`, `python tools/fy sweep <spec>`, `python tools/fy gait <spec>`, `python tools/fy view <scenario>`.
- Read results, not raw arrays: `sim/runs/DIGEST.md` (latest run per scenario), `sim/runs/ENVELOPE.md` (worst case per joint), `sim/gait/<id>/GAIT.md`. Regenerate with `python tools/fy runs digest` and `python tools/fy runs envelope`. Standing loads come from `stand_static`, not `hold_pose`.
- Thread (the system model): `python tools/fy thread validate | build | show <query> | impact [<address>] [--edit <address>=<value> ...] | why <work> | stamp <work> [--note T] [--pin] [--by N] | fixture --out DIR`. Read `thread/STATUS.md` (counts, rework queue with diffs, budgets, proposed records, problems) and `thread/dossiers/<id>.md`, not the raw records. Everything under `thread/derived/` and `thread/dossiers/`, and `thread/graph.json` and `thread/STATUS.md`, is generated. The hook rebuilds it on commit; also run `python tools/fy thread build` before `python tools/fy test`, because a test compares the committed outputs with a fresh build and any edit to their inputs since the last build makes the two differ.
- State: `python tools/fy state` before the final commit of each task group. Open every memo and final message with its STATE line.

## Rules for every session

1. Tests first: write the test, watch it fail, then implement. One commit per task, with the test output in the message. While iterating run only the affected test file; run the full suite once before each commit (it takes about six minutes: 344 s at memo 19). Stage files by explicit path, never `git add -A`; read `git diff --cached --stat` before committing and name any file that is not part of the task; confirm an edit applied before you commit it. Make multi-line edits with the editor tool, not a shell heredoc (heredocs have been dropped silently on this setup).
2. Never hand-edit a generated file. Never touch the sheet, `local_config.json`, credentials or keys. Never put a secret, an absolute path or a timestamp in a tracked artifact. Create thread records only as `proposed`, never set one `active`, and never stamp a manual work item unless the prompt says to.
3. Stop and ask before: changing the model, the template, `pre_processor` or the meaning of any placeholder; clipping or silently dropping a frame; adding a dependency; changing a check tolerance or a geometry value because a result looks wrong; choosing any tolerance by tuning toward a result.
4. A check or result that contradicts the brief, the memos or `CONVENTIONS.md` is a finding. Report the measured number and stop; do not quietly follow either side or make it pass.
5. A checkpoint named in the brief ends the session: write the memo, run `fy state`, and stop. Joe starts the next session. Do not print raw arrays or whole directory trees into the session. Summarise: counts, shapes, a few names.
6. Reports live in the repo: write each checkpoint report to the next free `docs/memos/memoN-<slug>.md`, committed, with findings first, the numbers behind every claim, every tolerance you chose and why, your own mistakes stated plainly, and the questions that need Joe. Joe should never have to paste it into chat. Open every memo and final message, after the STATE line, with a decision summary of about 15 lines in plain language for a reader who will not read the code: what the result means for Freyja; the five or six numbers that matter, each beside a reference value (literature, spec or the previous result); the decisions Joe must make, each with your recommended option; and what finding would change the conclusion. The detail follows below it.
7. If a change to a schema or a convention is needed, edit `CONVENTIONS.md` in the same commit as the change and say so. Joe owns that file.
8. Environment: Windows, LF line endings, the repo `.venv` if it exists. Tests are offline and deterministic. Raw datasets stay outside the repo (`CAMARGO_RAW_DIR` or `camargo_raw_dir` in `sim/local_config.json`, which only Joe edits).
9. Register: blunt, technically dense, no padding. State uncertainty with a number where you can. Do not soften a bad result or re-argue a recommendation Joe has declined.
