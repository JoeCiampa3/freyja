---
schema: roadmap-node/2
id: rm.v1-fall-case-arm-backward
title: "The arm's backward fall case written into the thread as a proposed record, citing the shoulder-concept record that owns the arm's arc in both directions"
short: Arm backward
parent: rm.v1-fall-load-cases
blocked_by: [rm.v1-fall-cases-recorded, rm.v1-shoulder-concept]
stub: true
tags: ["region:arm", "phase:spec", "stage3"]
---
Not yet expanded. One record, `lc.fall-hand-arm-backward`: zone `hand-arm`, direction backward with one arm and no sharing, `zone_in: seg.upper_arm`, `independent_source_required: true`, evidence the accepted adr-0025 clause that carries the backward arrest. About 0.25 day once adr-0025 is accepted.

Why it waits: adr-0037's arm scenario is forward or sideways, and adr-0044 D4 test 1 does not let a Revisions entry add a direction to a zone. adr-0008 D6(c) already owns a backward 45 mm, but at 430 J "assumed equal" to the forward case, and its heel-pivot check (420 to 427 J, arms leaning toward the feet only) is not in a committed script. Joe's call, 2026-11-04: the shoulder-concept record carries it, since it owns the arc and sets the cap for both directions.

What adr-0025 needs to state for this case: the backward arrest as a scenario of the hand-arm zone, its energy and where it comes from (a committed script reproducing 0008 D5's forward band and the backward check closes the gap; that is T2 of `docs/briefs/ariadne/fall-inputs-brief.md`, still held), and the arc's stroke in the anteromedial direction.
