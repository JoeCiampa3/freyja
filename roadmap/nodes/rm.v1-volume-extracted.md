---
schema: roadmap-node/2
id: rm.v1-volume-extracted
title: "Available volume extracted for every segment, the hip and trunk registration questions settled, and the v2 spine actuator volume reserved"
short: Volume extracted
parent: rm.v1-ariadne-body-envelope
blocked_by: [rm.v1-envelope-method]
tags: ["region:whole-body"]
---
ADR 0007 (accepted 2026-10-26) fixes the method. The extraction itself is built and committed (rm.v1-envelope-built); what stays open is the D11 list that structure design cannot ignore: the hip registration, the trunk's x offset, where the v2 spine modules live, and the arm joint anchors (rm.v1-arm-joint-anchors-decision). The sculpt is not an open question: D7 is an observation with no re-sculpt, and the arm stretches (1.124 and 1.120) are accepted against the 2 sigma / L gate (memo 39) until that decision settles them. Memo 43 showed that the elbow anchor is not fixed by the bisector cut: the node is a skin vertex 4.0 mm under the lateral skin and about 30 mm lateral of the section centre line, so the arm anchors are a leaf.

Reservations are the v2 spine articulation modules only (data/envelope/reservations.yaml). Hands and head are v1 placeholders swapped whole in v2, with only the wrist and neck interfaces fixed, so no volume is reserved for them. The v1 lumbosacral actuators are designed, not reserved.

Dependents wait on the leaves they consume, not on this node as a whole; rm.v1-thread-budgets keeps the whole-node edge because it needs every number final.
