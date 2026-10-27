---
schema: roadmap-node/2
id: rm.v1-envelope-built
title: "Available volume extracted for all ten sheet segments, the conformed bodies summing to the mesh volume within 0.5% with no remainder"
short: Envelope built
parent: rm.v1-volume-extracted
estimate_days: 0.5
tags: ["region:whole-body", "phase:sim", "stage3"]
done_when:
  type: artifact
  path: data/envelope/arm_bodies.json
---
Built by volume-extractor briefs 1 to 8 (memos 27 to 39), already passing when this leaf was written. The evidence: a section ledger and `_sections.csv` for each of thigh_R, shank_R, foot_R, pelvis, abdomen, thorax, head_neck, upper_arm_R, forearm_R and hand_R under data/envelope/, and the closure with every body built at +0.333% against the 0.5% gate (memo 39, gate 7; threshold authored in ADR 0007 D10).

The artifact criterion only proves arm_bodies.json exists (it holds the closure and the share table, written by `fy envelope gates`); it does not read the closure number. Upgrade to a metric against 0.5% once Code reports a stable JSON pointer for the closure value.
