# Thread sources brief (for Claude Code): evidence on load cases, and the stamping rule

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `docs/briefs/ariadne/stage3a-brief.md` (the system model this extends), `decisions/0036-fall-intent.md` and `decisions/0037-fall-design-basis.md`. This brief belongs to the Ariadne track. It specifies `rm.v1-thread-sources`, which closes when Joe signs off the memo.

Tag: Delegate.

## Purpose

Stage 3a gave every load case `independent_source_required`, a boolean that is true where the simulation's physics is itself the untrusted part. Nothing reads it, so it is decorative. 0036 and 0037 make fall loads rest on evidence the simulation cannot supply, and `rm.v1-fall-load-cases` will write the first flagged cases. This brief makes the flag bite before that happens:

1. A load case can carry `evidence`: citations the build resolves and grades. Three kinds exist: a clause of a decision record, a row of a literature table, a test record.
2. A flagged case with no admissible evidence is **unsourced**. `write_stamp` refuses to stamp an active work item that consumes one; any other work item that consumes one draws a warning on every build.
3. The load-case record gains the energy-defined form 0037 D1(a) specifies, so `rm.v1-fall-load-cases` writes into a schema that already fits.
4. Every record moves to `thread-record/2`.

"Independent" means independent of the simulation's contact physics. Under 0037 a fall case's design energy comes from the energy bound (D1(b), mechanics) or a geometric drop, and the literature only calibrates. The commonest evidence for a fall case is therefore an accepted decision clause, not a paper. The roadmap title said "literature or test" until 2026-10-31; under that title no v1 fall case could have been sourced, and the rule would have refused every piece of active work that consumed one.

One checkpoint. The session ends with the memo.

## Gate criteria

Stated before the work. Each is reported in the memo as pass or fail with its numbers, and Joe signs off the memo's gate table. Do not change a criterion to make a result pass; a criterion that looks wrong is a finding.

**G1. Grading.** On the `sources` fixture (T4), every load case derives the sourcing the T4 table gives. Derived equals intended, by test.

**G2. The rule.** Every stamp in the T4 table is written or refused as the table says, through `fy thread stamp`; the refusals also hold through the CAD path as T3 describes. A refused stamp writes nothing: the root is byte-identical before and after. A refusal names every unsourced case the item consumes and no other case.

**G3. Evidence lost after a stamp.** Superseding the decision that alone sources a case, after a consumer was stamped, makes the next build warn `unsourced-consumption` naming that consumer, and leaves its work status `current`.

**G4. Derived-file addresses count.** A work item consuming `thread/derived/<case>.json#/...` is treated as consuming the case.

**G5. What-if.** `fy thread impact --edit <case>#/evidence=[]` on a sourced case with a stamped active consumer reports the new `unsourced-consumption` warning and leaves the root byte-identical.

**G6. Migration.** After T1 the real store holds its 27 records, all `thread-record/2`, with zero errors and the same warnings as before T1 (none at the time of writing). `work.upper-arm-cad` keeps its work status. The memo lists every generated file T1 changed, with the reason for each.

**G7. Error classes.** Each new error (T2) has a hand-authored invalid fixture that produces exactly that error and nothing else.

**G8. Cost.** Two builds from the same inputs are byte-identical. A warm `fy thread build` on the real store stays under 2 s. The new tests add under about 15 s to the suite. Report the measured numbers either way.

## Concepts

**Evidence entry.** `evidence` is an optional list on a load-case record, unique items, each one of:

```yaml
evidence:
  - {kind: decision, record: adr-0037, clause: D1(b)}
  - {kind: literature, file: data/falls/sources.md, row: S1}
  - {kind: test, path: bench/<record>.json}
```

