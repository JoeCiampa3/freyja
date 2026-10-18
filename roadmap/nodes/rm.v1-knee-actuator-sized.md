---
schema: roadmap-node/2
id: rm.v1-knee-actuator-sized
title: "Knee actuator sized from the recorded load basis and recorded"
short: Knee sized
parent: rm.v1-knee-actuation
blocked_by: [rm.v1-actuator-sizing-method, rm.v1-knee-concept-adr, rm.v1-knee-load-basis, rm.v1-stage2-closed, rm.v1-knee-actuator-map]
estimate_days: 2.0
tags: ["phase:spec"]
done_when:
  type: decision
  record: decisions/0015-knee-actuator-sizing.md
---
Sizes against the moment-angle envelope (memo11, T5), not a peak alone, from the regenerated loads once Stage 2 has closed.
