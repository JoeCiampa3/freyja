---
schema: roadmap-node/2
id: rm.v1-pelvis-structure
title: "Pelvis structure designed, fabricated and verified against its load envelope"
short: Pelvis structure
parent: rm.v1-skeletal
blocked_by: [rm.v1-upper-arm-validated, rm.v1-hip-architecture-adr, rm.v1-lsj-concept, rm.v1-ariadne-task-loads, rm.v1-envelope-built, rm.v1-hip-registration-decided, rm.v1-spine-reservation-decided]
stub: true
tags: ["region:pelvis"]
---
Carries the lower half of the lumbosacral joint and whichever hip actuators the hip architecture places in the pelvis, inside the aesthetic pelvic dimensions.

Fall zones (adr-0044 D3): this node owns the hip zone (lateral, 540 J) and the buttock zone (backward, 540 J). The decision record that designs their stroke home sets each zone's mechanism, cap and reserved stroke under adr-0044 D2, and an adr-0037 Revisions entry points to it. Memo 59's room readings (`data/falls/room.json`) are evidence for a linear stroke only, and are upper bounds.