Each may also carry `note` (text). `clause` is `D<n>`, optionally followed by one lowercase letter in parentheses (`D3`, `D1(b)`). A value set by a Revisions or Amendments entry is cited by the clause that entry amends, plus the record that derived the value where one exists (0037's hand-and-arm energy: `adr-0037 D3` and `adr-0008 D5`).

**Resolution.** An entry that does not resolve is an error, as an unresolved reference is.

- *decision:* `record` names a decision in `decisions/` by its front-matter id, and the record's body carries the clause's `D<n>` label either as a bold run (`**D<n>` followed by a space, a full stop or an opening parenthesis, so `D1` does not match `**D10`) or as a heading (`#`s, a space, `D<n>`). The parenthesised letter is not checked.
- *literature:* `file` is a repo-relative `.md` path that exists. A qualifying table is a Markdown table whose header's first cell is `#` and which has a `Status` column. `row` must be the first cell of exactly one row across all qualifying tables in the file. Cells split on unescaped `|` only.
- *test:* `path` is a repo-relative JSON or YAML file that exists and parses.

**Admissibility.** A resolved entry is admissible when:

- *decision:* the record's status is exactly `accepted`. A proposed record and a `"superseded-by: adr-NNNN"` record are not.
- *literature:* the row's Status cell, stripped, starts with `Verified`. An Unverified row may be attached as a cross-check and never counts (0037 D1(c)).
- *test:* the file validates against a schema on the library's list of admitted test-record schemas. This brief leaves that list empty: no test-record format exists, and admitting any JSON would let a simulation run record count as a test. A test entry therefore resolves and is never admissible yet. Adding a schema to the list is Joe's decision.

**Sourcing**, derived per load case: `not_required` when `independent_source_required` is false (evidence may still be attached, and is shown); otherwise `sourced` when at least one entry is admissible, else `unsourced`. A **flagged** case is one with `independent_source_required: true`.

**Consuming a case.** A work item consumes a case when an address in its `consumes` belongs to that case: the record itself or `thread/derived/<case>.json`, as `Build._record_of_address` already decides. Consumption is direct only. A work item that consumes a requirement or a result file built from a fall case is not seen by the rule. Nothing does that today (`requirements/` is empty); the gap is written into CONVENTIONS and revisited when the first `req.` file lands.

**The rule.** `build.write_stamp` refuses, writing nothing, when the work item's status is `active` and it consumes an unsourced case. Every other stamp proceeds as it does now. On every build, every work item that is not superseded and consumes an unsourced case draws the warning `unsourced-consumption`, naming the item, its status, its baseline stamp if it has one, and each unsourced case. Work status is not touched: it still follows the stamped addresses alone.

**Energy-defined load case.** A third form of a load case's `source`, for fall cases (0037 D1(a)):

```yaml
schema: thread-record/2
id: lc.fall-hip-lateral        # illustrative; the real cases are rm.v1-fall-load-cases'
kind: load_case
status: proposed
purpose: Lateral fall from standing, hip first.
source:
  zone: hip                    # the 0037 D3 zone, a slug
  direction: lateral, hip first
  energy_j: 540                # E_design
  energy_basis: E_max          # free text, as in D3
  # contact_velocity_m_s and effective_mass_kg are optional, where 0037 D1(a) needs one
zone_in: seg.pelvis            # the segment housing the zone (0037 D3, "Housed in")
independent_source_required: true
evidence:
  - {kind: decision, record: adr-0037, clause: D1(b)}
```

With this form `independent_source_required` must be true (the schema says so) and `zone_in` is required; `zone_in` is forbidden on the other two forms. `energy_j` is a number greater than zero. `zone_in` is a new authored relation, load case to segment, and derives `fall_cases` on the segment; both go in the edge registry. A work item consumes the energy as `lc.fall-hip-lateral#/source/energy_j`.

The decision decides the energy and the record carries it, because a decision's Markdown is not addressable and work must consume a number. A change to a decision that moves a carried value edits the load-case record in the same commit.

## Out of scope

- Writing any fall case, or any evidence on the real store's load cases. That is `rm.v1-fall-load-cases`. The five real cases are unflagged and stay as they are, apart from their schema line.
- The fall-reserve part records of 0037 D7, volume budgets (`rm.v1-thread-budgets`) and any fall scenario in the simulation.
- A test-record schema, and any entry on the admitted-test-schemas list.
- Provenance from requirements or result files back to load cases.
- Any edit to `data/falls/sources.md`, to a decision record, to `roadmap/` or to the viewer. `thread-stamp/1` and `thread-graph/1` do not change (edge types are free strings in the graph schema).

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, rule 10 on coupled tasks included, except for the test-run waiver below. No new dependencies. `tools/thread/` still must not import `mujoco`. Deterministic outputs: sorted keys, LF, no timestamps outside a stamp's id.

**Test-run waiver (overrides `CLAUDE.md` rule 1 for this brief only, on Joe's instruction; amended after memo 56).** No commit in this brief runs the full suite, whatever `git diff --cached --name-only` shows, and neither does the checkpoint. Before every commit, run in order: `python tools/fy thread build`, `python tools/fy test --quick`, then `python -m pytest checks/test_thread_checks.py`. The last is run explicitly because those tests read the real store that T1 rewrites and `--quick` does not collect them (`QUICK_GLOBS` looks only in `tests/`; memo 56). It must report its tests passed: zero tests collected is a failure, not a pass. Each commit message names this waiver and gives the three results with their times. While iterating, run only the affected test file, as rule 1 says. At the checkpoint, run `fy state --no-run`. The first later commit that rule 1 covers runs the full suite as usual, so a regression outside this brief's set surfaces there.

The waiver holds because this brief changes only the thread library, its schemas, records and generated outputs, the fixture generator, the two stamp CLIs and CONVENTIONS, and none of the slow tests (gate simulations, gait, envelope builds) exercises the thread. T0 checked that claim (memo 56): the one thread-reading test outside `--quick` is `checks/test_thread_checks.py`, which the waiver runs. A commit that reaches outside that set (anything under `sim/`, `tools/roadmap/`, `tools/envelope/` or `tools/state/`, or under `checks/` other than `thread_checks.py` and `test_thread_checks.py`) loses the waiver: rule 1 applies to it, and its message says so.

Stop and ask before:

- adding an evidence kind, or admitting any schema as a test record;
- making `unsourced-consumption` an error, or letting sourcing change a work status;
- changing the stamp schema, the address grammar or the hashing rule;
- parsing anything other than the Markdown table form above as literature evidence;
- changing the real store beyond the schema line of T1.

Report as a finding, and stop if it blocks a task: a duplicate row id among `data/falls/sources.md`'s qualifying tables, or a row whose Status cell starts with neither `Verified` nor `Unverified`.

## Amendments to CONVENTIONS (each lands with the task named)

1. **Section 8, Thread record (T1).** `thread-record/2`, schema `docs/schemas/thread-record-2.schema.json`. In the example block, an optional `evidence` line under the load-case example, and one line for the energy-defined form with `zone_in`.
2. **Section 3, Thread terms (T2).** Define evidence, resolved, admissible, flagged load case and the three sourcing values. Add `zone_in` to the list of stored relations. State that consumption is direct (an address into the record or its derived file), and that requirements and result files are not traced back to load cases.
3. **Section 8, Decision (T2).** One sentence: a change to a decision record that moves a value a load case carries edits that load-case record in the same commit.

## Tasks

**T0. Baseline and inventory.** Run `fy thread build` and `fy test --quick`, and record the counts and warnings. Inventory every place that writes, reads or asserts `thread-record/1` (the library, the fixture generator, tests, `tools/cad/`, `checks/`). List every test that `fy test --quick` does not collect and that imports `tools/thread` or reads `thread/`. Any such test other than `checks/test_thread_checks.py`, which the waiver runs before every commit, means the test-run waiver does not cover this brief's changes: report it as a finding and stop before T1. T0 ran in memo 56, and its numbers stand while the code at 9dcc0b0 is unchanged; on a re-run, start at T1 and say in the memo whether that still holds. Inventory `data/falls/sources.md`'s qualifying tables: how many, their row ids, any duplicate, and the Status prefixes seen. Nothing is committed; the inventory goes in the memo.

**T1. Contract and migration (one commit; the tasks are coupled).** The hook builds the thread on every commit, so the validator cannot move to /2 in one commit and the records in another. In one commit:

- write `thread-record-2.schema.json`: /1 plus `evidence`, the energy-defined `source` form and `zone_in`, with the conditionals above. Leave `thread-record-1.schema.json` in place and unchanged, as history. The loader accepts only /2; a /1 record is a schema error whose message says to migrate;
- change the `schema:` line of all 27 records and nothing else in them;
- move the fixture generator and every test fixture to /2;
- regenerate the outputs, and make amendment 1.

Schema tests. Rejected, one example each: an unknown evidence kind; a decision entry without `clause`; a malformed clause; the energy form with the flag false; the energy form without `zone_in`; `zone_in` on a scenario-form case; `energy_j` of 0; evidence on a record that is not a load case; a /1 record. Accepted: one valid load case per `source` form, and one entry of each evidence kind. G6.

**T2. Library.** Evidence resolution, admissibility and sourcing; `zone_in` in the reference checks (`ref-unresolved`, `ref-kind`) and in the edge registry beside `fall_cases`; the `unsourced-consumption` warning.

New errors:
- `evidence-unresolved`: a cited decision, file, row or test path that does not exist;
- `evidence-ambiguous`: the row id is the first cell of more than one qualifying row in the file;
- `evidence-clause`: the decision exists but carries no `D<n>` label as defined above.

A load case's derived document carries its evidence entries, each with `resolved`, `admissible` and a one-line `reason`, and its `sourcing`. It depends on each cited decision's front matter and each cited row's cells, so changing a decision's status or a row's Status moves the case's banner and its consumers' warnings.

Invalid fixtures: one per new error, one per sub-case of `evidence-unresolved` (decision, file, row, test path), and one for `zone_in` naming a joint. Amendments 2 and 3. G7.

**T3. Rule, CLI and rendering.**

- The refusal in `build.write_stamp`. Its message names the work item, each unsourced case, and each case's attached entries with the reason each is not admissible, or says the case has no evidence.
- `fy thread stamp` and `fy cad stamp` both print the `unsourced-consumption` warnings naming the item after a stamp that proceeds. Both paths already end in `build.write_stamp` (`tools/cad/ops.py`), which is why the rule lives there.
- `fy thread why <work>` adds one line per unsourced case the item consumes.
- Load-case dossiers gain an **Evidence** section after Relations: each entry, with a relative link where it cites a file (every dossier link must resolve, as now), its admissibility and reason, and the case's sourcing. Segment dossiers list `fall_cases` among their relations.
- `thread/STATUS.md` gains **Unsourced load cases** after Budgets: each unsourced case with its consumers and their statuses, or "None."

Test the CAD path with the fakes the Stage 3b stamp tests use. If it cannot be exercised without Fusion, test `build.write_stamp` directly, and say in the memo that the CAD path is covered only through its call site.

**T4. The `sources` fixture.** `fy thread fixture --out DIR --scenario sources` writes a root with the structural records, the model and the snapshot, and:

- decisions `adr-0901` (accepted, with `**D1` and `**D3` labels), `adr-0902` (proposed, `**D1`), `adr-0903` (status `"superseded-by: adr-0901"`, quoted as CONVENTIONS section 8 writes it; `**D1`) and `adr-0904` (accepted, `**D1`, cited by one case only, for G3);
- a synthetic `data/falls/sources.md`, not a copy of the real one, with two qualifying tables holding `X1` (Status `Verified`), `X2` (`Unverified (abstract)`) and `X3` (`Verified (figure only)`), and one non-qualifying table;
- `bench/drop-0001.json`, any valid JSON.

The load cases, and the sourcing each must derive (G1):

| case | flag | evidence | sourcing |
|---|---|---|---|
| `lc.src-none` | true | none | unsourced |
| `lc.src-adr` | true | adr-0901 D1 | sourced |
| `lc.src-adr-proposed` | true | adr-0902 D1 | unsourced |
| `lc.src-adr-superseded` | true | adr-0903 D1 | unsourced |
| `lc.src-row` | true | X1 | sourced |
| `lc.src-row-qualified` | true | X3 | sourced |
| `lc.src-row-unverified` | true | X2 | unsourced |
| `lc.src-test` | true | bench/drop-0001.json | unsourced |
| `lc.src-mixed` | true | X2 and adr-0901 D3 | sourced |
| `lc.src-post` | true | adr-0904 D1 | sourced |
| `lc.src-plain` | false | none | not_required |
| `lc.src-plain-cited` | false | X2 | not_required |
| `lc.fall-sample` | true; energy form, `zone_in: seg.pelvis` | adr-0901 D3 | sourced |

The work items, each `of: seg.pelvis` (fixture only, so `active` is allowed here), and the stamp outcome each must give (G2):

| work item | status | consumes | stamp |
|---|---|---|---|
| `work.a-<case slug>`, one per flagged case | active | `<case>#/source` (`lc.fall-sample#/source/energy_j` for the fall case) | refused where the case is unsourced, else written |
| `work.p-none` | proposed | `lc.src-none#/source` | written, and the warning printed |
| `work.a-derived-none` | active | `thread/derived/lc.src-none.json#/sourcing` | refused (G4) |
| `work.a-two` | active | `lc.src-adr#/source` and `lc.src-none#/source` | refused, naming `lc.src-none` only |
| `work.a-snapshot` | active | one snapshot address | written |
| `work.a-plain` | active | `lc.src-plain#/source` | written |

The generator writes the intended sourcing and stamp outcome to the intent file, and tests compare them with what the library derives. G3: stamp `work.a-src-post`, change `adr-0904`'s status to `"superseded-by: adr-0901"`, rebuild, and assert the warning and the unchanged `current` status. G5 runs on `lc.src-adr` with `work.a-src-adr` stamped.

## Checkpoint

Write the memo per `CLAUDE.md` rule 6, numbered one above the highest in `docs/memos/`. Include the gate table G1 to G8 with its numbers, the T0 inventory, the T1 change set, the timings (each commit's quick-suite and thread-check times), the tests added and their runtime, every finding, and the questions for Joe. Run `fy state --no-run` and stop.

## Decisions this brief makes (Joe approves them by committing it)

1. Three evidence kinds: a clause of an accepted decision, a Verified literature row, a test record on an admitted schema. Under 0037 the decision clause is the normal evidence for a fall case.
2. Unverified rows attach and never count (0037 D1(c)). Test entries count only against an admitted schema, and none is admitted yet.
3. Citations are checked by resolution (the source exists, the row is unique, the clause label is present) and graded by the cited source's own status, never by a grade typed into the load case.
4. The rule lives in `write_stamp`, so every stamping path enforces it. Active work is refused; all other consuming work is warned on every build. The warning is not an error, so the commit that supersedes a decision is not blocked, and work status still follows the stamped addresses alone.
5. Consumption is direct. The gap is written into CONVENTIONS and revisited with the first requirement file.
6. The energy-defined form and `zone_in` land in /2 now, so the fall cases need no /3. The decision decides a carried value and the record carries it; both change in one commit.
7. Every record moves to /2 in one commit. /1 no longer loads, and its schema file stays as history.

## Prerequisites for Joe

- Commit this brief with the roadmap edits that accompany it (`roadmap/nodes/rm.v1-thread-sources.md`, `roadmap/nodes/rm.v1-fall-load-cases.md`, `roadmap/README.md`), and point the "Current Ariadne brief" line in `CLAUDE.md` at this file. Committing approves the amendments and the decisions above.
- Prompt Code with this brief's path and its `sha256sum` prefix.
