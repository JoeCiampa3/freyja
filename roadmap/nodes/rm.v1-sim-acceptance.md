---
schema: roadmap-node/2
id: rm.v1-sim-acceptance
title: "Acceptance protocol passed in simulation on the target compute, against the model with CAD masses and every actuator and sensor model in place"
short: Sim acceptance
parent: rm.v1-mind
blocked_by: [rm.v1-ariadne-mass-closure, rm.v1-actuator-models, rm.v1-sensor-models, rm.v1-state-estimation, rm.v1-balance, rm.v1-gait, rm.v1-operator-interface, rm.v1-stack-on-target, rm.v1-acceptance-protocol]
stub: true
tags: ["region:whole-body", "phase:sim"]
---
Waits on CAD masses because passing on the anthropometric model does not verify Freyja. The pass is against the acceptance protocol record (Trials), the same course and thresholds the body trials use.
