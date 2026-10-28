---
schema: roadmap-node/2
id: rm.v1-arm-joint-anchors-decision
title: "Arm joint-centre anchors decided: where the elbow and wrist nodes sit in the section, with the forearm stretch gate and the segment frame roll settled"
short: Arm anchors
parent: rm.v1-volume-extracted
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0042-arm-joint-anchors.md
---
ADR 0007 D2 and D11, memo 43. The elbow node is the midpoint of two Ruler chord vertices that lie on the skin. It sits 4.0 mm under the lateral skin and about 27 to 30 mm lateral of the section centre line (half the skin breadth there is about 33 mm); the wrist node is on the skin (0.07 mm). The anchor itself is the cause: not the roll (0.32 degrees on the upper arm), not the bisector cap (the field ignores it), not a slender mesh (the elbow's skin breadth, 66.8 to 68.3 mm, is about the 75th percentile of NHANES III women's elbow breadth, a caliper reading). The room the oracle reports around the elbow is one-sided as a result.

Options for the record: (A) keep the skin nodes and carry an explicit lateral offset for the joint centre; (B) the section centre line, extrapolated to the elbow station (cap-free); (C) landmark-picked epicondyle and styloid midpoints. Recommended: B. B puts the forearm stretch at 1.139 against a gate of 1.133, so the record decides the forearm gate in the same commit. The gate's sigma (17.3 mm, the knee anchor SD) is an assumption set before the result, and the sheet's forearm length is not a free variable (ADR 0007 D1). The record states its basis for any change to the gate and shows the old value beside the new; the other route is re-sculpting the arm-length sliders (memo 39), which removes the stretch at its source but makes every arm cache stale.

The record also settles the segment frame roll. The shortest-arc rotation leaves the upper arm's +x 0.32 degrees from the mesh's anterior but the forearm's 16.5 degrees, so a forearm part designed in the ISB frame would sit twisted against the mesh.

If the record changes the nodes, the arm bodies, ledgers and closure are rebuilt and the 0.5% closure and the arm gates rechecked in the same commit, and ADR 0007 D2 and D11 are amended by reference to the record. Blocks rm.v1-upper-arm-characterized.

The number 0042 is the next free record number when written; edit the path if records are written in a different order.
