---
schema: roadmap-node/2
id: rm.v1-bsip-reverified
title: "Every BSIP row in the sheet re-verified against its published source before simulation output is used for sizing"
short: BSIP verified
parent: rm.v1-ariadne
estimate_days: 2.0
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: manual
---
An earlier decision deferred re-verifying every BSIP row against the literature until before simulation output is used for sizing; the knee and elbow load bases are the first such uses. Includes the mass-fraction residual (rows sum to 96.9%, currently distributed proportionally). Manual: Joe signs off.
