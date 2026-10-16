STATE: base 162af6afd822 | brief sha256:0a67a27df03a | snapshot sha256:e5cc96ceed7e | tests 864/864 | dirty yes

**Decision summary (roadmap brief 1, Part A, Checkpoint A).** The roadmap library, CLI, generated files and hook exist and pass 864 tests (720 before). Nothing in the repo's real roadmap changed: `roadmap/nodes/` is empty and `fy roadmap validate` says "no nodes".
- **Result.** On a 300-node synthetic roadmap (two seeds), a 600-node one and a 60-node one, every status the library derives equals the status the generator intended, 0 mismatches in 300+300+600+60 nodes. 26 of 26 hand-authored invalid fixtures yield exactly their one error; the exception is "no root", which cannot occur alone (it always comes with an unresolved parent) and is tested as that pair.
- **Speed.** Load, validate and derive: 0.27 s at 300 nodes, 0.55 s at 600 (warm-cache median of 7, this machine; a cold first call is not measured, see Evidence). Part B's viewer must render in under 1 s at 600 nodes, so the server's compute alone uses about half of that budget.
- **Reference values.** Brief limit: first render under 1 s at 600 nodes. Estimate cap: 3.0 days. Tests: 720 before, 864 now. Frontier on the 300-node fixture: 60 (43 ready leaves, 17 expandable stubs).
- **Decisions for you.** (1) Check results are read from `docs/STATE.md` (the only tracked, machine-readable record); a WAIVED check counts as not passed. Recommend: accept. (2) A criterion whose evidence is missing evaluates `unknown` and the node stays ready or blocked with no warning, as the brief says. Recommend: add a `criterion-unknown` warning, since a typo in a record path is otherwise silent. (3) `roadmap/roadmap.yaml` does not exist in the repo and no code reads it; the `roadmap/` row of `CONVENTIONS.md` still lists it. Recommend: drop it from the row. (4) The banner on generated roadmap files carries the snapshot hash, as section 4 requires, so every snapshot change rewrites both files at the next commit. Recommend: amend section 4 so roadmap files carry only their inputs hash. (5) Reference matching lets a sentence-ending full stop end the token (the brief's literal rule would miss "see rm.foo."). Recommend: keep.
- **What would change this.** A derived-versus-intended mismatch on any seed; or Part B finding that cold-start compute leaves too little of the 1 s budget (a cache keyed on file mtimes would address it, not a change of design).

# Roadmap brief 1, Part A: contract, library, CLI, generated files (T1 to T5)

Brief: `docs/briefs/architecture/roadmap-brief1.md`. The prompt gave prefix `f2c92f2c2ee0`; the file hashes to `13dc7c519e50…` (no CR characters, LF-normalised hash identical). I stopped and asked; Joe replied that the first line was retitled and the version at HEAD is approved, prefix `13dc7c519e50`. `CLAUDE.md` still names `docs/briefs/stage2e-brief.md` as the current brief and I did not edit it, so `docs/STATE.md` reports the stage 2e brief hash. Commits: `39edbf4` (T1), `5f9588e` (T2), `6a959ae` (T2a and T3), `162af6a` (T4 and T5). T6 to T8 (Part B) not started.

## Findings

1. **Conflicts with `CONVENTIONS.md`, and how each was resolved.**
   - Tests location: the brief says `tests/` holds bench-run records and to put pytest tests elsewhere. Section 7 of `CONVENTIONS.md` says the old unittest suites now live in `tests/`, `pytest.ini` collects `tests/` and `checks/`, and `tests/` has 39 `test_*.py` files before this work and no run records. Section 2's `fea/`, `tests/` row is the stale one. I put the tests in `tests/` (`test_roadmap_*.py`, helper `rmhelp.py`, invalid fixtures under `tests/fixtures/roadmap/invalid/`). The section 2 row for `tests/` should be reworded; I did not touch it.
   - Banner: section 4 requires `(snapshot sha256:<12 hex>)`; the roadmap does not depend on the snapshot. Following section 4, banners read `(snapshot sha256:<12 or none>, inputs sha256:<12>)`, the second being a hash over the node files and every file a `done_when` reads. For JSON, section 4 asks for `generated_by` and `inputs` keys and the brief asks for `_generated`; `state.json` carries all three.
   - Schema file names: the brief says `roadmap-node-1.json` and `roadmap-state-1.json`; the four existing schemas are `*.schema.json`. I followed the brief.
   - Terms: the brief says to define the terms "wherever `CONVENTIONS.md` defines terms"; it has no glossary, so section 3 gained a "Roadmap terms" paragraph. For the `docs/OVERVIEW.md` glossary (not mine to edit): **node** (one file in `roadmap/nodes/`), **interior** (has children, no criterion), **leaf** (childless, has `done_when` and `estimate_days`), **stub** (childless placeholder, `stub: true`), **`done_when`** (a leaf's completion criterion; not a "gate"), **frontier** (ready leaves plus expandable stubs, sorted by id).
   - Amendment 3 of the brief puts the `rm.` ID row in section 3; section 3 has no conflicting ID kind. The new rule for Code is rule 8 of section 9.
2. **`roadmap/roadmap.yaml`.** It is not in the repo: `git ls-files roadmap` lists only `roadmap/README.md` (empty). I did not read or touch anything. Files that mention "roadmap": `CONVENTIONS.md` and the brief only. No Python, YAML or command file reads it. Joe decides its retirement.
3. **Where check results are recorded.** `checks/last_run.json` is gitignored (not reproducible from a commit). `docs/STATE.md` is tracked and lists `- <id> | <tier> | <STATUS>` under `## Checks`. The `check` type reads that. Consequences: a check's roadmap status is only as fresh as the last `fy state`; `STATE.md` written with `--no-run` says "not run" and the criterion evaluates `unknown`; PASS is the only passing value, so a WAIVED check (the one waiver today, `check.mjcf.com_pct_stature`) is not a pass.
4. **Decision records.** `CONVENTIONS.md` section 8 gives them a `status` front-matter field, so the `decision` type passes on `status: accepted`. A record with no parseable front matter status is `unknown`. Note the template's `superseded-by: adr-NNNN` is not valid YAML unquoted; it evaluates `unknown`, not `fail`, until it is quoted. Both mean "not done".
5. **Shape rules where the brief is silent, and what I chose.**
   - A node whose children are all superseded counts as childless (it then needs `done_when` and `estimate_days`, or `stub: true`).
   - A superseded node is exempt from the leaf, stub and interior field rules.
   - An interior node whose children are all done is `done` even when its own blockers are uncleared (rule 1 precedes rule 2); no warning, since the brief lists the warning for leaves only.
   - A superseded blocker, or one that does not resolve, is never cleared.
   - The `done_when` paths are validated by the schema as relative without `..`, and again at evaluation; an escaping path evaluates `unknown`.
   - A metric compares floats exactly for `==`.
   - Fixture "size N" counts all node files, including about 5% superseded; the statuses `node_count` excludes superseded.
6. **Reference matching.** The brief's rule (bounded by characters outside `[a-z0-9_.-]`) would not match `rm.foo.` at the end of a sentence, because `.` is in the set. I allow a trailing `.` that is not followed by another id character, so `rm.foo.bar` and `rm.foo-bar` still do not match. Tested. One line to revert (`refs.token_re`).
7. **Hook.** Tested in a throwaway repository with its own copy of `tools/`, offline, under Git for Windows' `sh` (the tests did not skip). It commits a valid roadmap with exactly `roadmap/state.json` and `roadmap/STATUS.md` staged and an unrelated untracked file left alone, and it blocks a commit containing an unresolved parent with the error text in the output and the generated files untouched. **Not exercised:** the `.venv` branch of the hook (tests set `FREYJA_PYTHON`, an extra variable I added so tests do not depend on the machine's Python; a text check pins that the script mentions `.venv`). I did not run the hook in this repo and I did not run `install-hooks` here; `core.hooksPath` is unset in this clone.
8. **Process.** The suite ran in full once after all code was written (865 passed) and again before the last code commit (864 passed, after I removed one misplaced test). The earlier three commits hold subsets of that tree and were checked by running their own test files; I did not run the full suite before each of them (about 3.7 minutes each). T4 and T5 are one commit because `cli.py`'s `build` calls `render.py`. T2 and T3 are split differently from the brief's tasks for the same reason (the derivation is part of the library), and T3's tests arrived with T2 and T2a.

## My mistakes

- Commit `6a959ae` first said "40 passed"; the run said 42. I amended my own unpushed commit message.
- Two test edits before the first commit: one tautological assertion and an `or True` I left in a draft, both removed. Neither was ever in a commit.
- I wrote `test_on_errors_nothing_is_built` into the validate tests although it needs the renderer; found when I split commits and moved it (render tests already cover it).
- `STATE.md` shows the stage 2e brief because `CLAUDE.md` was not edited (finding in the header paragraph); that is not a mistake in the state tool.

## Evidence

**Validation, one fixture per class** (`fy roadmap validate --root tests/fixtures/roadmap/invalid/<name>`; message abbreviated; all exit 1; each ends "1 errors, 0 warnings" except no-root).

| fixture | code | message |
|---|---|---|
| schema-unknown-field | schema | `rm.ok.md`: Additional properties are not allowed ('colour' was unexpected) |
| schema-missing-title | schema | `rm.ok.md`: 'title' is a required property |
| filename-id | filename-id | `rm.ok.md`: filename stem 'rm.ok' differs from id 'rm.other' |
| id-format | id-format | `rm.Bad_Id.md`: id 'rm.Bad_Id' does not match rm.<lowercase letters, digits, hyphens> |
| no-root | no-root, parent-unresolved | no root; rm.a has parent rm.ghost, which does not exist (2 errors) |
| multiple-roots | multiple-roots | more than one root: rm.root, rm.second |
| parent-unresolved | parent-unresolved | rm.x has parent rm.ghost, which does not exist |
| parent-cycle | parent-cycle | rm.c1 -> rm.c2 -> rm.c1 |
| blocker-unresolved | blocker-unresolved | rm.x is blocked by rm.ghost, which does not exist |
| blocked-self / -ancestor / -descendant | blocked-relative | blocked by itself / by its ancestor rm.grp / by its descendant rm.g1 |
| blocked-by-superseded | blocked-by-superseded | rm.x is blocked by rm.old, which is superseded by rm.keep |
| blocking-cycle | blocking-cycle | rm.p -> rm.q -> rm.p |
| blocking-cycle-interior | blocking-cycle | rm.g1 -> rm.x -> rm.g1 (x blocked by the interior rm.grp, which expands to rm.g1) |
| blocking-cycle-inherited | blocking-cycle | rm.g1 -> rm.x -> rm.g1 (rm.g1 inherits rm.grp's blocker rm.x) |
| interior-has-stub / -done-when / -estimate | interior-forbidden | rm.grp has children, so it may not carry stub: true / done_when / estimate_days |
| leaf-missing-done-when / -estimate | leaf-incomplete | rm.x has no children and is not a stub, so it needs done_when / estimate_days |
| stub-has-done-when / -estimate | stub-forbidden | stub rm.x may not carry done_when / estimate_days |
| superseded-by-unresolved | superseded-by-unresolved | rm.old is superseded by rm.ghost, which does not exist |
| superseded-by-superseded | superseded-by-superseded | rm.old1 is superseded by rm.old2, which is itself superseded |
| superseded-live-children | superseded-live-children | rm.old is superseded but has children that are not: rm.child |

Every message names its ids and its repo-relative file paths (a test asserts both).

**`show`, 300-node fixture (seed 0)**, trimmed:

```
rm.n000-root > rm.n001-cable > rm.n002-gearbox > rm.n009-wrist > rm.n014-pelvis > rm.n017-mount > rm.n028-cable > rm.n039-controller > rm.n279-femur
Femur 279 benchmarked on the bench
  kind:    leaf
  status:  blocked (blocked by rm.n043-battery, rm.n197-cooling)
  estimate: 1.5 days     tags: power
  done_when: decision: decisions/0038-n279-femur.md
  evaluation: fail - decisions/0038-n279-femur.md has status superseded-by: adr-9999
  effective blockers (2): rm.n043-battery, rm.n197-cooling      dependents (0)
  references (1 in files, 0 in commits): log/events.log:111: event 110 touched rm.n279-femur and rm.n279-femur-extra

rm.n000-root > rm.n001-cable > ... > rm.n031-bearing > rm.n090-harness
Harness 090 fitted inside the envelope
  kind:    interior       status:  in_progress (2 leaves done, 1 active below)       done_when: none
  children (3):  rm.n155-encoder [done]   rm.n167-femur [active]   rm.n212-controller [done]

rm.n000-root > rm.n001-cable > rm.n008-pelvis
Pelvis 008 assembled and torque tested
  kind:    stub           status:  expandable (stub not yet decomposed)               done_when: none
```

**Frontier** (300-node fixture): 60 = 43 ready leaves + 17 expandable stubs, of 285 live nodes (15 superseded). First ids: `rm.n008-pelvis` (stub), `rm.n012-spring` (manual, 1.5 d), `rm.n029-sensor` (metric `/result/value > 4.77`, 1.5 d), `rm.n040-mount` (stub), `rm.n043-battery` (check, 3 d). Counts by status: done 70, in_progress 35, active 20, ready 43, expandable 17, blocked 84, not_started 16.

**Timing** (this machine, Windows; medians of 7):

| nodes (files) | load + validate + derive | `state.json` + `STATUS.md` text | generate fixture |
|---|---|---|---|
| 300 | 0.265 s | 0.58 s | 0.39 s |
| 600 | 0.554 s (one of the 7 runs took 2.9 s; I did not find out why) | 1.17 s | 0.81 s |

A warm second call of the 300-node compute under the profiler takes 0.54 s (profiler overhead included): YAML load 0.09 s, file opens 0.03 s. My first profile, of a first call right after the fixture was written and before I switched to PyYAML's C loader, took 1.84 s, of which 0.76 s was `io.open` over 419 files (about 1.8 ms each) and 0.65 s YAML parsing. **I have not re-measured a cold first call with the C loader**, and Part B's server will pay that cost on its first request, so the 1 s budget at 600 nodes is not yet shown to hold from cold. The render figure includes reading and hashing every node file and every record for the banner; it is the build's cost, not the server's.

**Reference search** on the 300-node fixture: 112 of 300 ids have at least one file reference, 178 file hits in total, at most 3 per id; scanning for all 300 ids takes 0.52 s. The fixture's log lines include `rm.x-extra` distractors, and the unit test shows they do not count as references to `rm.x`. Commit search returns nothing on a fixture (not a git repository); on a git root it uses `git log --fixed-strings --grep`, then re-checks the full message with the token rule, tested on a throwaway repository (a commit whose body mentions only `rm.foo-bar` is not a reference to `rm.foo`).

**Fixture coverage** (test asserts, seeds 0 and 7, 300 nodes): all of done, blocked, active, ready, expandable, in_progress, not_started and superseded appear; maximum depth is 8 (asserted between 6 and 8); at least 20 blocking edges between nodes with different parents (178 edges in total in seed 0); all five criterion types; its own `decisions/`, metric and artifact records, a `docs/STATE.md` check list, and log, memo and notebook files. The generator does not import the library (an AST test pins it).

**Library location:** `tools/roadmap/` (`model`, `validate`, `evaluate`, `derive`, `render`, `refs`, `query`, `editor`, `fixture`, `cli`); `tools/fy/cli.py` gained a small `roadmap` wrapper (12 lines). Tests: 144 new, counted by `pytest --collect-only` per file (schema 40, derive 13, evaluate 16, refs/query 8, validate 32, fixture 10, render 9, cli 16); full suite 864 passed.

## Tolerances and constants I chose

- `ESTIMATE_CAP_DAYS = 3.0` (the brief's cap), one named constant in `model.py`.
- `MERMAID_CAP = 40` (the brief's cap), `render.py`.
- `MAX_CANDIDATES = 10` for query candidates (the brief's number).
- No numeric tolerance was tuned toward a result. Fixture generator weights (leaf intent mix 0.32 done, 0.22 ready, 0.10 active, 0.36 blocked; 12% stubs; attachment weights) were set once so that all statuses and depth 6 to 8 appear; they change what the fixture looks like, not what any check accepts.

## Not done, by the brief's scope

Part B (notification workflow, server, viewer), staleness detection, any real roadmap content, the weekly report. `STATUS.md` and `state.json` for the real (empty) roadmap are not committed; the hook will create them at the first commit after `install-hooks`.

## Questions for Joe

1. The five decisions in the summary.
2. Run `python tools/fy roadmap install-hooks` in each clone. Until then nothing rebuilds the generated files.
3. Go-ahead for Part B (T6 to T8). The GitHub Actions prerequisites in the brief are yours.
