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
