---
schema: roadmap-node/2
id: rm.v1-safety-chain
title: "Emergency stop and watchdog cut actuator power and leave every joint in its recorded safe state, tested on the bench and on the body"
short: Safety chain
parent: rm.v1-metabolic
blocked_by: [rm.v1-power-architecture, rm.v1-comms-architecture, rm.v1-bench-estop]
stub: true
---
The watchdog's signal travels over the comms architecture; the power cut lives here.
