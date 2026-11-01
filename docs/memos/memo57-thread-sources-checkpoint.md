STATE: base 9e5518eb2f22 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:fa15c37d9eb1 | snapshot sha256:492fe816e6d8 | tests not run | dirty no (before this memo)

# Memo 57: thread sources checkpoint; the flag now bites

Brief: `docs/briefs/ariadne/thread-sources-brief.md`, hash confirmed as fa15c37d9eb1. Specifies `rm.v1-thread-sources`, which closes when you sign off the gate table.

## Decision summary

- **G1 to G8 all pass.** A load case flagged `independent_source_required` now has to show evidence before active work on it can be stamped. `rm.v1-fall-load-cases` can write its cases into a schema that already fits.
- **What this means for Freyja:** no fall loads, no real load case and no budget changed. The 5 real cases are unflagged, so the rule fires on nothing yet.
- **Real citations work.** `adr-0037` D1(b), D3 and D7 and `adr-0008` D5 and D6 resolve on the real files; 14 of the 34 literature rows are admissible, matching the 14 Verified at memo 56.
- **Real store: 27 records, 0 errors, 0 warnings**, as at T0. `work.upper-arm-cad` is still `current`.
- **Warm build 0.60 s** against G8's 2 s and 0.64 s at T0.
- **New tests 9.6 s** against about 15 s. The quick suite went from 904 to 1040 passed, and from 307 s to 320 s.
- **Full suite not run**, as the amended waiver says. The last result is memo 55's 2080/2083; the next commit under rule 1 runs it.
- **Fusion not exercised.** `fy cad stamp` is tested through its real CLI against the fake; the 28 deselected tests were not run.
- **Decision 1:** sign off the gate table. Recommended yes.
- **Decision 2:** add the stamping rule to CONVENTIONS. Recommended yes; it is in code and the brief, not in the contract.
- **Decision 3:** leave `adr-0036` uncitable. Recommended yes; 0037 carries what a case needs.
- **Decision 4:** keep superseded load cases graded. Recommended yes.
- **What would change this:** a failure in the next full suite, outside the thread and CAD tests, would mean the waiver's claim was wrong. A fall case resting on a requirement rather than directly on a case stays invisible to the rule, as the brief accepts.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G1 Grading | Pass | 13 of 13 cases derive the table's sourcing |
| G2 The rule | Pass | 16 of 16 stamps as tabled through `fy thread stamp`: 7 refused, 9 written. Each refusal leaves the root byte-identical and names exactly its cases |
| G3 Evidence lost | Pass | `work.a-src-post` warned, status stays `current`, 0 errors |
| G4 Derived addresses | Pass | `work.a-derived-none` consumes `lc.src-none`, refused |
| G5 What-if | Pass | Reports the new warning, 0 status changes, root byte-identical |
| G6 Migration | Pass | 27 records all /2, 0 errors, 0 warnings, same as T0; `work.upper-arm-cad` `current` |
| G7 Error classes | Pass | 8 new invalid fixtures, each exactly one error |
| G8 Cost | Pass | 56 outputs byte-identical across builds; warm `fy thread build` 0.56 to 0.60 s; new tests 9.6 s |

G2's CAD half: active work on an unsourced case is refused with exit 1 and nothing written, and proposed work prints the warning, both through `fy cad stamp` with the Stage 3b fake. G2's fixture also has `fy thread stamp` refuse `work.a-two` naming `lc.src-none` only.

Refused work items: the 5 unsourced flagged cases' `work.a-` items, `work.a-derived-none` and `work.a-two`.

Mutation: with the rule disabled in `write_stamp`, 3 of the 17 fixture tests fail. Restored after.

## Findings

