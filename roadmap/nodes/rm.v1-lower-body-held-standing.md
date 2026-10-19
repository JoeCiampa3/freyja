---
schema: roadmap-node/2
id: rm.v1-lower-body-held-standing
title: "Lower body stands in the rig under the onboard controller with the rig carrying a recorded fraction of its weight"
short: Lower standing
parent: rm.v1-lower-body-trials
blocked_by: [rm.v1-lower-body-assembled, rm.v1-stack-on-target, rm.v1-balance, rm.v1-state-estimation, rm.v1-compute-installed]
stub: true
tags: ["region:leg", "phase:integrate"]
---
The first place the controller runs on the body. The simulation is corrected from what it measures in rm.v1-sim-to-real-gaps.
