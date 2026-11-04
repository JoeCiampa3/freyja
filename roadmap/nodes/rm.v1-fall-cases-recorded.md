---
schema: roadmap-node/2
id: rm.v1-fall-cases-recorded
title: "One fall load case per zone and scenario of adr-0037 as amended by adr-0044 written into the thread as a proposed record, each carrying its design energy and checked evidence, with no unsourced case"
short: Cases recorded
parent: rm.v1-fall-load-cases
estimate_days: 1.0
tags: ["region:whole-body", "phase:spec", "stage3"]
done_when:
  type: manual
---
Delegate. Writes the records below in the energy-defined form of thread-record/2 (adr-0037 D1(a)): `independent_source_required: true`, `zone_in` the housing segment, `evidence` as listed, status proposed. A case carries energy and direction, never a cap, so none of this waits on a cap. When an owning record enters a zone's cap (adr-0044 D2), the zone's case gains that record as evidence. The Code brief is not yet written (`docs/briefs/ariadne/fall-cases-brief.md`). The gates below are authored before the work.

| id | zone | direction | energy_j | energy_basis | zone_in | evidence |
|---|---|---|---|---|---|---|
| lc.fall-hip-lateral | hip | lateral, hip first | 540 | E_max | seg.pelvis | adr-0037 D1(b) |
| lc.fall-shoulder-lateral | shoulder | lateral, shoulder first | 540 | E_max | seg.thorax | adr-0037 D1(b) |
| lc.fall-buttock-backward | buttock | backward, buttock first | 540 | E_max | seg.pelvis | adr-0037 D1(b) |
| lc.fall-back-backward | back | backward, back first | 540 | E_max | seg.thorax | adr-0037 D1(b) |
| lc.fall-chest-forward | chest | forward, chest first, arm not arresting | 540 | E_max | seg.thorax | adr-0037 D1(b); adr-0044 D1 |
| lc.fall-knee-forward | knee | forward collapse onto one knee | 260 | centre of mass drops 0.40 m | seg.thigh | adr-0037 D1(c), D3 |
| lc.fall-hand-arm | hand-arm | forward or sideways, one arm, no sharing | 430 | geometric drop, mu = 1.0 cone | seg.upper_arm | adr-0037 D3; adr-0008 D5 |
| lc.fall-hand-arm-backward | hand-arm | backward, one arm, no sharing | 430 | assumed equal to forward | seg.upper_arm | adr-0008 D6(c) |

Choices made in this table:

- **One arm case for forward or sideways.** adr-0008 D5 puts the lateral arrest at 238 to 331 J, under the forward band, and says it never governs the arm. The lateral superomedial arc is the shoulder zone's own case (adr-0008 D6(c)). One case at 430 J therefore covers both.
- **Backward arm case.** Joe, 2026-11-04: add it, because the same arc works both ways. adr-0037's zone table lists forward or sideways only, and adr-0044 D4 test 1 does not let a Revisions entry add a direction to a zone. adr-0008 D6(c) is an accepted record that already owns the backward 45 mm, at 430 J assumed equal to the forward case (its heel-pivot check gave 420 to 427 J and is not in a committed script). So the case cites adr-0008 D6(c) directly. Before the record is written, Joe approves the exact text of a pointer Amendment to adr-0037 so its table agrees. Draft: "YYYY-MM-DD. Pointer; no number changes. D3's hand-and-arm row lists forward or sideways arrests. adr-0008 D6(c) owns the arm's backward stroke at the same 430 J, assumed equal to the forward case, and the zone's backward case cites it." Joe decides whether that suffices or a new record is wanted; if a new record, the backward case waits on it and the other seven proceed.
- **Evidence grade is not validation.** "Sourced" means an accepted decision carries the number. The knee's 260 J rests on a drop height chosen in adr-0037 D3 [design], and the arm's mu = 1.0 has no source. Each record's `notes` says so.
- **S1 and S11 are not cited.** Both are Verified rows at 107 to 257 J. They lower nothing (adr-0037 D1(c)), and attaching them would show Verified support for 540 J that they do not give. They go in `notes` as calibration.

Gates (authored before the work; Joe signs off the memo):

- **G1.** `fy thread build` gives 0 errors and 0 warnings.
- **G2.** All eight cases derive `sourcing: sourced`, with every evidence entry resolved and admissible.
- **G3.** Each housing segment's derived `fall_cases` lists its cases: thorax 3 (shoulder, back, chest), pelvis 2, thigh 1, upper_arm 2.
- **G4.** No existing record, work status or stamp changes.

Open for the characterization step, not decided here: the shoulder zone is housed in the thorax (adr-0037 D3), but its skin contact is on `upper_arm_R` (memo 59, finding 7). `seg.upper_arm`'s derived `fall_cases` will therefore not list `lc.fall-shoulder-lateral`, and the upper-arm characterization has to read it through the thorax-shoulder interface or the schema needs a contact-segment field. Joe approves any schema change.

Out of scope: caps and strokes (the owning records of adr-0044 D3), the `part.<segment>.fall-reserve` records of adr-0037 D7 (rm.v1-fall-reserves-recorded, a deferred stub: their id pattern has no zone in it, so hip and buttock collide in the pelvis), and the ranking (rm.v1-fall-ranking-audit).
