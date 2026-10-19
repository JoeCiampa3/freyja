---
schema: roadmap-node/2
id: rm.v1-knee-actuator-map
title: "Knee moment-angle envelope mapped into actuator coordinates for the recorded knee concept"
short: Knee map
parent: rm.v1-ariadne-actuator-map
blocked_by: [rm.v1-map-method, rm.v1-knee-concept-adr, rm.v1-stage2-closed]
estimate_days: 1.5
tags: ["region:leg", "phase:sim"]
done_when:
  type: manual
---
For a linkage the mapping is a function of joint angle, not a single ratio.
