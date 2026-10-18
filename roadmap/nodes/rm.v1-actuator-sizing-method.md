---
schema: roadmap-node/2
id: rm.v1-actuator-sizing-method
title: "Actuator sizing method recorded: envelope statistic, separate safety factor, peak versus continuous duty, and how a requirement record becomes an actuator spec"
short: Sizing method
parent: rm.v1-muscular
estimate_days: 1.0
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0009-actuator-sizing-method.md
---
Approach so far: lock a trusted demand number first, then apply the safety factor on top, rather than lowering the factor to cover a doubtful number.
