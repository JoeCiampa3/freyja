---
schema: roadmap-node/2
id: rm.v1-structural-method
title: "Structural sizing and verification method recorded: load statistic, factors on yield and fatigue, stiffness limits, analysis or physical test, and how a requirement record becomes a structural spec"
short: Structure method
parent: rm.v1-skeletal
estimate_days: 1.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0019-structural-method.md
---
Structural counterpart of rm.v1-actuator-sizing-method. Settles whether segments are verified by analysis alone or also by a physical test on rm.v1-load-rig, and what load that test applies. The numbers are Joe's and live in the record.

Inputs from the Oct 2026 arm discussion, not yet decided (docs/briefs/ariadne/stage3b-brief.md, Follow-ups): static SF of at least 2 on yield at peak stress including stress concentration, under the actuator-peak case rather than the payload case; fatigue SF of at least 1.5 against fatigue strength for swing and payload cycling; an advisory deflection limit of 1 mm at the hand under the design payload.
