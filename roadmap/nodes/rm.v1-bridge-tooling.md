---
schema: roadmap-node/2
id: rm.v1-bridge-tooling
title: "Bridge tooling passes the Stage 3 gates: parameters out to Fusion, mass properties back into the model"
short: Bridge tooling
parent: rm.v1-ariadne-cad-bridge
blocked_by: [rm.v1-stage3-brief, rm.v1-thread-store]
estimate_days: 3.0
tags: ["stage3"]
done_when: {type: manual}
signed_off: true
---
Reads its parameters through system-model addresses and records what each CAD export consumed as a stamp (Stage 3a), so a changed input marks the CAD model stale.
