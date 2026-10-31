# Brief (for Claude Code): ADR 0037 Revisions entries for the arm's energy basis and the centre of mass

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives. This whole message is the brief.

## Purpose

ADR 0037 D1(d) allows dated amendments under Revisions to the energy basis. ADR 0008 D5 (as amended 2026-10-31) derived the arm's energy, and ADR 0037's hand-and-arm row still carries the placeholder it replaces. This brief adds two Revisions entries to ADR 0037. It changes no value in the Decision section.

## Out of scope

Anything but `decisions/0037-fall-design-basis.md` and this brief's own file. Do not edit the D3 table row (the entries supersede it), ADR 0008, any node, thread record, tool or test. Do not enter a cap for the hand-and-arm zone.

## Ground rules

`CONVENTIONS.md` section 9 and `CLAUDE.md` apply, with Joe's waiver for this brief only, as for briefs 15 and 16: `fy test`, `fy test --quick` and `fy state` are not run; the four targeted tests below are. No new dependencies. Stage by explicit path and read `git diff --cached --stat` before each commit. Use the editor tool for the edit, not a heredoc.

## T1. Save this brief

Save this message as `docs/briefs/architecture/volume-extractor-brief17.md`. Commit it alone, no tests.

## T2. Add the entries

In `decisions/0037-fall-design-basis.md`, at the end of the file, replace this sentence, which must occur exactly once (if not, stop and report):

Each entry states the change, the three tests (interface directions already rated, caps unchanged, stroke inside the existing reservation) and the result. None yet.

with this, byte for byte (the first sentence is the original text without "None yet."; the two entries follow as list items after one blank line):

Each entry states the change, the three tests (interface directions already rated, caps unchanged, stroke inside the existing reservation) and the result.

- 2026-10-31. Hand and arm zone, energy basis (D1c; D3 table row "hand and arm"). The row's basis "centre of mass drops 0.50 m", 320 J, and its "if linear" strokes (67 / 34 / 17 mm) are replaced by the basis of adr-0008 D5: the geometric-drop route of D1(c), one arm acting alone, no sharing, over a pose family bounded by a friction cone (μ = 1.0 [design], no source). Forward-fall energy is 378 to 422 J at the design cone (β = 45°) and 331 to 380 J at μ = 0.5; the lateral fall is lower. The design energy is 430 J (422 J rounded up to the next 10 J), and the strokes at 10 / 20 / 40 kN are 90 / 45 / 23 mm (s_res = 1.25 E / (η F_cap), η = 0.6, D3's rounding). The scenario list is unchanged (forward or sideways); no backward arrest is derived. The band's limits (the pivot model does not cover foot slip, so 430 J is its upper edge, not a bound; μ has no source) are stated in adr-0008 D5 and carried here by reference. Tests: (1) no new direction: the scenarios are the ones already listed, and the arm zone has no cap, so its interfaces are unrated before and after; this entry rates none. (2) No cap set or changed: the zone has none; adr-0008 D6a gives 20 kN as a design judgment, which this entry does not enter, because the first-cap exception of D1(d) needs room cited from data/envelope/ and none exists. (3) No stroke reserved or moved: the zone had no reserved stroke, the "if linear" figures were illustrations, and its stroke home and requirement are set by adr-0008 D6c as D3 provides. The zone's mass claim stays at the 40 kN element, 0.15 kg per unit (D7). Result: valid under the three tests as stated.
- 2026-10-31. D1(b), centre-of-mass height. The [design] placeholder 0.55 × 1.70 = 0.935 m is replaced by 0.942 m [derived: params/snapshot.csv segment masses and centres of mass, standing, vertical stack, pelvis tilt ignored, per adr-0008 D5]. E_max = m g (h_standing − h_end), with h_end 0.10 to 0.20 m, becomes 473 to 537 J (was 469 to 532 J). Its design value, the upper edge rounded up to the next 10 J, stays 540 J, so no zone's E_design in D3 changes, and the knee and hand drop heights do not use h_standing. The vertical-stack value carries about ±10 mm (about ±6 J), which the rounding absorbs. Tests: (1) no direction changes. (2) Caps unchanged. (3) Strokes unchanged, since every E_design is unchanged. Result: valid.

The file ends after the last entry, with one trailing newline and LF endings. Leave the front matter and the "## Revisions" heading unchanged.

Before committing run exactly:

python -m pytest tests/test_conventions.py tests/test_roadmap_validate.py tests/test_roadmap_evaluate.py tests/test_roadmap_derive.py

The pre-commit hook rebuilds the roadmap files. If it changes tracked generated files, include exactly those; if it changes anything else, or a test fails, stop and report. Commit alone, naming the waiver in the message.

## Reporting

No checkpoint and no memo. End with a final message of at most five lines: the two commits, the test result, whether the hook changed any file, and any disagreement.

## Follow-ups (record only; do not act)

1. Backward single-arm arrest energy is not derived. ADR 0008 D6c states 45 mm anteromedial for a backward fall on the assumption that the forward value bounds it; that is unverified.
2. The first-cap entry for the hand-and-arm zone (20 kN) waits until the room is cited from `data/envelope/`.
3. rm.v1-fall-load-cases creates the lc.fall-* records for the arm from adr-0008 D5.
