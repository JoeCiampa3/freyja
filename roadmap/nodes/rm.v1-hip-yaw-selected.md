---
schema: roadmap-node/2
id: rm.v1-hip-yaw-selected
title: "Hip yaw actuator selected and recorded against its torque, speed and backlash spec"
short: Hip yaw
parent: rm.v1-hip-actuation
blocked_by: [rm.v1-actuator-sizing-method, rm.v1-hip-architecture-adr, rm.v1-stage2-closed, rm.v1-hip-actuator-map]
estimate_days: 2.0
tags: ["region:pelvis", "phase:spec"]
done_when:
  type: decision
  record: decisions/0013-hip-yaw-actuator.md
---
Spec values come from the sizing method and the envelope, not from this title. Waits for the regenerated loads (Stage 2 closed) and for the hip architecture, which fixes where the yaw axis sits.
