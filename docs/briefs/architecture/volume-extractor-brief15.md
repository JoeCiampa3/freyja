# Brief (for Claude Code): commit ADR 0008, the elbow and upper-arm load basis

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives. Everything above the line `BEGIN ADR 0008` in this message is this brief. The block between `BEGIN ADR 0008` and `END ADR 0008` is the record, not part of the brief.

## Purpose

Joe and Claude drafted ADR 0008 in chat and Joe approved it. This brief files the brief and commits the record. It does nothing else.

## Out of scope

- Editing the record text. Write it byte for byte. If you think something is wrong, say so in the final message.
- Any node file, `roadmap/` file you do not regenerate through the hook, thread record, tool, test, sheet, snapshot or other decision record. In particular do not edit ADR 0037, do not add or edit any roadmap node, and do not create any `lc.*` record.
- The follow-ups below. They are recorded, not acted on.

## Ground rules

`CONVENTIONS.md` section 9 and the `CLAUDE.md` session rules apply, with one waiver from Joe for this brief only. This brief adds one markdown file and files itself; it changes no code, test, schema or generated input. So `CLAUDE.md` rule 1's `fy test --quick` on every commit, its full-suite trigger, and the `fy state` run are waived. Run the targeted tests in T2 instead and name them in the commit message as the waiver Joe granted. Do not run `fy test`, `fy test --quick` or `fy state`. No new dependencies. Stage files by explicit path and read `git diff --cached --stat` before each commit. Never set `signed_off`.

## T1. Save this brief

Save everything above the `BEGIN ADR 0008` marker, including the follow-up list below, as the next brief. Follow `CLAUDE.md`'s rule for the current brief of this track. If it does not settle the name, use the next unused number in `docs/briefs/architecture/volume-extractor-brief<N>.md` and say so in the commit message. Commit it alone. Run no tests for this commit (only `docs/briefs/` changes; the hook still runs).

## T2. Commit the record

Write the text between the markers, excluding the marker lines, to `decisions/0008-elbow-load-basis.md`. LF line endings, one trailing newline, no timestamps or absolute paths. Check that the front matter parses (id `adr-0008`, status `accepted`, date `2026-10-31`, links as written). If `decisions/README.md` indexes the records, add the 0008 line in the same commit and report it; otherwise change nothing else.

Before committing run exactly these and no others:

python -m pytest tests/test_conventions.py tests/test_roadmap_validate.py tests/test_roadmap_evaluate.py tests/test_roadmap_derive.py

The pre-commit hook rebuilds the roadmap files. If it changes tracked generated files, include exactly those in this commit and say so in the commit message. If it changes anything else, or any of the four test files fails, stop and report.

## Reporting

There is no checkpoint and no memo. End with a final message of at most six lines: the brief's filename and commit, the record's commit, the test result, whether the hook changed any file, whether `decisions/README.md` changed, and any disagreement with the record text. The 15-line decision summary of `CLAUDE.md` rule 6 and the STATE line are waived for this brief.

## Follow-ups (record only; do not act)

1. `rm.v1-upper-arm-characterized`: add a line that elbow-position quantities in the characterization file carry 0042 D2's 7 mm anteroposterior bar.
2. Brief 11 (raster-grid change) runs separately and may move envelope volumes by about 0.1 mm. 0008 depends on no envelope volume. The 32.5 mm and 16.25 mm figures in it are illustrative.
3. A committed script under `analysis/` that reproduces the arm fall-energy band (D5) and the static and swing torques (D2, D3) from `params/snapshot.csv`, with a mutation-tested check.
4. A 0037 Revisions entry under D1(d) replacing the arm's 0.50 m drop (320 J) with D5's band, design 430 J, using the snapshot's centre of mass in place of 0.935 m, and stating the three tests.
5. The first-cap Revisions entry for the hand-and-arm zone at 20 kN, deferred until the room is cited from `data/envelope/`. The mass claim stays at 0.15 kg per unit until then.
6. `rm.v1-shoulder-concept`: the thorax-shoulder stroke requirement (45 mm posteromedial and anteromedial at η ≥ 0.6, plus 0037's 57 mm superomedial), the shoulder actuator and drivetrain not in the fall load path, the mount moment rating (illustrative 2.7 kN·m at the 30 kN rating), and the interface record (`if.*`) carrying direction, rated force, stroke and engagement gap per 0037 D6.
7. The sternal pivot (SC joint) position is not in the repo and is needed for the arc.
8. `rm.v1-thread-budgets`: the stroke as a volume reservation on the thorax.
9. The sheet: a functional-target row of 157° for elbow flexion with its Magermans provenance (ADR 0002 rule 6).
10. Sources: obtain Morrey's functional arc and re-check against the PDFs the Magermans Table 4 and Simon-Martinez Table 1 values, Soucie's 4.7° and 150°, and the Flash and Hogan profile constants.
11. Pin the stack-axis offset from the snapshot's standing pose and model foot slip, replacing the 0.09 to 0.195 m bracket in D5.
12. ADR 0009 takes the D7 table as its input.
13. First CAD part: the elbow stop and upper-arm column rated to 30 kN axial and the couple across the stop faces (about 320 N·m at the rating); bearing static ratings from the catalog.
14. Decide ADR 0002 rule 7's mass tolerance (it gates D2's validity).
