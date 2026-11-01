# Brief (for Claude Code): two factual corrections, ADR 0037 and ADR 0008

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives. This whole message is the brief.

## Purpose

Your report on commit 1b70715 found that ADR 0037's second Revisions entry says the hand drop height does not use h_standing, which is wrong for the arm (adr-0008 D5 starts from 0.942 m), and that D3's calibration text and Consequences still cite 320 J and 67 mm for the arm. Separately, Joe decided that the backward single-arm stroke in adr-0008 D6(c) is an assumption equal to the forward one. This brief makes three edits in place and logs them, per CONVENTIONS section 8 (factual correction, logged under Amendments). No value or decision changes.

## Out of scope

Anything but `decisions/0037-fall-design-basis.md`, `decisions/0008-elbow-load-basis.md` and this brief's own file. Do not edit D3's table or text, the Consequences of 0037, any node, thread record, tool or test.

## Ground rules

`CONVENTIONS.md` section 9 and `CLAUDE.md` apply, with Joe's waiver for this brief only, as for briefs 15 to 17: `fy test`, `fy test --quick` and `fy state` are not run; the four targeted tests below are. No new dependencies. Stage by explicit path and read `git diff --cached --stat` before each commit. Use the editor tool for edits, not a heredoc. Each old string below must occur exactly once; if not, stop and report. Where the hook adds generated files to a commit, name them in the commit message.

## T1. Save this brief

Save this message as `docs/briefs/architecture/volume-extractor-brief18.md` (or the next unused number if that name is taken). Commit it alone, no tests.

## T2. ADR 0037

Edit 1, in place. In the second Revisions entry of 2026-10-31 (the one that begins "D1(b), centre-of-mass height"), replace:

so no zone's E_design in D3 changes, and the knee and hand drop heights do not use h_standing.

with:

so no zone's E_design in D3 changes.

Edit 2. At the end of the file, after the last Revisions entry and one blank line, add the heading `## Amendments` if the file has none, then this bullet; if the heading exists, append the bullet to it:

- 2026-10-31. Factual correction and pointer; no decision changes. (1) The second Revisions entry of this date said that the knee and hand drop heights do not use h_standing. That was not checked when it was written, and it is wrong for the hand and arm: under the first Revisions entry their energy starts from the standing centre of mass, 0.942 m, not from a chosen drop height (adr-0008 D5). No number changes, since 430 J was computed at 0.942 m. The clause is removed; whether the knee's drop height uses h_standing is not asserted. (2) D3's calibration text and Consequences still cite 320 J and 67 mm at 10 kN for the hand and arm; for that zone they are superseded by the first Revisions entry of 2026-10-31 and are left as history. Cause: Claude Code's final message on commit 1b70715.

LF endings, one trailing newline. Run exactly:

python -m pytest tests/test_conventions.py tests/test_roadmap_validate.py tests/test_roadmap_evaluate.py tests/test_roadmap_derive.py

Commit alone, naming the waiver. If the hook changes anything beyond tracked generated roadmap files, or a test fails, stop and report.

## T3. ADR 0008

Edit 1, in place. In D6(c), replace:

This record owns 45 mm in those two directions.

with:

This record owns 45 mm in those two directions. The forward value is derived in D5; the backward value is assumed equal [design: assumed. A rough check with the heel as pivot (0.062 m behind the ankle [source: snapshot foot_heel_behind_ankle]), wrist reach and the cone edge gives 420 to 427 J against the forward 422 J, so the same 430 J and 45 mm stand. The check is not in D5 or a committed script, and it applies only to arms leaning toward the feet: the sheet's 57.3° of shoulder extension excludes arm poses within about 15° of vertical in a backward fall].

Edit 2. Append to the existing `## Amendments` section, after its last bullet:

- 2026-10-31. D6(c): the backward 45 mm was stated as owned without a derivation. It is now labelled an assumption equal to the forward value, with the rough check noted. No decision changes. Cause: Claude's check against brief 17's follow-up 1, after Joe decided to assume it.

Run the same four tests. Commit alone, naming the waiver.

## Reporting

No checkpoint and no memo. End with a final message of at most five lines: the three commits, the test results, whether the hook changed any file, and any disagreement.

## Follow-ups (record only; do not act)

1. The committed script (brief 15, follow-up 3) should also cover the backward fall about the heel, with the stack-offset bracket stated.
2. rm.v1-shoulder-concept: a backward single-arm arrest needs about 30° of shoulder extension at the cone edge and excludes arms within about 15° of vertical, against the sheet's 57.3°. The shoulder's range and the compliant arc must not preclude those poses.
3. Brief 17's follow-ups 2 and 3 stand (first-cap entry waits for the room; rm.v1-fall-load-cases creates the lc.fall-* records).
