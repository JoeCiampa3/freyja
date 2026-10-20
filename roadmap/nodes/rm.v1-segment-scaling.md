---
schema: roadmap-node/2
id: rm.v1-segment-scaling
title: "Segment scaling and foot geometry decided and recorded: one factor for every Dumas length, closed on vertical heights at the design posture, with the foot's heel, ball and toe tip taken from the sheet"
short: Segment scaling
parent: rm.v1-ariadne-walk-loads
blocked_by: [rm.v1-hip-stop-pelvis-pose]
estimate_days: 0.5
tags: ["region:whole-body", "phase:spec", "stage2"]
done_when:
  type: decision
  record: decisions/0038-segment-scaling.md
---
BSIP re-verification notes: the arm, forearm, hand and foot lengths are unscaled, and the stack closure assumes vertical chord lengths. Waits on the pelvis tilt in record 0004, which the closure uses. Draft record: ADR 0038.
