---
schema: roadmap-node/2
id: rm.v1-forearm-structure
title: "Forearm structure and hand mass dummy designed, fabricated and verified, with the dummy on its final wrist interface"
short: Forearm and hand
parent: rm.v1-skeletal
blocked_by: [rm.v1-upper-arm-validated, rm.v1-envelope-built]
stub: true
tags: ["region:arm"]
---
Its elbow connector is fixed by the upper arm's connector record. Loads follow the elbow load basis (0008); if that record does not cover the forearm, add rm.v1-ariadne-task-loads here.
