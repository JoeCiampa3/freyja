---
schema: roadmap-node/2
id: rm.v1-gait
title: "Walking in simulation from estimated state: the protocol's course, straight legs and the turn, at the acceptance speed following operator commands, without a fall"
short: Gait
parent: rm.v1-mind
blocked_by: [rm.v1-control-interface, rm.v1-toe-joint-decided, rm.v1-trunk-modes-decided]
stub: true
tags: ["phase:sim"]
---
The toe joint and the v1 trunk mode both change the model the gait is tuned on, so both are blockers. Further blockers join when it is expanded. Turning is part of the acceptance course, so the turn is in scope here and the operator interface carries a turn command.
