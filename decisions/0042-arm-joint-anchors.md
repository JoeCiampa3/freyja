---
id: adr-0042
status: accepted
date: 2026-10-30
links: [adr-0007]
---
## Context

ADR 0007 D2 registers each arm segment by a rigid rotation about its proximal joint centre and an axial stretch onto the sheet's joint-centre nodes. It puts the elbow and wrist nodes on Ruler chord vertices "on or near the skin", and gives the arms a stretch gate of 2 x sigma / sheet length with sigma = 17.3 mm (the knee anchor SD). Three findings reopened that (D11, amended 2026-10-28):

- The elbow node is the midpoint of two skin vertices. It sits 4.0 mm under the lateral skin and about 30 mm lateral of the section centre line; the wrist node is on the skin (0.07 mm) (memo 43). The room the oracle reports at the elbow is one-sided: a placeholder on the axis sits 10.97 mm proud of the skin. The cause is the anchor, not the roll, the bisector cap or a slender mesh: the elbow's skin breadth, 66.8 to 68.3 mm, is about the 75th percentile of NHANES III women's elbow breadth.
- The arm stretch is a known length shortfall, not anchor uncertainty. The sculpt's upper arm and forearm are 12.4% and 12.0% short of the sheet on the skin nodes, and the forearm's Ruler chord (223.5 mm) is 11% short of ANSUR II radiale-stylion scaled to stature (memo 38); node to node it is 7.9% short (memo 52). Sigma was chosen after memo 38 had shown those stretches, so the arm gate was sized with them in view. Moving the elbow to the section centre line puts the forearm at 1.139 against its 1.133 gate (memo 43).
- The shortest-arc rotation leaves the upper arm's +x 0.32 degrees from the mesh's anterior and the forearm's 16.55 degrees (memo 43), so a forearm part designed in the ISB frame would sit twisted against the mesh.

Brief 9 (docs/briefs/architecture/volume-extractor-brief9.md, sha256 5e075048104b) tested the centre-line anchor against three thresholds Joe set in the brief before any result: T1 5 mm, T2 1 mm, T3 5 degrees. The brief was committed after the run with its text unchanged (memo 50, mistakes). Results (memos 50 and 51):

- T1 tripped. The midpoint of the mediolateral skin extremes at station -230 mm lies 5.27 mm from the centre-line elbow node: 4.15 mm anteroposterior and 3.25 mm mediolateral. Over neighbouring stations, with the mediolateral direction turned by up to 5 degrees, it ranges from 4.13 to 6.78 mm, in vertex steps. The other T1 numbers pass: the two segments' centre lines are 4.30 mm apart at the elbow plane (closest approach 4.17 mm) and 1.95 mm apart at the wrist; the wrist midpoint is 2.33 mm from the node (1.96 to 4.57 mm over the clean stations).
- T2 held. A second iteration moves the elbow 0.24 mm and the wrist 0.26 mm, and the fit trim moves the nodes by at most 0.32 mm. The centre lines are straight (residual rms at most 0.48 mm).
- T3 failed. The line through the mediolateral extremes spreads 9.8 to 10.2 degrees over the distal third of the forearm. The construction took the mediolateral extremes as the styloids, which assumes a supinated forearm; the model's forearm is not supinated.
- The model has no pronation-supination joint. The elbow hinge is about (0, -1, 0), the wrist hinge about (1, 0, 0), and the hand ellipsoid is 0.04 by 0.015 m along x and y, so at zero the forearm is in neutral rotation, thumb forward and palm toward the thigh (memo 50 section 4c, inferred). `isb_to_segment` assumes no forearm posture, so a forearm part inherits the model's zero (memo 51).
- Observation, not a test (the window was chosen after looking). Over stations -220 to -250 the distal forearm's largest Feret diameter (45.8 mm, against a mediolateral breadth of 33.7 mm at -254.4) stays within 1.4 degrees of one direction, about 12 degrees from the anterior-preserving x in the supination sense. The sculpt's distal forearm is widest roughly anteroposteriorly, as a forearm near neutral rotation is.
- The MakeHuman arm-length targets (pinned, 75b1c8b) cover both shortfalls with more than 2x margin, at weights of about 0.41 (upper arm) and 0.43 (forearm) on the skin nodes. The forearm target moves only the forearm and hand. The upper-arm target also moves the shoulder girdle (34 of 57 vertices, up to 18.7 mm at full weight) and 23 axilla and chest-wall vertices (up to 14.3 mm), on both sides; at the weight needed, about 0.4 of that.

