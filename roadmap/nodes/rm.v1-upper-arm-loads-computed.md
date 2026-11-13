---
schema: roadmap-node/2
id: rm.v1-upper-arm-loads-computed
title: "Upper-arm demand loads computed at its interface frames for every load-basis case and every fall case that strikes the segment"
short: UA loads
parent: rm.v1-upper-arm-characterized
blocked_by: [rm.v1-upper-arm-geometry-extracted, rm.v1-elbow-load-basis, rm.v1-fall-cases-recorded, rm.v1-fall-case-arm-backward]
estimate_days: 2.5
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: manual
---
Delegate. Demand only, per the contract record: the cases decision 0008 accepts (static gravity sweep with payload, minimum-jerk swing with robot inertias from the snapshot) and the fall cases whose contact is the upper arm (lc.fall-hand-arm, lc.fall-hand-arm-backward, and lc.fall-shoulder-lateral through `contact_in`), each expressed as transmitted loads in the interface frames from rm.v1-upper-arm-geometry-extracted and flagged structural load or clearance constraint.

The backward case is a blocker by Joe's call, 2026-11-13. His working assumption is that it mirrors the forward case; adr-0008 D6(c) already assumes 430 J "equal" to the forward, but no committed script backs it (T2 of `docs/briefs/ariadne/fall-inputs-brief.md`). The mirror covers energy only; the load path and the stop that carries it are the shoulder-concept record's to state. This leaf therefore waits on rm.v1-shoulder-concept; nothing else under the characterization does. Gates are in the brief.
