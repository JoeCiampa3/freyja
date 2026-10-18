---
schema: roadmap-node/2
id: rm.v1-gait
title: "Walking in simulation from estimated state: 10 m straight at the acceptance speed, following an operator velocity command, without a fall"
short: Gait
parent: rm.v1-mind
blocked_by: [rm.v1-control-interface, rm.v1-toe-joint-decided, rm.v1-trunk-modes-decided]
stub: true
tags: ["phase:sim"]
---
The toe joint and the v1 trunk mode both change the model the gait is tuned on, so both are blockers. Further blockers join when it is expanded.