1. **`fy cad stamp` could show a traceback.** It caught only `Refused`, while `write_stamp` raises `ValueError`, so any refusal from there, old or new, would have crashed. `ops.stamp` now converts it. Fixed in T3 because the rule needed it.
2. **`adr-0036` has no `D<n>` labels**, so it cannot be cited: its body uses `**Protocol.**` and `**Principle.**`. Citing it gives `evidence-clause`. The other labelled records checked resolve (see Decision summary). I checked 0036, 0037 and 0008; I did not check the other 7 decisions.
3. **An unquoted superseded status blocks the commit.** `status: superseded-by: adr-0901` is invalid YAML, so `_load_decisions` drops the record, and any case citing it fails with `evidence-unresolved` (measured on `lc.src-post`). The hook then blocks the commit. Brief decision 4 says superseding is not blocked, and that holds for the quoted form CONVENTIONS requires. The failure is loud, so I left it.
4. **The what-if cannot edit a decision.** `apply_edit` takes records and snapshot values only. G5 uses a record edit as the brief says. "What if I supersede this ADR" has to be tried on a real edit.
5. **A superseded load case is still graded.** The brief defines sourcing per load case, whatever its status, so consumers of a superseded unsourced case still warn or refuse.
6. **`zone` is a slug**, so D3's "hand and arm" must be written as for example `hand-arm` by `rm.v1-fall-load-cases`.
7. **`CLAUDE.md` still gives old timings.** Quick is about 5 minutes; the full suite 3424 s at memo 55. Reported at memo 56, unchanged, since I do not edit it without a task.

## T1 change set

59 YAML files changed their schema line alone: 27 records and 32 fixtures. `thread-record-1.schema.json` is unchanged.

All 56 generated files changed: 27 derived, 27 dossiers, `graph.json` and `STATUS.md`. The reason is the same for each: outputs hash the whole record, including its schema line, so each file's inputs hash moved. The diff has 112 lines, all banner or `inputs`, and no content line.

Later, T2 changed 31 generated files (load cases and segments gained `sourcing`, `evidence` and `fall_cases`) and T3 changed 6 (the load-case dossiers and `STATUS.md`).

## T0 inventory

T0 ran at memo 56 and holds: between 9dcc0b0 and the start of T1 only the memo, `docs/STATE.md` and the brief changed. Its inventory is in that memo. The only thread-reading test outside `--quick` is `checks/test_thread_checks.py`, which ran before every commit. I also ran `tests/test_envelope_cad_registry.py`, outside quick and near the CAD code: 16 passed.

## Timings

Each commit used the waiver's sequence, in order.

| Commit | Thread build | Quick suite | `checks/test_thread_checks.py` |
|---|---|---|---|
| 38cb3a1 T1 | 0.57 s | 943 passed, 307 s | 8 passed, 1.25 s |
| 258268b T2 | 0.59 s | 1006 passed, 315 s | 8 passed, 1.34 s |
| abb23b4 T3 | 0.60 s | 1023 passed, 318 s | 8 passed, 1.38 s |
| 9e5518e T4 | 0.60 s | 1040 passed, 320 s | 8 passed, 1.23 s |

## Tests added

136 in the quick set: `tests/test_thread_evidence.py`, `test_thread_stamp_rule.py` and `test_thread_sources.py` (86 tests, 9.6 s), the rest in the schema, validate and CAD tests.

## Choices the brief left open

No tolerance was chosen. These are the small ones:

- Clause digits: `D[0-9]+`.
- Evidence list: no minimum, because G5 sets it to `[]`.
- `energy_j`, velocity and mass: greater than 0.
- A cited row's banner key is the file, `#/`, and the row id with whitespace replaced, so `fy thread impact data/falls/sources.md#` finds the case.

## My mistakes

- **T4's tests were not watched failing first.** I wrote the generator in the same batch. Afterwards I ran them against the pre-T4 generator: 2 failed, 15 errors.
- **The first T3 commit failed.** A double quote in the message broke PowerShell's argument passing, and I wrote T4 on top before seeing it. T3 was still staged, unchanged since its test run, and I committed it from a message file.
- **T4's commit message says 19 work items.** The fixture has 16, measured from its intent file. I left the commit as it is; this line is the correction.
- **I overreached in CONVENTIONS during T2.** My draft also stated the stamping rule, which amendment 2 does not list. I removed it before committing; see Question 2.

## Questions for Joe

1. Sign off the G1 to G8 table? Recommended yes.
2. Add one sentence to CONVENTIONS section 3: stamping refuses active work on an unsourced case, other live consumers warn, and sourcing never changes a work status? Recommended yes.
3. Give `adr-0036` labels, or leave it uncitable? Recommended leave it; a change there is yours, and fall cases cite 0037.
4. Should a superseded load case stop being graded? Recommended no; it is the simpler rule, and no real case is affected yet.