## Decision

D1. **Joint-centre rule.** An arm joint centre is the proximal segment's skin-section centre line, extrapolated to the joint station: the elbow on the upper arm's line, the wrist on the forearm's. The line is a straight least-squares fit of exact plane-section centroids (no voxels, no cap) on 5 mm stations from -40 mm to -(L - 40) mm in the segment frame. It is computed once in the frame defined by the Ruler-chord nodes and not iterated (memo 50 section 1). The SJC stays the sheet's, through the trunk registration. The hand's proximal node is the wrist node. For the arms, this replaces ADR 0007 D2's nodes on the Ruler chord vertices "on or near the skin".

D2. **Error bar.** T1 tripped and is recorded as tripped. The rule is kept because no candidate does better (see the rejected options). The elbow node carries an error bar of 7 mm, mostly anteroposterior, and the wrist node 5 mm: the upper ends of the cross-checks' ranges in memo 50. An elbow clearance or interface position quoted to better than 7 mm anteroposteriorly is inside the anchor's uncertainty, and results say so.

D3. **Arm length.** The sculpt's arms are conformed to the sheet at the source. v3 is v2 plus the pinned MakeHuman targets `measure-upperarm-length-incr` and `measure-lowerarm-length-incr`, at the weights that make each segment's D1 node-to-node length equal the sheet's within 0.1 mm. It is generated by a committed script from the pinned files, never by a manual export, and its `.mhm` carries the same weights. The arms then take ADR 0007 D10's 8% stretch gate, and the 2 x sigma / L arm gate (sigma = 17.3 mm) is retired. v3 becomes the baseline sculpt (ADR 0007 D1) only if all four criteria hold, evaluated in memory before anything is written:

- C1. Both arm stretches are within the 8% gate.
- C2. Closure is within 0.5% (D10).
- C3. With the trunk registration rerun on v3, the SJC moves by at most 2 mm.
- C4. No trunk body (pelvis, abdomen, thorax, head and neck) changes volume by more than 0.5%.

If C3 or C4 fails, v3 takes the forearm target only. The upper arm then keeps v2's length, and its stretch (1.1147 with the D1 elbow, memo 43) is recorded as a known deviation from the 8% gate, with this record as its reason, never as a pass. Any other failure stops for Joe. Before the commit, Joe looks at the candidate in MakeHuman and enters its Blender volume (D10, `data/envelope/body_density.json`).

D4. **Frame roll.** Each arm segment's rotation is the shortest-arc rotation onto the zero-pose axis, followed by the twist about the segment axis that maps the mesh's +x, projected onto the section plane, onto the frame's +x (anterior-preserving). The hand takes the forearm's. The upper arm's 0.32 degrees and the forearm's 16.55 degrees go to 0. The styloid-line construction is not used (T3).

D5. **Forearm zero.** In v1 the forearm's rotation is fixed at neutral, thumb forward and palm toward the thigh, as the model's zero already has it. The forearm's CAD frame takes that posture, so its x is anterior and its z lateral in space, and z is not the radial side. Pronation and supination come in a later version with the dexterous hands, and that joint's zero is neutral, so this record and any forearm CAD made under it stay valid. `isb_to_segment` is unchanged (memo 51).

