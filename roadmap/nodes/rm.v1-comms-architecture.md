---
schema: roadmap-node/2
id: rm.v1-comms-architecture
title: "Joint communication architecture recorded: bus, topology, control-loop rate and latency budget, and where each joint's driver and controller sit"
short: Comms arch
parent: rm.v1-nervous
blocked_by: [rm.v1-hip-architecture-adr, rm.v1-knee-concept-adr]
estimate_days: 1.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0026-comms-architecture.md
---
Actuators lead: the interfaces of the lower-limb actuators under selection set what the bus must speak, and where an actuator has its own driver the driver is its end of the bus. The record follows them. A change of bus or topology supersedes this record and reopens everything built on it; a refinement amends it.
