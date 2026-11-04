---
schema: roadmap-node/2
id: rm.v1-fall-ranking-audit
title: "First floor contact ranked per fall direction on the v3 mesh with contact only at the feet, and any direction where an unzoned region lands first reported"
short: Fall ranking
parent: rm.v1-fall-load-cases
blocked_by: [rm.v1-fall-cases-recorded]
stub: true
tags: ["region:whole-body", "phase:sim", "stage3"]
---
Not yet expanded; proposed reframing of the ranking the parent describes, for Joe to accept or reject when this reaches the frontier.

The parent has the ranking reported across a solref and solimp sweep. Before the first non-foot contact the only contact physics is at the feet, so contact parameters enter only through foot slip and the pivot. What decides which zone lands first is the joint condition and the collision geometry: a welded topple reaches shoulder, head or back first, and a limp collapse buckles at the knees and reaches knee, buttock or hip first. This is the same pose problem as T2 of `docs/briefs/ariadne/fall-inputs-brief.md`.

So the proposal is a coverage audit. Take the zones' stations (memo 59, with adr-0044 D1's chest) plus a vertex region for every segment no zone covers. Detect the first floor crossing kinematically, with contact only at the feet, which also stays inside adr-0036's bar on soft-contact quantities. Run forward, backward and lateral falls at welded and limp bounds, and report the foot-contact spread. A direction where an unzoned region (other than head and neck, which have no energy) lands first is a finding. It goes to a 0037 Revisions entry or a new record under adr-0044 D4.

Expand once rm.v1-fall-cases-recorded is done. Estimate if accepted as framed: 2 to 3 days.
