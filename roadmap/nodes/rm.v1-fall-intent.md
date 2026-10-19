---
schema: roadmap-node/2
id: rm.v1-fall-intent
title: "Fall intent recorded: whether v1 is designed to touch the ground in a fall, which regions may, and which damage is accepted and replaceable"
short: Fall intent
parent: rm.v1-ariadne-fall-loads
estimate_days: 0.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0036-fall-intent.md
---
Joe's decision. The trial rig holds a slack catch line, so a fall in the trial ends on the line, not necessarily on the floor. Options: (A) the line is set so no body part reaches the floor; (B) contact is tolerated on named regions (arms braced, hips, back) with sacrificial, replaceable parts; (C) contact is not designed for, and a fall that reaches the floor is a failed trial and a repair. Only B needs impact load cases. A and C need only the arrest load on the harness hardpoint, which rm.v1-trial-rig-concept and rm.v1-torso-structure already carry. The record also says what happens if the line fails or is not fitted.

If it chooses A or C, supersede rm.v1-fall-sources, rm.v1-thread-sources, rm.v1-fall-load-cases and rm.v1-drop-test.
