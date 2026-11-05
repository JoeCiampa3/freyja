---
schema: roadmap-node/2
id: rm.v1-shoulder-concept
title: "Shoulder actuation concept chosen and recorded: actuated DOF for v1 arm swing, mechanism, placement and governing load case"
short: Shoulder concept
parent: rm.v1-shoulder-actuation
estimate_days: 3.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0025-shoulder-actuation-concept.md
---
Blocks rm.v1-upper-arm-connectors, so it sits on the path to the first validated part. It settles only what the shoulder end of the connector must carry and where the actuators sit; if it places one inside the upper arm, that selection joins the blockers of rm.v1-upper-arm-designed.

Fall zones (adr-0044 D3): this record owns the lateral shoulder zone (540 J) and the hand-and-arm zone (430 J, adr-0008 D5), whose stroke home is the thorax-shoulder interface (adr-0008 D6(c)). It sets each zone's mechanism, cap and reserved arc under adr-0044 D2, starting from 20 kN for the arm (adr-0044 D5). Whether one guideway serves both zones stays open. No repo tool sweeps the arc yet (memo 59). Estimate raised to 3.0 days for the two arcs; if the arc work grows, split it into a child leaf.

Backward arm arrest (Joe, 2026-11-04): this record also carries the hand-and-arm zone's backward scenario, since the same arc works in both directions. adr-0037's arm scenario is forward or sideways and adr-0044 D4 does not let a Revisions entry add a direction, so the record states the scenario, its energy and where the energy comes from (adr-0008 D6(c) has 430 J assumed equal to the forward case, and its heel-pivot check is not in a committed script), and the arc's stroke in the anteromedial direction. rm.v1-fall-case-arm-backward writes the load case from it. The estimate stays 3.0; the added direction is the same arc, and if it grows, split it with the arcs.
