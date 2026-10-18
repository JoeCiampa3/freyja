---
schema: roadmap-node/2
id: rm.v1-control-architecture
title: "Control architecture recorded: the layers from operator command to joint torque, what each layer does and where it runs, their rates and interfaces, and whether any layer is learned"
short: Control arch
parent: rm.v1-mind
estimate_days: 3.0
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0030-control-architecture.md
---
Open decision, and the one the rest of Mind waits on: estimation, balance and gait each decompose differently under a whole-body QP, MPC, capture-point stepping or a learned layer. The controller sets the rate it needs; rm.v1-comms-architecture sets what the bus delivers; whichever record is written second checks the other and notes any mismatch. Cognitive architecture is outside this tree.
