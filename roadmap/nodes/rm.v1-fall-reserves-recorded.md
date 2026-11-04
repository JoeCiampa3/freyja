---
schema: roadmap-node/2
id: rm.v1-fall-reserves-recorded
title: "The adr-0037 D7 mass-reservation records written into the thread, one per zone, each claiming the 40 kN element until its owning record enters a cap"
short: Fall reserves
parent: rm.v1-fall-load-cases
blocked_by: [rm.v1-fall-cases-recorded]
stub: true
tags: ["region:whole-body", "phase:spec", "stage3"]
---
Deferred by Joe on 2026-11-04. The parent's text assigned these records to the fall-load-cases node; this stub keeps them in the tree so the parent cannot close without them.

Seven records, one per zone, 3.50 kg in all (adr-0044 D6): hip and buttock in the pelvis; back, chest and shoulder in the thorax; knee in the thigh; hand and arm in the upper arm. Each claims the 40 kN element at its standoff (adr-0037 D7) until an owning record enters a cap and releases mass.

Two problems with the form adr-0037 D7 gives, to settle in an Amendment before this is expanded:

- **Id collision.** The id is `part.<segment>.fall-reserve`, but the pelvis houses two zones and the thorax three, so their ids collide. The part-id pattern allows a hyphenated second segment, so a zone suffix works (`part.pelvis.fall-reserve-hip`), but the record needs to say so.
- **Unit counts.** D7 says `sides` as the segment and the mass is one unit. `seg.pelvis` and `seg.thorax` carry no `sides`, so a hip record would claim one unit where the table has two (and the shoulder the same), under-claiming about 0.6 kg of the 3.10 kg in adr-0037 D7's table. Either the kg field carries the zone's total, or the pelvis and thorax records get a way to say two units.

Open, and not decided by 0037: when a later version fits a compliant element in a zone (a D6 protective part), does its mass draw down this reserved claim or sit beside it? The claim is sized as the structural element rated to the cap, not the absorber.
