# Memo 19: Stage 3a Part B, the real store, the commands and the hook

STATE: (filled in by the commit that regenerates docs/STATE.md)

## Decision summary

- The system model is live. The real store holds 23 records (10 segments, 9 joints, 4 proposed load cases), builds with 0 errors and 0 warnings, and the 48 generated files (derived JSON and dossier per record, `graph.json`, `STATUS.md`) are committed. The pre-commit hook rebuilds them on every commit.
- Numbers that matter:
  - coverage: 16 of 16 model bodies and 31 of 31 hinges are each bound by exactly one record; 259 of 261 snapshot keys are claimed (the two unclaimed are `target_mass` and `target_stature`, by design);
  - warm real-store build 0.10 s in the library, 0.52 s through `fy` including the interpreter (reference: under 2 s);
  - the hook adds about 0.5 s per commit (reference: under 2 s);
  - Part A's what-if, 0.53 s end to end (reference: under 3 s);
  - 52 tests added in Part B, about 15 s of runtime (reference: about 20 s); all 230 thread tests run in 23 s; full suite 1326 passed in 344 s (1274 at Checkpoint A).
- Decisions for Joe (recommended option first):
  1. Staleness test policy (Finding 1). Dossiers list where a record id is mentioned in memos, notebook, log and roadmap nodes, so editing any of those files makes the committed dossiers stale until `fy thread build` runs. The hook always fixes it at commit time, but `fy test` fails in between (`tests/test_thread_real.py`). Recommended: keep the test and add the build line to `CLAUDE.md` (below). Alternative: drop references from the staleness comparison.
  2. Approve the `CLAUDE.md` and `docs/OVERVIEW.md` lines below (I edited neither).
  3. Activate the four load cases when you have read them; they are `proposed` and stay so until you say.
  4. Keep `check.thread.coverage` advisory (recommended; the brief).
- What would change the conclusion: a record id mentioned so often that the 20-reference cap hides what matters, or a hook cost that grows with the number of memos (it scans about 190 files per build today).

## What was built (Part B)

| commit | task | what |
|---|---|---|
| `d8d3174` | prelude | Joe's answers: per-unit mass wording and claim arithmetic, new error `reaction-path`, `independent_source_required` definition, joint names |
| `5a4e987` | T5 | dossier sections 7 (references) and 8 (Mermaid neighbourhood, cap 25), link, cap and banner tests |
| `8bb87bc` | T6 | `fy thread validate`, `build`, `show`, `why`, `stamp` and the query rules |
| `0a554ab` | T7 | the real records and generated outputs, `check.thread.coverage`, fixture reads the real records, `seed.py` deleted |
| `fe601f4` | T8 | pre-commit hook, `Thread:` line in `fy state` |

**Prelude.** `mass.kg` is the mass of one unit and `sides` gives one unit per side (CONVENTIONS, schema). Claims carry `sides`, `total_kg` and `arithmetic`, and the `count` field is gone. Every budget row in the derived JSON, the dossiers and `STATUS.md` shows it, for example `2 x 2.847 kg, part.hip.m1 left and right`; the whole-body budget in `graph.json` lists the same. The new error `reaction-path` fires when a part's `reacts_into` is neither the parent nor the child segment of its `acts_across` joint, with its invalid fixture (`tests/fixtures/thread/invalid/reaction-path`). When an end of the joint is a body that two records bind (already an error) the check stays quiet so nothing cascades.

**T5.** References come from `roadmap/nodes/`, `docs/memos/`, `notebook/` and `log/` by the roadmap's whole-token rule (imported read-only), files only, 20 listed per dossier and the rest counted. They are inputs of the dossier alone: a changed note changes that dossier, `graph.json` and `STATUS.md` (their banner hashes cover every input), and not the derived JSON. The neighbourhood graph is read from the record's own document, the record plus its neighbours, and above 25 nodes it is a list.

