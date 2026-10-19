---
schema: roadmap-node/2
id: rm.v1-control-interface
title: "Controller interface to the simulation running: a controller reads the simulated sensor channels and commands joint torques at the architecture's rate, with a null controller passing a smoke run"
short: Control loop
parent: rm.v1-control-sim
blocked_by: [rm.v1-control-architecture]
estimate_days: 2.0
tags: ["region:whole-body", "phase:sim"]
done_when:
  type: manual
---
Manual: Joe signs off on the smoke run. The interface is the seam every later Mind node attaches to.
