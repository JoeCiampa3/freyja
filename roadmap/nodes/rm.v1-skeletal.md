---
schema: roadmap-node/2
id: rm.v1-skeletal
title: "v1 skeleton fabricated in final form, every link and joint verified against its load envelope."
short: Skeletal
parent: rm.freyja-v1
---
Sector. Links, frames, connectors and passive joint structure, designed per segment. A segment's actuators are Muscular and mount to its structure through a recorded interface; drivers, encoders and harness are Nervous. Component load tests live here; integration trials live in Trials.

The upper arm goes first as the Ariadne benchmark. Every other segment's design waits on rm.v1-upper-arm-validated, and its fabrication also waits on rm.v1-upper-arm-benchmark and rm.v1-dmc2-qualified, so no other part is cut before the predictions have been checked against a real one or on an unqualified machine; both fabrication edges are wired when the segment stub is expanded. When a segment stub is expanded, wire it as the upper arm is wired: its design leaf waits on the segment's characterization and requirement records in Ariadne, and Ariadne's validation of the segment waits on the design leaf. Never block a Skeletal node on rm.v1-other-part-traces as a whole: its validation children will be blocked by Skeletal design leaves, which closes a cycle.

Bilateral segments (designed once, mirrored) carry no region tag until tags.yaml gains bilateral values.
