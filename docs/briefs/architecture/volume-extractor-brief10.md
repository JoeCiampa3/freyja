Brief 10: ADR 0042 committed, the new implementation leaf, and the v3 arm sculpt generated and evaluated in memory. Context: memos 43, 50 and 51; ADR 0007; docs/briefs/architecture/volume-extractor-brief9.md.

Step 0. Save this prompt verbatim as docs/briefs/architecture/volume-extractor-brief10.md, repoint CLAUDE.md's architecture brief line to it, and commit those two changes alone, before anything else.

Tests: run fy test --quick once after Phase 1's commits and once before Phase 2's commit. No full suite in this session. Use fy state --no-run for the memo's STATE line.
Timebox: Phases 1 and 2 in about 45 minutes. If an item would run long, report what it needs and move on.

PHASE 1. Records (no computation)

1.1 Write decisions/0042-arm-joint-anchors.md exactly as given between the markers below. In the same commit (the changes are coupled), make these three edits:
  (a) Append to ADR 0007's `## Amendments`:
      "- 2026-10-30. D2 (the arm nodes, the arm stretch gate, the arm frame roll) and D10 (the arms take the 8% gate) amended by adr-0042, and D1 (the baseline sculpt) when its v3 is committed; D11's arm item closed in place."
  (b) In ADR 0007 D11, replace
      "the elbow and wrist nodes are still on the skin and open, and the forearm frame's roll is 16.5 degrees from the mesh's anterior (memo 43); both are decided in rm.v1-arm-joint-anchors-decision."
      with
      "the elbow and wrist nodes and the arm frame roll are decided in adr-0042 (memos 43, 50, 51)."
  (c) In CONVENTIONS section 3 (CAD frame), after "for the humerus, y runs from the elbow joint centre to the glenohumeral centre.", insert:
      " For the forearm, the reference posture is the model's zero, neutral rotation (thumb forward, palm toward the thigh; adr-0042): x is anterior and z lateral in space in that posture, and z is not the radial side."

1.2 Roadmap, one commit:
  (a) Create roadmap/nodes/rm.v1-arm-sculpt-v3.md exactly as given between its markers below.
  (b) In rm.v1-upper-arm-characterized, add rm.v1-arm-sculpt-v3 to blocked_by and keep the existing entries.
  (c) In rm.v1-volume-extracted, replace
      "The sculpt is not an open question: D7 is an observation with no re-sculpt, and the arm stretches (1.124 and 1.120) are accepted against the 2 sigma / L gate (memo 39) until that decision settles them."
      with
      "D7 is an observation with no re-sculpt of the trunk; the arms are re-sculpted to the sheet's lengths under adr-0042 (rm.v1-arm-sculpt-v3) and then take the 8% stretch gate, with the upper arm's fallback recorded there."
  The roadmap must validate with 0 errors.

1.3 Memo 51's wording fixes, own commit; show the diffs in the memo:
  - the manifest's `note` should say it also lists the four arm-length targets (pinned for adr-0042);
  - `retrieved` should give 2026-10-25 for the 161 files and 2026-10-29 for the four arm targets;
  - data/makehuman/SOURCE.md's "161 files read" should become 165, with the four arm targets named as such.

PHASE 2. Read-only evaluation
Write nothing to tracked files under data/envelope, tools/ or checks/. Candidate files go to the gitignored data/makehuman/cache/v3-candidate/.

2.1 Full B on v2, right side. Build the adr-0042 D1 nodes and the D4 roll. Report:
  - the upper-arm and forearm stretches;
  - closure;
  - the elbow and wrist nodes' distance to the skin;
  - the elbow placeholder's margin, measured the same way as the 10.97 mm proud figure.
  Lengths may now be reported.

2.2 Weights. For measure-upperarm-length-incr and measure-lowerarm-length-incr (pinned, 75b1c8b), solve the weight w in [0, 1] at which v2 + w x delta (body vertices only) gives a D1 node-to-node length equal to the sheet's within 0.1 mm. Recompute the D1 nodes at every step, since they move with the mesh. Report w and the residual.

2.3 Candidate. Write analysis/makehuman_v3.py (new, authored). It reads the pinned targets through the manifest, verifies their hashes, and writes:
  - data/makehuman/cache/v3-candidate/freyja-body-v3.obj, with the same topology, face order and OBJ conventions as v2;
  - freyja-body-v3.mhm: v2's .mhm plus the two modifier lines at the solved weights, in v2's format.

2.4 Evaluate the candidate in memory against adr-0042 D3:
  - C1: both arm stretches within 8%;
  - C2: closure within 0.5%;
  - C3: the SJC moves at most 2 mm, with the trunk registration rerun on v3;
  - C4: no trunk body (pelvis, abdomen, thorax, head and neck) changes volume by more than 0.5%.
  Give a table: criterion, measured value, limit, pass or fail. Also report, with no criterion attached:
  - the leg bodies' changes;
  - the sculpt volume and mass base;
  - the D8 comparators and the D7 share table;
  - the elbow placeholder's margin on v3.
  If C3 or C4 fails, evaluate the forearm-only fallback the same way.

