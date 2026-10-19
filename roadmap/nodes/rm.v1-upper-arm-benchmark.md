---
schema: roadmap-node/2
id: rm.v1-upper-arm-benchmark
title: "Ariadne's predictions for the upper arm checked against the built part: CAD mass and centre of mass against the weighed part, FEA deflection and strain against the load test, with the errors recorded"
short: UA benchmark
parent: rm.v1-upper-arm-trace
blocked_by: [rm.v1-upper-arm-load-tested]
stub: true
tags: ["region:arm", "stage3"]
---
The benchmark that quantifies how well the Ariadne loop works. Every other segment's fabrication waits on it, wired as each segment stub is expanded; their design waits only on rm.v1-upper-arm-validated. Further measures, such as time through the loop or iteration count, are Joe's to define when this stub is expanded.
