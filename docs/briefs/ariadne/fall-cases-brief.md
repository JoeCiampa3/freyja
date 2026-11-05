# Fall cases brief (for Claude Code): the seven fall load cases of rm.v1-fall-cases-recorded

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `decisions/0036-fall-intent.md`, `decisions/0037-fall-design-basis.md` (all of it, including Revisions and Amendments), `decisions/0044-fall-zone-caps.md`, `decisions/0008-elbow-load-basis.md` D5 and D6, and `docs/briefs/ariadne/thread-sources-brief.md` (the evidence mechanism this uses). This brief belongs to the Ariadne track. It specifies `rm.v1-fall-cases-recorded` and closes when Joe signs off the memo.

Tag: Delegate.

## Purpose

`rm.v1-thread-sources` made the thread hold evidence on a load case and refuse to stamp active work on a flagged case without it. No fall case exists yet. This writes the first seven, in the energy-defined form of `thread-record/2` (adr-0037 D1(a)), so that `rm.v1-upper-arm-characterized` and the other segments have fall cases to read.

A case carries a zone, a direction, a design energy and the evidence for it. It never carries a force, a cap or a stroke. Force is an output of adr-0037 D2, and each zone's cap is set later by the record that designs its stroke home (adr-0044 D2, D3). The record then gains that record as evidence.

## What this run does not do

- It writes no eighth case. The arm's backward case is `rm.v1-fall-case-arm-backward`, which waits on adr-0025.
- It writes no `part.<segment>.fall-reserve` record (`rm.v1-fall-reserves-recorded`, deferred).
- It edits no decision record, no roadmap node, no schema, no library code, no `CONVENTIONS.md` and no existing thread record. It creates no work item and stamps nothing.
- It computes no energy. Every number in the table below is typed from the cited decision, and the memo shows each beside the number in the clause.
- It runs no simulation.

## Gate criteria

Stated before the work. Each is reported in the memo as pass or fail with its numbers, and Joe signs off the memo's gate table. Do not change a criterion to make a result pass; a criterion that looks wrong is a finding.

**G1. Clean build.** After the records land, `python tools/fy thread build` reports 0 errors and 0 warnings. The real store held 27 records at memo 57 and holds 34 after this brief.

**G2. All sourced.** Every one of the seven cases derives `sourcing: sourced`, and every evidence entry on each is resolved and admissible, read from `thread/derived/<id>.json`, not from the record.

**G3. Segments see them.** The derived `fall_cases` of each housing segment lists exactly its cases: `seg.thorax` 3 (`lc.fall-shoulder-lateral`, `lc.fall-back-backward`, `lc.fall-chest-forward`), `seg.pelvis` 2 (`lc.fall-hip-lateral`, `lc.fall-buttock-backward`), `seg.thigh` 1 (`lc.fall-knee-forward`), `seg.upper_arm` 1 (`lc.fall-hand-arm`). No other segment lists a fall case.

**G4. Nothing else moved.** The 27 existing records are byte-identical. No work status changes (`work.upper-arm-cad` stays `current`), and there is no `unsourced-consumption` warning. The generated files that changed are the new cases' derived files and dossiers, the four segments' derived files and dossiers, `thread/graph.json` and `thread/STATUS.md`, and nothing else. Any other changed generated file is a finding. The memo lists every one with its reason.

**G5. Numbers match their clauses.** The memo carries one table: case, `energy_j` as recorded, the number in the cited clause as read from the decision file (quoting at most the table cell), and equal or not. Seven of seven equal. Any mismatch is a finding, and the record follows the decision.

## The cases

Each is `thread-record/2`, `kind: load_case`, `status: proposed`, `independent_source_required: true`, with `source` in the energy-defined form. Write them as block YAML in the style of the existing load-case records (sorted keys, LF). The `zone` is a slug.

| id | zone | direction | energy_j | energy_basis | zone_in | evidence |
|---|---|---|---|---|---|---|
| `lc.fall-hip-lateral` | `hip` | lateral, hip first | 540 | E_max | `seg.pelvis` | adr-0037 D1(b) |
| `lc.fall-shoulder-lateral` | `shoulder` | lateral, shoulder first | 540 | E_max | `seg.thorax` | adr-0037 D1(b) |
| `lc.fall-buttock-backward` | `buttock` | backward, buttock first | 540 | E_max | `seg.pelvis` | adr-0037 D1(b) |
| `lc.fall-back-backward` | `back` | backward, back first | 540 | E_max | `seg.thorax` | adr-0037 D1(b) |
| `lc.fall-chest-forward` | `chest` | forward, chest first, with the arm not arresting | 540 | E_max | `seg.thorax` | adr-0037 D1(b); adr-0044 D1 |
| `lc.fall-knee-forward` | `knee` | forward collapse onto one knee | 260 | centre of mass drops 0.40 m | `seg.thigh` | adr-0037 D1(c); adr-0037 D3 |
| `lc.fall-hand-arm` | `hand-arm` | arrest on one arm, forward or sideways; no sharing | 430 | geometric drop, one arm, friction cone mu = 1.0 (adr-0008 D5) | `seg.upper_arm` | adr-0037 D3; adr-0008 D5 |

