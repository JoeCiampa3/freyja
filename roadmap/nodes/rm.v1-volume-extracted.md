---
schema: roadmap-node/2
id: rm.v1-volume-extracted
title: "Available volume extracted for every segment, the hip and trunk registration questions settled, and the v2 spine actuator volume reserved"
short: Volume extracted
parent: rm.v1-ariadne-body-envelope
blocked_by: [rm.v1-envelope-method]
tags: ["region:whole-body"]
---
ADR 0007 (accepted 2026-10-26) fixes the method. The extraction itself is built and committed (rm.v1-envelope-built); what stays open is the D11 list that structure design cannot ignore: the hip registration, the trunk's x offset, and where the v2 spine modules live. The sculpt is not an open question: D7 is an observation with no re-sculpt, and the arm stretches (1.124 and 1.120) are accepted against the 2 sigma / L gate (memo 39). The elbow anchor is fixed by the bisector cut, so the arm anchors are not a leaf.

Reservations are the v2 spine articulation modules only (data/envelope/reservations.yaml). Hands and head are v1 placeholders swapped whole in v2, with only the wrist and neck interfaces fixed, so no volume is reserved for them. The v1 lumbosacral actuators are designed, not reserved.

Dependents wait on the leaves they consume, not on this node as a whole; rm.v1-thread-budgets keeps the whole-node edge because it needs every number final.
