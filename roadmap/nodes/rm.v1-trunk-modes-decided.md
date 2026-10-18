---
schema: roadmap-node/2
id: rm.v1-trunk-modes-decided
title: "Lumbosacral sizing mode and v1 gait trunk mode chosen and recorded"
short: Trunk modes
parent: rm.v1-ariadne-walk-loads
estimate_days: 0.5
tags: ["region:spine", "phase:spec", "stage2"]
done_when:
  type: decision
  record: decisions/0005-trunk-modes.md
---
v1 torso: one 3-DOF joint at the lumbosacral joint, unlocked and actuated in gait; thoracic and cervical rigid. v2 aims at a more human gait with more joints. The record picks the v1 gait trunk mode from the envelope's modes and the mode the lumbosacral hardware is sized for.
