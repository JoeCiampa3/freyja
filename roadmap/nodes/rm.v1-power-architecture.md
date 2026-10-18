---
schema: roadmap-node/2
id: rm.v1-power-architecture
title: "Power architecture recorded: bus voltage, distribution topology, protection, the emergency-stop power path and regenerated energy"
short: Power arch
parent: rm.v1-metabolic
blocked_by: [rm.v1-hip-architecture-adr, rm.v1-knee-concept-adr]
estimate_days: 1.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0028-power-architecture.md
---
Actuators lead and the bus follows: the lower-limb actuators under selection set the working voltage, and a joint that wants a different voltage is served by local conversion. The record is written now from that working assumption. A change of bus voltage supersedes the record, which reopens the battery, distribution, harness and controller nodes built on it; a change of detail amends it.