2.5 Commit analysis/makehuman_v3.py and the memo. Stop here. Do not start Phase 3.

PHASE 3. Only when Joe says "proceed to Phase 3". Listed here so the plan is on record.
  - Joe has opened the candidate .mhm in MakeHuman and entered v3's Blender volume in data/envelope/body_density.json.
  - Write tests first in tools/envelope/arms.py for the D1 nodes, the D4 roll and the 8% arm gate. Each needs a mutation test that fails on, respectively, a skin-vertex node, the shortest-arc roll, and the retired 2 x 17.3 mm / L gate.
  - Commit v3 (.obj and .mhm) into data/makehuman/ beside v2, switch the baseline, and update the CONVENTIONS section 2 rows (the tools/envelope gate text, the data/makehuman baseline) in the same commit.
  - Rebuild the arm bodies, ledgers, free ledgers, examples and closure, plus the trunk if the SJC moved; rerun the gates.
  - Log the outcome with the measured C1 to C4 as an Amendments line on adr-0042, and add ADR 0007's D1 line.
  - Run the full suite once. Write the memo. Joe signs off rm.v1-arm-sculpt-v3.

Output: the next free memo, with the C1 to C4 table, what would change each conclusion, your mistakes, and questions. No recommendation beyond reporting the criteria.

===== BEGIN decisions/0042-arm-joint-anchors.md =====
---
id: adr-0042
status: accepted
date: 2026-10-30
links: [adr-0007]
---
## Context

ADR 0007 D2 registers each arm segment by a rigid rotation about its proximal joint centre and an axial stretch onto the sheet's joint-centre nodes. It puts the elbow and wrist nodes on Ruler chord vertices "on or near the skin", and gives the arms a stretch gate of 2 x sigma / sheet length with sigma = 17.3 mm (the knee anchor SD). Three findings reopened that (D11, amended 2026-10-28):

- The elbow node is the midpoint of two skin vertices. It sits 4.0 mm under the lateral skin and about 30 mm lateral of the section centre line; the wrist node is on the skin (0.07 mm) (memo 43). The room the oracle reports at the elbow is one-sided: a placeholder on the axis sits 10.97 mm proud of the skin. The cause is the anchor, not the roll, the bisector cap or a slender mesh: the elbow's skin breadth, 66.8 to 68.3 mm, is about the 75th percentile of NHANES III women's elbow breadth.
- The arm stretch is a known length shortfall, not anchor uncertainty. The sculpt's upper arm and forearm are 12.4% and 12.0% short of the sheet on the skin nodes, and the forearm is 11% short of ANSUR II radiale-stylion scaled to stature (memo 38). Sigma was chosen after memo 38 had shown those stretches, so the arm gate was sized with them in view. Moving the elbow to the section centre line puts the forearm at 1.139 against its 1.133 gate (memo 43).
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
- The elbow placeholder on the axis is expected to move from 10.97 mm proud of the skin to inside it, since the D1 elbow node is 28.6 mm from the skin on v2 (memo 43). The rebuild reports the measured margin.
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
===== END decisions/0042-arm-joint-anchors.md =====

===== BEGIN roadmap/nodes/rm.v1-arm-sculpt-v3.md =====
---
schema: roadmap-node/2
id: rm.v1-arm-sculpt-v3
title: "Arm lengths conformed to the sheet: v3 sculpt generated from the pinned arm-length targets, arm bodies rebuilt on the adr-0042 nodes and roll, gates rechecked"
short: Arm sculpt v3
parent: rm.v1-volume-extracted
blocked_by: [rm.v1-arm-joint-anchors-decision]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: manual
---
ADR 0042 D1 to D4; memos 50 and 51; brief 10. The sculpt's arms are 12.4% and 12.0% short of the sheet. v3 adds the pinned MakeHuman arm-length targets at the weights that close each segment on the D1 nodes, and is generated by analysis/makehuman_v3.py, not by a manual export. It becomes the baseline only if adr-0042's C1 to C4 hold in memory. If C3 or C4 fails, it takes the forearm target only, and the upper arm's stretch is recorded as a known deviation.

Joe signs off when all of the following hold:
- v3 (both targets, or the forearm-only fallback) is committed beside v2, with its Blender volume in data/envelope/body_density.json;
- the arm bodies, ledgers, free ledgers, examples and closure are rebuilt on the D1 nodes and the D4 roll;
- the arm stretches pass the 8% gate or carry D3's recorded deviation, and closure is within 0.5%;
- adr-0042's Amendments log the measured C1 to C4.

The manual criterion is deliberate: the outcome branches, so no single metric fits. Blocks rm.v1-upper-arm-characterized.
===== END roadmap/nodes/rm.v1-arm-sculpt-v3.md =====
