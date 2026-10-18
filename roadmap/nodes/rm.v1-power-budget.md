---
schema: roadmap-node/2
id: rm.v1-power-budget
title: "Power and energy budget for the acceptance trial recorded: per-joint peak and continuous electrical power, compute and sensing load, trial duration and margin"
short: Power budget
parent: rm.v1-metabolic
blocked_by: [rm.v1-stage2-closed, rm.v1-actuator-sizing-method, rm.v1-power-architecture]
estimate_days: 1.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0029-power-budget.md
---
First pass from the simulated joint power the runs already record plus the sizing method's efficiency and duty conventions. Amended, not superseded, as each actuator is selected, so the leaf stays passed while the numbers sharpen.
