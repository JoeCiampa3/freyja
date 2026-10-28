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

From the Oct 2026 arm discussion: headroom is checked as a trajectory on the actuator's torque-speed curve (peak speed and peak acceleration do not coincide, and gravity torque acts even at rest), not as two independent peaks. The 70% headroom proposed for the arms is a design choice, not sourced.
