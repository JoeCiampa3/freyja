---
schema: roadmap-node/2
id: rm.v1-toe-in-model
title: "Snapshot change applied once and the model checks passing: toe body and hinge, foot box from anatomical landmarks, standing posture and vertical-stack scaling, the nine new joint ranges, and the pelvis-frame offset applied in the retargeting if Joe adopts it"
short: Snapshot change
parent: rm.v1-ariadne-walk-loads
blocked_by: [rm.v1-toe-joint-decided, rm.v1-hip-stop-pelvis-pose, rm.v1-segment-scaling, rm.v1-rom-gaps-filled, rm.v1-stage2g-brief]
estimate_days: 3.0
tags: ["region:foot", "phase:sim", "stage2"]
done_when:
  type: manual
---
The model and sheet change every Stage 2 decision implies, done once so the three-speed gait run is repeated once, at rm.v1-stage2-closed. Brief: docs/briefs/ariadne/stage2g-brief.md; sheet contract: docs/briefs/ariadne/stage2g-sheet-spec.md. Part A (code, template, tests and the frame experiment) needs no sheet edit and can start once ADRs 0001, 0004 and 0038 are accepted; Part B needs the edited sheet and the ROM values. The estimate is the roadmap's cap; the run adds about 33 minutes of machine time. Manual: Joe signs off after Checkpoint B.
