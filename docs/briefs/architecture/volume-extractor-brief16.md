# Brief (for Claude Code): amend ADR 0008 D5 (factual correction)

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives. This whole message is the brief.

## Purpose

Your report on commit 539e001 found that D5's stated band edges do not match its stated reach. Joe and Claude agree, and Claude found a related error in the lateral gap. This brief corrects the text in place and logs it, per CONVENTIONS section 8 (factual correction). No decision changes.

## Out of scope

Anything but `decisions/0008-elbow-load-basis.md` and this brief's own file. Do not touch CLAUDE.md, ADR 0037, any node, thread record, tool or test.

## Ground rules

`CONVENTIONS.md` section 9 and `CLAUDE.md` apply, with Joe's waiver for this brief only, as for brief 15: `fy test`, `fy test --quick` and `fy state` are not run; the targeted tests below are. No new dependencies. Stage by explicit path and read `git diff --cached --stat` before each commit. Use the editor tool for the edits, not a heredoc.

## T1. Save this brief

Save this message as `docs/briefs/architecture/volume-extractor-brief16.md`. Commit it alone, no tests.

## T2. Edit the record in place

In `decisions/0008-elbow-load-basis.md`, make these two replacements. Each old string must occur exactly once; if not, stop and report.

Replacement 1. Old:

- Reach from the shoulder to the contact point 0.515 m, the wrist [design: the v1 hand is a placeholder; reach to the end of the hand node, 0.589 m, lowers the energy by about 25 to 30 J].

New:

- Reach from the shoulder to the contact point: 0.515 m, the wrist, is the design case; 0.589 m, the end of the hand node, is the lower case [design: the v1 hand is a placeholder; the longer reach lowers the energy by 24 to 33 J at the same pose and pivot].

Replacement 2. Old, from "Results [derived]." to "never governs the arm.":

Results [derived]. Forward fall: arm straight down at contact 302 to 355 J; β = 27° (μ = 0.5) 331 to 380 J; β = 45° (μ = 1.0) 378 to 422 J. A lateral fall about the outer foot edge gives 238 to 331 J across the same cone, 65 to 105 J below the forward fall at the same angle, so it never governs the arm.

New:

Results [derived]. Each range spans both reaches and the stack bracket: the low edge is the 0.589 m reach with the 0.195 m offset, the high edge the 0.515 m reach with the 0.09 m offset. Forward fall: arm straight down at contact 302 to 355 J; β = 27° (μ = 0.5) 331 to 380 J; β = 45° (μ = 1.0) 378 to 422 J. At the wrist reach alone, the design case, these are 335 to 355 J, 360 to 380 J and 402 to 422 J. A lateral fall about the outer foot edge gives 238 to 331 J across the same cone (268 to 331 J at the wrist reach), 64 to 91 J below the forward fall at the same angle, reach and bracket, so it never governs the arm.

Then append this section at the end of the file, after the last Rejected option, with one blank line before the heading, LF endings and one trailing newline:

## Amendments

- 2026-10-31. Factual correction to D5; no decision changes. (1) The stated low edges of the forward band (302, 331, 378 J) were computed with the 0.589 m reach and the 0.195 m stack offset, while the text gave the model reach as 0.515 m. The text now says each range spans both reaches and gives the wrist-reach ranges. (2) The effect of the longer reach is 24 to 33 J, not about 25 to 30 J. (3) The lateral band is 64 to 91 J below the forward fall within the stated bracket, not 65 to 105 J (the upper figure used an unbracketed zero offset), and is 268 to 331 J at the wrist reach. The upper edge, 422 J, and the design energy, 430 J, are unchanged. Cause: Claude Code's final message on commit 539e001, which recomputed D5, and Claude's check of the lateral gap against the same table. No memo; the brief waived it.

Before committing run exactly:

python -m pytest tests/test_conventions.py tests/test_roadmap_validate.py tests/test_roadmap_evaluate.py tests/test_roadmap_derive.py

The pre-commit hook rebuilds the roadmap files. If it changes tracked generated files, include exactly those; if it changes anything else, or a test fails, stop and report. Commit alone, naming the waiver in the message.

## Reporting

No checkpoint and no memo. End with a final message of at most five lines: the two commits, the test result, whether the hook changed any file, and any disagreement.
