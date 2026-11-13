---
schema: roadmap-node/2
id: rm.v1-upper-arm-char-brief
title: "Upper-arm characterization brief written, with every gate authored before the work"
short: UA char brief
parent: rm.v1-upper-arm-characterized
blocked_by: [rm.v1-upper-arm-char-contract]
estimate_days: 0.5
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: artifact
  path: docs/briefs/ariadne/upper-arm-characterization-brief.md
---
The Code brief for the schema, geometry, loads and file leaves, written in chat to the accepted contract record. It authors the gates of each leaf (thresholds are authored before the work, README section 8), reuses the envelope tooling and the thread's stamp machinery rather than copying them, and tags each part Delegate or Pair.
