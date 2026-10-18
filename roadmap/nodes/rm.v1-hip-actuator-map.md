---
schema: roadmap-node/2
id: rm.v1-hip-actuator-map
title: "Hip envelope mapped into actuator coordinates for the recorded hip architecture, every hip degree of freedom included"
short: Hip map
parent: rm.v1-ariadne-actuator-map
blocked_by: [rm.v1-map-method, rm.v1-hip-architecture-adr, rm.v1-stage2-closed]
estimate_days: 2.0
tags: ["region:pelvis", "phase:sim"]
done_when:
  type: manual
---
Covers the coupled hip axes and the yaw axis. The loads are the regenerated ones, so it waits for Stage 2 to close.