**T6.** Commands as in the brief. Choices the brief left open: a root without `thread/` is a quiet success for `build` and `validate` (the roadmap's throwaway-repository hook test is untouched); `show` prints dossier sections 1 to 6; `stamp` writes a time-named stamp and refuses to overwrite one made in the same minute; `--by` defaults to `git config user.name`. `impact` takes an address, `--edit`, or both.

**T7.** The records were written once from the proposal in `seed.py`, which is deleted; the fixture now copies `thread/records/seg.*` and `jnt.*`. If the real store is invalid the fixture, and so every acceptance test, stops with `the real thread store (thread/records) is invalid ... <first errors>` (tested). The four load cases are as Joe specified: `lc.stand-static`, `lc.walk-1p4`, `lc.walk-1p6`, `lc.gravity-hold-rom`, all `proposed`, all `independent_source_required: false`, each with its reason in `notes` (rigid-body statics or inverse dynamics with the ground reaction supplied explicitly, no contact solver; provisional trust stays on the envelope rows). `check.thread.coverage` is advisory in `checks/thread_checks.py`; `fy check` and pytest run it, the model build gate does not (I reverted a first wiring through `checklib.make_post_checks`, which is the gate hook, before committing).

**T8.** The hook runs `fy thread build` after the roadmap build, only when `thread/` exists, and stages exactly `thread/derived`, `thread/dossiers`, `thread/graph.json`, `thread/STATUS.md`. The hook test builds a throwaway repository, commits, finds the outputs tracked, then breaks a record and sees the commit blocked with `ref-unresolved` and the generated files untouched.

## The real store

- Records: 10 segments, 9 joints, 4 load cases; 0 parts, interfaces, harness runs, work items. Segments and joints `active`, load cases `proposed`.
- Joints: ankle, cervicothoracic, elbow, hip, knee, lumbosacral, shoulder, thoracolumbar, wrist. Seven ROM keys the sheet lacks are listed (`rom_missing` in their derived files): lumbosacral flexion, extension, lateral bending, axial rotation; shoulder adduction, external and internal rotation.
- Outputs: 48 files, 0 errors, 0 warnings. `fy check`: `check.thread.coverage` PASS (16 bodies, 31 hinges).

## Timings

| what | time |
|---|---|
| warm real-store build, library | 0.10 s |
| `python tools/fy thread build`, nothing changed | 0.52 s |
| pre-commit hook, thread part | about 0.5 s (the roadmap part was there before) |
| fixture generation | 0.3 s |

## Tests added

Part B: 52. prelude 1 (the `reaction-path` fixture), `test_thread_render.py` 12, `test_thread_cli.py` 18, `test_thread_real.py` 9, `checks/test_thread_checks.py` 8, `test_thread_hook.py` 4. About 15 s. Full suite 1326 passed, 344 s. The T5, T6 and T8 tests were written before their code and failed first (T8: 4 failed). For T7 I wrote the tests and the record-writing script in one sitting and did not run the tests before the records existed, so there is no recorded red run for those 17; the mutation tests in `checks/test_thread_checks.py` are the proof that the check can fail.

## Lines I propose (I edit neither file)

For the `CLAUDE.md` command list:

- Thread: `python tools/fy thread validate | build | show <query> | impact [<address>] [--edit <address>=<value> ...] | why <work> | stamp <work> [--note T] [--pin] [--by N] | fixture --out DIR`. Read `thread/STATUS.md` (counts, rework queue with diffs, budgets, proposed records, problems) and `thread/dossiers/<id>.md`, not the raw records. The files under `thread/derived`, `thread/dossiers`, `thread/graph.json` and `thread/STATUS.md` are generated: never edit them. The hook rebuilds them on commit; after editing a memo, note or log that mentions a record id, run `python tools/fy thread build` before `python tools/fy test`.
- Thread records: create them only as `proposed`; never stamp a manual work item unless the prompt says to.

For the `docs/OVERVIEW.md` glossary:

- **Thread / system model:** the records of Freyja's segments, joints, parts, interfaces, load cases, harness runs and work items, with the relations between them stored once and everything else derived (`thread/`).
- **Record, binding:** one authored YAML file; a binding ties a segment to its model body and a joint to its hinges and ROM keys.
- **Address:** `<source>#<JSON pointer>`; its hash is 12 hex of the canonical JSON of its value.
- **Work item, stamp, pinned:** assisted or manual work whose output depends on addresses; a stamp records the hashes it was made against; a pinned stamp makes a difference `drifted` instead of `stale`.
- **Work status:** `unstamped`, `current`, `stale`, `drifted`, `unknown` (`reverified` is reserved).
- **Rework queue, impact, budget, dossier:** the stale, drifted and unknown work items with the values that moved; what an address touches; a segment's provision against its claims (mass first); the generated per-record document.

## Findings

1. **A memo edit makes the committed dossiers stale until `fy thread build` runs.** `test_the_generated_outputs_on_disk_are_what_a_fresh_build_gives` compares the files with a fresh build, and the fresh build reads `docs/memos/` and `notebook/`. This memo, for example, mentions record ids, so the dossiers of those records change when it is saved. The hook repairs it on commit; the suite fails in between. I ran `fy thread build` before the final suite run for exactly this reason. It is the price of references being generated (Decision 1).
2. **`CLAUDE.md` says the suite takes about 90 s; it takes 5.5 minutes** (342 s at the start of Part A, 344 s now). `state.py` repeats the figure. Not changed.
3. **Brief wording closed by your answers:** the "rises by it" mass sentence in T4 (per unit, now shown with its arithmetic); the combined T3 and T4 commit (accepted once; Part B kept to one commit per task, with the prelude as a separate commit for your answers).
4. **`rework` beside errors.** Work statuses are derived only when the thread has no errors, so the `Thread:` line shows `rework 0` next to a non-zero error count; read the errors first. Records and work-item counts do not depend on it.
5. **Cosmetic:** the dossier's "Authored" list prints list-valued fields as compact JSON (`hinges`, `rom_keys`). Fine for now; a table would read better.
6. **Choices recorded for later:** references use the roadmap's whole-token rule, so `seg.thigh2` and `xseg.thigh` do not match `seg.thigh`; a reference line is cut at 200 characters (the roadmap's cap); the dossier's reference list is capped at 20, which will matter for `seg.pelvis` and `jnt.hip` once more memos mention them.
7. **Tolerances chosen:** none new beyond Part A's. The 20-reference and 25-node caps are the brief's (25) and mine (20): a dossier is read by a person, and 20 lines is a screenful.
8. **My own mistakes.**
   - I started a full suite with the hook test already in the tree and the hook not yet written; I stopped it and restarted without that file. The T6 commit records the clean run.
   - I first wired the new check through `checklib.make_post_checks`, which would have put it in the model build gate; I read the diff before committing and reverted it.
   - A shell here turns `\n` inside a heredoc-fed Python string into a real newline; it broke a test file twice and I fixed it by building the string with `chr(92)` and by writing larger files with the editor tool.
   - I wrote a first version of the reference test that expected the derived JSON to be unaffected by a changed note, which was true only after I split the dossier's inputs from the derived file's; the test caught my own mistake and the split is now the design.
   - A query-rule test I wrote assumed `hip` is ambiguous; by the roadmap's rule (a kind prefix added when exactly one record has it) it resolves to `jnt.hip`. I changed the test to use `m2`, which is ambiguous.
9. **Defects seen outside the task.** The roadmap hook rebuilt `roadmap/` on every commit and staged nothing new. `docs/STATE.md` carried the old node count until regenerated at Checkpoint A (fixed there). None other.
10. **Not done, by the brief:** a roadmap `done_when` type that reads a work item's status, any real part, interface, harness or work record, other budgets, the viewer. The 3b bridge writes into this model.

## Questions that need Joe

- Q1. Staleness test policy (Decision 1 above).
- Q2. The `CLAUDE.md` and `docs/OVERVIEW.md` lines above.
- Q3. The four load cases are `proposed`. Activate them when you have read the notes, or tell me what to change.
- Q4. The reference cap per dossier: 20 (mine). Say if you want more or fewer.
- Q5. Should the brief for 3b name which record kinds it will write first (parts for the upper arm, per the roadmap)? Nothing in 3a needs the answer.

## Checkpoint

Part B ends here. `fy state` is run in the commit that follows this one.
