---
schema: roadmap-node/2
id: rm.v1-bridge-tooling
title: "Bridge tooling passes the Stage 3 gates: parameters out to Fusion, mass properties back into the model"
short: Bridge tooling
parent: rm.v1-ariadne-cad-bridge
blocked_by: [rm.v1-stage3-brief, rm.v1-thread-store]
stub: true
tags: ["stage3"]
---
Reads its parameters through system-model addresses and records what each CAD export consumed as a stamp (Stage 3a), so a changed input marks the CAD model stale.
