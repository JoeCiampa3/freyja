---
schema: roadmap-node/2
id: rm.v1-upper-arm-geometry-extracted
title: "Upper-arm ROM, available volume and interface frames extracted, each position carrying its anchor error bar"
short: UA geometry
parent: rm.v1-upper-arm-characterized
blocked_by: [rm.v1-upper-arm-char-schema, rm.v1-envelope-method, rm.v1-arm-joint-anchors-decision, rm.v1-arm-sculpt-v3]
estimate_days: 1.5
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: manual
---
Delegate. Elbow ROM from the contract record; available volume from the envelope oracle on the v3 sculpt; the shoulder and elbow interface frames on the adr-0042 D1 nodes with the D4 roll, each with the envelope section at its station. Every position quotes adr-0042 D2's bar (7 mm at the elbow, mostly anteroposterior; 5 mm at the wrist). The room around the elbow was one-sided under the old skin-vertex anchor (memo 43), so the brief should check it again on the D1 node. Gates are in the brief.