D6. **Amendments.** This record amends ADR 0007 D2 (the arm nodes, the arm stretch gate, the arm frame roll) and D10 (the arms take the 8% gate), and amends D1 (the baseline sculpt) when v3 is committed. ADR 0007 keeps its status. D11's arm item is closed in place.

## Consequences

- The elbow node moves about 30 mm and the wrist node about 15 mm (memo 50), and the bisector cut moves with the elbow. In the commit that brings v3 in, the arm bodies, ledgers, free-space ledgers, silhouettes, examples and closure are rebuilt on the D1 nodes and the D4 roll, and the gates are rechecked.
- The elbow placeholder on the axis is expected to move from 10.97 mm proud of the skin to inside it, since the D1 elbow node is 28.03 mm from the exact skin on v2 (memo 52; memo 43 gave 28.6 mm, the same node read off the upper arm's 2 mm voxel field in its stretched frame). The rebuild reports the measured margin.
- A re-sculpted arm grows the mesh volume: about +0.4 l at the weights needed (memo 50 section 5). The sculpt mass, the D8 comparators and the D7 share table move; they are reported, not re-decided. The upper-arm target reaches the shoulder girdle and the axilla, and C3 and C4 bound what that does to the trunk.
- The sigma = 17.3 mm arm gate leaves `tools/envelope/arms.py` and CONVENTIONS section 2 in the same commit.
- `rm.v1-upper-arm-characterized` waits on the implementation, `rm.v1-arm-sculpt-v3`, as well as on this record.
- The outcome (v3 with both targets, or the forearm-only fallback) is logged in this record's Amendments with the measured C1 to C4.

## Rejected options, and why each one died

- (A) Keep the skin nodes and carry an explicit lateral offset for the joint centre. It puts two elbows in one system, leaves the axis on the lateral surface 4.3 degrees off the centre line, and leaves every section off-centre. Its one advantage was that it did not touch the gate.
- (C) Landmark-picked epicondyle and styloid midpoints as the definition. These are subjective picks on a sculpt with no bony features. Their programmatic analog, the skin-extremes midpoint, is noisier than the centre line (4.1 to 6.8 mm across neighbouring stations, in vertex steps, against 0.32 mm for the trim), so it serves as the cross-check instead.
- The bisector-cut and uncut centroids. They are biased by the 28% slice and by the forearm overlap (memo 43 section 6).
- Raising the forearm gate to clear 1.139, or re-basing sigma on an elbow source now. The gate was sized with the stretch in view, so a second accommodation of the same mismatch would move a threshold after the result. An honest elbow-specific sigma would likely be smaller than the knee's and would tighten the gate.
- Keeping the stretch as a labelled tolerance for both arms. That leaves a known length defect in the segment that hosts the first CAD part. It is kept only as the upper arm's fallback (D3).
- Redefining T1's cross-check after the trip (the largest Feret diameter, or station -225). That is the post-hoc rescue the thresholds exist to prevent.
- The styloid-line roll, which failed T3 and assumed a supinated forearm. The shortest-arc roll, whose 16.55 degrees are an artefact of the rotation convention.
- A manual MakeHuman export for v3. It cannot be reproduced from the repo; the targets are linear and pinned, so v3 is a scripted output.

## Amendments

- 2026-10-30. Outcome: v3 with both targets is the baseline (weights 0.381365 and 0.512871, memo 52). C1 1.00001 and 0.99997; C2 -0.430%; C3 0.007 mm; C4 worst thorax -0.026%. The MakeHuman export of the .mhm agrees with the scripted mesh to 0.017 mm, and its Blender volume is 52.7178 l against 52.7155 l. The elbow placeholder is 13.93 mm inside the skin. On v3 the forearm (259.4 mm, the sheet's) is 3.1% longer than ANSUR II radiale-stylion scaled to stature, a surface-landmark distance, context only. In place: Context's ANSUR comparison now names the Ruler chord; Consequences' elbow-to-skin distance is the measured 28.03 mm.
