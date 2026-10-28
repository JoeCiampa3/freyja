---
schema: roadmap-node/2
id: rm.v1-upper-arm-connectors
title: "Upper-arm elbow and shoulder connectors decided and recorded: bolt circle, clocking, fastener count and size"
short: UA connectors
parent: rm.v1-upper-arm-structure
blocked_by: [rm.v1-elbow-actuator-selected, rm.v1-upper-arm-requirements, rm.v1-provisional-design-rules, rm.v1-shoulder-concept]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0020-upper-arm-connectors.md
---
Final once accepted. The shoulder end is set from the shoulder concept (rm.v1-shoulder-concept); the shoulder's detailed design and the forearm are then made to these connectors. Fastener and dowel sizes follow what the provisional design rules say the shop can tap and ream; rm.v1-design-rules confirms them before the part is cut. The values live in the record.

The record also carries the connector's fall provisions (rm.v1-fall-design-basis): an axial compliance stroke and an overload stop that grounds an impact into structure before it reaches the bearings.