Each evidence entry is `{kind: decision, record: adr-NNNN, clause: D<n>(<letter>)}`, one entry per row of the evidence column. Energies and directions are those of adr-0037 D3 as revised on 2026-10-31 (the arm's 430 J is its first Revisions entry), and of adr-0044 D1 for the chest.

**Each record's `purpose`** is one sentence naming the fall (for example "Lateral fall from standing, hip first."). **Each record's `notes`** carries what the grade does not say. Required content, in the register of `CLAUDE.md` rule 9:

- *Every case.* The energy is a design upper edge, not a measurement. Its zone has no cap yet, and the cap and stroke are set by the owning record (adr-0044 D3): `rm.v1-pelvis-structure` for hip and buttock, `rm.v1-torso-structure` for back and chest, `rm.v1-shoulder-concept` for shoulder and hand-arm, `rm.v1-knee-concept-adr` for knee. No energy is shared between zones or between limbs without a verified source (adr-0037 D1(c)).
- *The E_max cases (hip, shoulder, buttock, back, chest).* 540 J is the upper edge of the energy bound of adr-0037 D1(b), 473 to 537 J after its 2026-10-31 Revisions, rounded up to the next 10 J. No credit for leg buckling or bracing (adr-0036).
- *Hip, in addition.* S1 and S11 of `data/falls/sources.md` (both Verified) put the energy at 212 to 257 J and 107 to 163 J. They are calibration, they lower nothing until Freyja's own effective mass at the trochanter exists (adr-0037 D3, calibration, hip), and they are deliberately not in `evidence`.
- *Chest.* Its scenario is a forward fall that the arm does not arrest, beyond adr-0008 D5's friction cone or short of the floor (adr-0044 D1).
- *Knee.* 260 J rests on a centre-of-mass drop of 0.40 m chosen in adr-0037 D3 and tagged [design]; nothing sources it. adr-0037 Consequences gives about 360 J for a 0.55 m drop.
- *Hand-arm.* 430 J is the upper edge of a pivot model about the toe: forward fall, arm straight at the friction cone's edge (45 degrees, mu = 1.0, [design], no source), band 378 to 422 J, rounded up. The model does not cover foot slip, and a slipping fall can reach E_max. The lateral band, 238 to 331 J, lies below, so this one case covers forward and sideways. The backward arrest is a separate case.

Do not put S1 or S11 or any Unverified row in `evidence`. Do not cite adr-0036: it has no `D<n>` labels and cannot be cited (memo 57, finding 2).

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply in full, rule 10 on coupled tasks included. Records are created `proposed` only. No new dependencies. The hook builds the thread on every commit, so a record that fails to load blocks the commit.

**Test-run waiver (proposed; Joe approves it by committing this brief).** This brief adds seven records, one test and generated thread outputs, and changes no library code. The sequence before every commit is, in order: `python tools/fy thread build`, `python tools/fy test --quick`, then `python -m pytest checks/test_thread_checks.py` (it reads the real store, and `--quick` does not collect it; zero collected is a failure). The full suite is not run by this brief or at its checkpoint (`fy state --no-run`). The first later commit that `CLAUDE.md` rule 1 covers runs it. A commit that touches anything outside the new records, the new test, the memo and generated thread outputs loses the waiver, and its message says so.

Stop and ask before: citing anything beyond the table's evidence; setting `independent_source_required` false; adding a field, a kind or a schema change; any energy that differs from its clause.

Report as a finding, and stop if it blocks a task: a cited decision whose status is not `accepted` or whose body lacks the clause's `D<n>` label (the build reports `evidence-clause` or `evidence-unresolved`); a housing segment that does not exist; a warning from the build; any record whose zone slug the schema rejects.

## Tasks

**T0. Baseline.** Run `python tools/fy thread build` and `python tools/fy test --quick`. Record the counts, the warnings and the timings. Check that adr-0008, adr-0037 and adr-0044 are `accepted`, that each cited `D<n>` label is in its record's body, and that `seg.pelvis`, `seg.thorax`, `seg.thigh` and `seg.upper_arm` exist. Nothing is committed.

**T1. Test and records (one commit; the test cannot be committed failing).** Write `tests/test_fall_cases.py` first and show it failing in the commit message with no records present. It reads the real store and asserts, for each of the seven ids: the record exists and is `proposed`; the flag is true; `source.zone`, `source.direction` and `zone_in` are those of the table; the evidence entries are exactly the table's; the derived document says `sourced` with every entry resolved and admissible. It asserts that each housing segment's `fall_cases` is exactly the set of G3, and that no other record is a fall case. It does not restate the energies: those are checked against the decisions in the memo (G5), because a typed copy of a decision's number in a test is a second home for it. Then write the records and make the test pass. The mutation check: with one evidence clause changed to a label the decision does not carry, the test and the build fail.

**Checkpoint.** Write the memo per `CLAUDE.md` rule 6, numbered next free in `docs/memos/`. Include the gate table G1 to G5 with its numbers, the G5 table, the list of changed generated files with reasons, the timings, every finding, and the questions for Joe. Run `fy state --no-run` and stop.

## Decisions this brief makes (Joe approves them by committing it)

1. Seven cases now. The arm's backward case waits on adr-0025 (`rm.v1-fall-case-arm-backward`), and the reservation records wait on `rm.v1-fall-reserves-recorded`.
2. One arm case covers forward and sideways at 430 J, because adr-0008 D5 puts the lateral arrest below the forward band and says it never governs the arm.
3. Evidence is the accepted decision that carries the number. "Sourced" then means the decision exists and is accepted, not that the number is validated, and each record's `notes` says so.
4. S1 and S11 stay out of `evidence`; they calibrate and lower nothing.
5. The test-run waiver above.

## Prerequisites for Joe

- Point the "Current Ariadne brief" line in `CLAUDE.md` at this file.
- Commit this brief.
- Prompt Code with this brief's path and its `sha256sum` prefix.
- After the memo, sign off `rm.v1-fall-cases-recorded` (`signed_off: true`) if the gates hold. Code never sets it.
