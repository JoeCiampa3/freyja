STATE: base c558e05c298b | brief architecture sha256:e93e6b785bae, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1780/1784 | dirty yes

# Memo 39: arms, reservations, corridor and hip check (volume-extractor brief 8)

Brief: `docs/briefs/architecture/volume-extractor-brief8.md`, with your memo 38 decisions (the arm gate 2 x 17.3 mm / sheet length, the hand with no stretch, ANSUR arm lengths as context, closure unchanged). Phase A and Phase B are both done in this session; no stop condition tripped after your decision (the stretches 1.124 and 1.120 are inside their gates of 13.6% and 13.3%). **Two gates failed on my first arm build (closure +0.531%, arm field +2.5% over the raster); the cause was my cut rule at the elbow, not a tolerance, and I changed the method, not a number. Read finding 2.** All 35 gates pass now.

## Decision summary

- **What it means for Freyja.** All ten sheet segments now exist as voxel bodies and sum to the mesh volume within 0.333% (gate 0.5%), nothing left over. The sculpt's arms are 11% shorter than the sheet's and fit the sheet's arm masses at 1.27 to 1.33 kg/l (whole arm 1.054 raw ratio). The three spine modules do not fit the abdomen at all, fit the pelvis (taking 44% of its mass budget) and the thorax (25%). A 56 mm column through the trunk fits best 5 mm behind the hip line; the sim's stack is 12 to 52 mm behind that.

| Number | Value | Reference |
|---|---|---|
| Arm stretch, upper arm / forearm, against own gate | 1.124 / 1.120 against 13.6% / 13.3% | legs' gate 8% (2 x 17.3 / 398 = 8.7%); memo 38: 1.124 / 1.120 |
| Rotation from vertical, upper arm / forearm; elbow bend | 43.2 / 56.2 deg; 42.4 deg | A-pose; zero pose 0 deg |
| Closure, bodies only, arms included | +0.333% (52.506 l against 52.332 l); conform effect +0.238 l, arms +0.380 l | gate 0.5%; memo 36 -0.389% with the arms unbuilt; your expectation +0.3 l |
| Whole arm raw ratio (mass share / volume share); forearm; hand | 1.054; 1.078; 1.028 | 1.00 = the sheet's reference women |
| Lumped abdomen-to-thigh raw ratio (frame bodies) | 1.103 | memo 33: 1.099 (MSR10 region) |
| Three AKH70 modules (D 90 x L 81.5 mm, clearance 5 mm): best skin margin, abdomen / pelvis / thorax | none fits (even at 0) / 17.0 mm / 13.5 mm | design shell t = 5 mm |
| Corridor column: best d, least diameter, cylinder (0.8 x) | -5 mm, 70 mm (abdomen, station 31 mm), 56 mm | sim stack axis -56.7 (zero), -35.2 (stance), -31.8 to -17.4 (lean) mm |
| Hip: frames disagree (signed skin distance / lateral step) | 16.2 mm / 17.3 mm | flag limit 5 mm |

- **Decisions for you.**
  1. **Which body takes the spine modules.** The abdomen cannot (no three 90 mm modules in its section: at a section 60 mm below the TJC the largest inscribed circle is 84.5 mm in radius, which leaves a feasible-centre set too small for three centres 95 mm apart). The thorax: margin 13.5 mm, 25% of its sheet mass, the rest must carry 1.05 kg/l if the modules are inside its mass budget (1.40 if they are extra), against 1.19 without them. The pelvis: margin 17.0 mm, but the modules are 44% of its 9.49 kg and the rest would carry 1.72 (inside) or 3.08 kg/l (extra) over a free 3.08 l. **Recommended: the thorax.** Also say whether the modules are inside the body's mass budget or additional (the file's `v1_ballast: false` does not say) and whether their axes are vertical (my assumption, nothing in the file).
  2. **The trunk's zero-pose x offsets** (memo 37 follow-up 2, now with a number for the fitting column): the column that fits best is at -5 mm; the sim's stack is 51.7 mm behind that in the zero pose, 30.2 in the design stance, 12.4 (CJC) to 26.8 mm (LJC) in the stance with the lean. **Recommended: take the design stance as the reference and move the zero-pose stack forward by about 30 mm; a model/sheet change, not mine.**
  3. **The elbow and wrist nodes are on the skin** (finding 4): the wrist node is 0.07 mm inside the skin, the elbow 4.0 mm, so each arm segment's axis runs near its lateral surface and a part at the model's axis is 17 to 28 mm from the arm's centre line. You declined re-anchoring picks; I did not re-anchor. **Recommended: leave until an arm part is placed, then re-pick the radial styloid and the olecranon.**
  4. **The hip** (finding 6): flagged. **Recommended: leave (cross-sections stay unchanged, ADR 0007 D2); place a hip part against one frame, the thigh's, and state which.**
  5. **ADR 0007 and `rm.v1-volume-extracted`.** The ADR is edited, still `proposed`; the proposed `done_when` is in section 9. **Recommended: accept the ADR after you read item 10's edits, then apply the `done_when`.**
- **What would change the conclusion.** The elbow and wrist anchor vertices (the stretches are node-to-node lengths: 5 mm on the wrist moves the forearm stretch by 2%); the sigma of 17.3 mm (a gate of 2 x 17.3 / L; at sigma 10 mm the arms would exceed it); the module orientation (a horizontal module is a different search); a different sculpt (the 11% arm shortfall is the sculpt's).

## 1. Gate table (`fy envelope gates`, v2, chords, 2 mm)

All 35 pass. New in this brief (rows of `leg_R_trial.json`):

| Gate | Result | Numbers |
|---|---|---|
| 1 topology and watertight, upper_arm_R / forearm_R / hand_R | pass | boundary edges near the body 0, non-manifold 0, odd-parity columns 0 (the arm builds count the parity along x over every triangle that overlaps the grid in y and z, `field.build_segment(full_ray=True)`; finding 3) |
| 2 arms: stretch within 2 x 17.3 mm / sheet length | pass | upper arm 1.1244 (+12.44%, gate 13.56%); forearm 1.1198 (+11.98%, gate 13.34%); hand 1.0000 |
| 3b arms: field volume (unconformed, both sides) within 1% of the raster accounting of arms and girdles | pass | field 3.6094 l, raster 3.6118 l (-0.067%) |
| 5 oracle examples: cylinder in the upper arm; box in the forearm; union across the elbow | pass | cylinder +4.59 / -10.44 mm; box +3.05 / -12.47; rod +3.39 mm in the union (the upper arm alone overruns by 80.0 mm) / -13.87 |
| 7 closure, arms included | pass | +0.333%; no remainder; conform effect +0.2375 l (arms +0.3802 l); raster minus mesh -0.0006 l |

Every earlier gate is unchanged (legs, trunk bodies, volume against Blender, the trunk examples). Gate 3 (matched-station areas) is not run for the arms: the arm field is taken from a rotated mesh, so a layer raster has no matching section; the substitute is 3b and the interface sections (finding 5). `data/envelope/arm_bodies.json` is the committed result.

## 2. Findings

1. **The arm registration (item 1).** Mesh nodes, right arm (the Ruler lists are the left arm's; the right takes the nearest vertex to each mirrored position, 0.00 mm away): SJC (15.57, -192.33, 1349.24) mm, elbow (18.73, -347.62, 1183.69), wrist (176.96, -457.39, 1054.91), fingertip (296.82, -501.64, 923.99). Node-to-node lengths against the sheet:

| Segment | Mesh (mm) | Sheet (mm) | Stretch | Gate | Rotation from vertical |
|---|---|---|---|---|---|
| Upper arm, SJC to elbow | 227.00 | 255.23 | 1.1244 | 13.56% | 43.17 deg |
| Forearm, elbow to wrist | 231.67 | 259.44 | 1.1198 | 13.34% | 56.23 deg |
| Hand, wrist to fingertip | 182.93 (extent along the forearm axis 175.6) | 74.57 (SCS length only) | 1.0000 | none | forearm's rotation; the hand's own axis is 16.3 deg off the forearm's |

   The elbow bends 42.4 deg. ANSUR II female ratios (context only, `data/ansur2/ratios.json` now carries `arm_lengths`): shoulder-elbow 348.7 mm (acromion to olecranon; the mesh SJC-to-elbow is 227.0, not comparable), radiale-stylion 251.7 mm (the mesh forearm is 0.920 of it, **8% short**, as you said), forearm-hand 458.9 (mesh elbow to wrist plus the hand's extent 407.3), hand length 188.9 (mesh wrist to fingertip 182.9).

2. **My first cut rule failed two gates, and I changed the method.** With each segment cut by its own plane (perpendicular to its axis), the elbow's planes overlap on the inner side and leave a gap on the outer: measured on the raster, 0.0475 l counted twice and 0.0079 l lost per side. That gave gate 3b +2.497% (field 3.7019 l against 3.6118 l) and closure +0.531% (limit 0.5%). I did not touch a tolerance; I gave the overlap cells to one body by the bisector plane of the two axes through the EJC (a cell is the upper arm's on the proximal side, the forearm's on the other), which leaves the gap (0.008 l a side) and removes the double count. The wrist needs no such rule (the hand takes the forearm's rotation). The brief says "cut at the EJC plane"; the bisector is a plane through the EJC with a different normal. If you want the perpendicular planes, the closure is +0.531% and gate 7 fails.

3. **Two defects in my first build, found and fixed.** (a) The vertex label for "arm" also marks the ears (a separate piece of the head's layers), which stretched the first upper-arm field to 294 mm above the SJC; vertices above the mesh CJC are now excluded (the girdle's top is 36 mm above the SJC). (b) The field's ray parity used only the triangles near the grid box, so for a rotated arm 153 columns had an odd crossing count; `field.build_segment` has a `full_ray` option (arms only; the legs and trunk are byte-identical, checked by rebuilding).

4. **The nodes are on the skin.** The Ruler chord ends are skin vertices. Signed distance of the nodes to the skin (positive inside): SJC 34.5 mm; elbow 4.03 mm (as the upper arm's distal node and the forearm's proximal); wrist 0.07 mm (forearm's distal), -0.06 mm (hand's proximal). The inscribed centre of the section at the elbow is 28.5 mm from the axis, at the wrist 16.7 mm. The section shapes are unaffected (a rotation leaves them as they are), but each arm segment's frame axis is near its lateral skin, not along its centre line. Reported, not fixed.

5. **The arm bodies** (right; conformed volumes; all numbers in `data/envelope/{upper_arm,forearm,hand}_R.yaml` and `_sections.csv`, every 10 mm; silhouettes `_sagittal.png`, `_coronal.png`; the inspect layer `envelope_arms_t5.obj` is in the original-mesh frame because no assembled arm exists):

| Body | Field length (mm) | Skin (l) | Unconformed (l) | Conform (l) | Inner t = 3 / 5 / 8 / 10 mm (l) | Required density, skin / t5 (kg/l) | Min inscribed radius (mm) and station | Pinch stations |
|---|---|---|---|---|---|---|---|---|
| upper arm | 291.2 (SJC at station 36.0) | 1.1053 | 0.9830 | +0.1223 | 0.937 / 0.830 / 0.683 / 0.594 | 1.294 / 1.723 | 18.25 at 40 (search 36 to 276) | none |
| forearm | 259.4 | 0.6338 | 0.5660 | +0.0678 | 0.509 / 0.432 / 0.329 / 0.268 | 1.333 / 1.957 | 16.03 at 259.4 (search 15 to 259.4) | none |
| hand | 176.0 | 0.2557 | 0.2557 | 0 | 0.166 / 0.119 / 0.068 / 0.044 | 1.271 / 2.733 | 6.75 at 150 (search to 156) | none |

   The sheet masses are 1.43, 0.845 and 0.325 kg. With and without the joint-zone slab (h = 25 mm): upper arm 1.1053 l with, 1.0006 l without the elbow slab (0.0711 l) and the SJC sphere (0.0336 l, owned jointly); **with the shoulder girdle 1.1053 l, without it 0.8148 l (girdle 0.2904 l stretched, 0.258 l unstretched)**, without girdle and zones 0.7102 l. Forearm 0.6338 l, without its elbow slab (0.0702 l) and wrist slab (0.0313 l) 0.5323 l. Hand 0.2557 l, without the wrist slab (0.0397 l) 0.2160 l. **The girdle is 0.252 l in the raster, not the brief's 0.296 l (memo 35's number was before brief 6 moved the shoulder plane to the sheet's SJC, 192.33 mm lateral).** Hand: bounding box 110 x 94 x 174 mm (x anterior, y lateral, axial), the wrist interface section at the WJC plane 1221 mm2, perimeter 106 mm, 46 x 34 mm, inscribed radius 16.1 mm. Interfaces: the section areas on the two sides of the elbow 1141.6 / 1133.2 mm2 (-0.74%), of the wrist 1233.1 / 1221.2 (-0.96%). The minimum radii skip the last 15 mm at the elbow cut (ELBOW_CUT_MM: the slanted end face gave 12.8 mm there, an artefact of the cut) and the hand's fingertip cap.

6. **Left and right.** The left arm built by the same code from the left Ruler lists: upper arm -0.86%, forearm -0.01%, hand +0.05%, whole arm -0.47% (left minus right, conformed volumes); the raster's girdle volumes 0.2608 l left against 0.2513 l right (+3.8%). The closure counts the right twice.

7. **Closure and the conform's volume change.** Sum of the conformed bodies 52.5056 l against the mesh 52.3315 l: +0.333%. By body (conformed minus unconformed): upper arm +0.1223 l, forearm +0.0678 l, hand 0 (x 2 sides: +0.3802 l), legs and trunk -0.1427 l (as memo 35); the total effect is +0.2375 l. The cell accounting itself closes to -0.0006 l. The arm field against the raster accounting of arms and girdles: -0.067%.

   The final share table (denominator: the sum of the conformed volumes, 52.506 l; sheet masses over the sheet's total 64.935 kg; **raw ratio primary**):

| Row | Role | Volume (l) | Volume share | Sheet mass (kg) | Mass share | Raw ratio | Required density (kg/l) |
|---|---|---|---|---|---|---|---|
| head and neck | result | 3.781 | 7.20% | 4.355 | 6.71% | 0.931 | 1.152 |
| thorax | result | 15.842 | 30.17% | 17.095 | 26.33% | 0.873 | 1.079 |
| forearm (both) | result | 1.268 | 2.41% | 1.690 | 2.60% | 1.078 | 1.333 |
| hand (both) | result | 0.511 | 0.97% | 0.650 | 1.00% | 1.028 | 1.271 |
| whole arm (both) | result | 3.990 | 7.60% | 5.200 | 8.01% | 1.054 | 1.303 |
| lumped abdomen to thigh | result | 22.821 | 43.46% | 31.135 | 47.95% | 1.103 | 1.364 |
| shank (both) | result | 4.941 | 9.41% | 5.850 | 9.01% | 0.957 | 1.184 |
| foot (both) | result | 1.132 | 2.16% | 1.300 | 2.00% | 0.929 | 1.149 |
| upper arm (both) | diagnostic (top cut unknown) | 2.211 | 4.21% | 2.860 | 4.40% | 1.046 | 1.294 |
| abdomen | diagnostic | 4.449 | 8.47% | 2.665 | 4.10% | 0.484 | 0.599 |
| pelvis | diagnostic | 5.533 | 10.54% | 9.490 | 14.61% | 1.387 | 1.715 |
| thigh (both) | diagnostic | 12.840 | 24.45% | 18.980 | 29.23% | 1.195 | 1.478 |

   The lumped row here is the frame bodies (abdomen + pelvis + thighs: planes LJC, TJC and the KJC), memo 33's was the MSR10 region (1.099): 1.103. The lumped 9.4% shortfall of D7 (1 / 1.103 = 0.907) stands; the thorax's volume share is 14.5% above its mass share (raw ratio 0.873), the whole arm's 5% below (1.054).

## 3. The reservations (item 5, the file `data/envelope/reservations.yaml`)

3 x pi/4 x 90^2 x 81.5 = 1,555,442 mm3 against 1.55e6 mm3: +0.35%, within 2%. Modules as reserved registry components (cylinders, clearance 5 mm, 1.4 kg each, vertical axes, modules at one height; `data/envelope/reserved/<body>.yaml`, `components/1` in the model frame, generated by `fy envelope reserve`; none is written for the abdomen). The search takes the largest skin margin m at which three modules of the file's size fit (each inside {skin sd >= m} over its length, centres at least 95 mm apart), at the height with the least offset of their centroid from the model's trunk axis; the margin is a lower bound, short by up to the 6 mm centre lattice.

| Body | Best arrangement | Skin margin m | Centroid from the model's trunk axis | Inner volume at t = 5 / free left / occupied (l) | Largest free sphere before / after (mm) | Sheet mass; modules | Density the rest must carry: inside the mass budget / modules extra / without modules (kg/l) |
|---|---|---|---|---|---|---|---|
| abdomen | none | none even at 0 | - | 4.010 / (4.010) / 0 | 180.8 / - | 2.665 kg; 4.2 kg (158%) | exceeds the budget / 0.665 (no modules placed) |
| pelvis | station 57 mm; centres (x, y) oracle frame (-18.9, 0.7), (29.1, -83.3), (29.1, 84.7) | 17.0 mm | 69.8 mm | 5.096 / 3.081 / 2.015 | 192.5 / 82.3 | 9.490 kg; 4.2 kg (44%) | 1.717 / 3.080 / 1.862 |
| thorax | station 119 mm; centres (-24.0, -2.3), (12.0, -92.3), (12.0, 87.7) | 13.5 mm | 56.7 mm | 14.390 / 12.254 / 2.136 | 195.2 / 175.2 | 17.095 kg; 4.2 kg (25%) | 1.052 / 1.395 / 1.188 |

The oracle frame has the model's trunk axis at x = -56.72 mm; the modules sit 57 to 70 mm in front of it. In a ring of three, the pelvis arrangement has the third module on the midline at the back; the thorax's is a triangle across the chest at 119 mm below the CJC. The occupied volume includes the 5 mm clearance. Where m is at or above the design shell (5 mm) the arrangement is feasible in the sense of ADR 0007 D4: pelvis and thorax are; the abdomen has none.

## 4. The corridor sweep (item 6, `fy envelope corridor`)

Mesh frame (the trunk bodies' own: origin on the hip line, midline y = 0), design stance as the reference, the inner envelope at t = 5 mm, every 2 mm layer from the LSJ (the LJC plane, 0 mm) to the CJC (451 mm above), d from -60 to +60 mm in 5 mm steps. Least diameter by d (mm): d -35 10, -30 18, -25 30, -20 38, -15 50, -10 58, **-5 70, 0 70**, 5 58, 10 50, 15 38, 20 30, 25 18, 30 10; zero for |d| >= 40. **Best d = -5 mm** (the first of the two equal values; the minimum is the abdomen's waist: abdomen station 31 mm, 96 mm above the LSJ); least diameter 70.0 mm; the column's diameter along it, every 30 mm: 146 mm at the LSJ, 122, 94, 74, 70 (waist at 120), then 78, 94, 106, 122, 142, 158, 162 (at 331), 158, 154, 102, 78 at the CJC.

The sim's stack axis in the same x (mm, relative to the hip line), and the forward shift the best d implies (best d less the axis):

| Pose | LJC / TJC / CJC axis x | Forward shift of d = -5 mm |
|---|---|---|
| zero | -56.7 / -56.7 / -56.7 | +51.7 / +51.7 / +51.7 |
| design stance | -35.2 / -35.2 / -35.2 | +30.2 / +30.2 / +30.2 |
| stance with the ankle lean | -31.8 / -27.8 / -17.4 | +26.8 / +22.8 / +12.4 |

Corridor cylinder: the file's diameter is null, so 0.8 x 70.0 = 56.0 mm, at d = -5 mm, through the abdomen (LJC to TJC) and the thorax (TJC to CJC), as a reserved component with clearance 0 (`data/envelope/corridor/<body>.yaml`). Free-space ledgers (`data/envelope/corridor/free/<body>.yaml`, skin margin 5 mm): abdomen inner 4.010 l, free 3.699 l (corridor 0.311 l), largest free sphere 114.2 mm (180.8 mm before); thorax inner 14.391 l, free 13.582 l (corridor 0.808 l), largest free sphere 136.2 mm (195.2 mm before). The pelvis and the head and neck are not crossed. Nothing in the sim, the sheet or the model changed.

## 5. The hip registration check (item 6b, `fy envelope hip`, report only)

| Quantity | Thigh frame | Pelvis frame | Difference |
|---|---|---|---|
| Signed skin distance at the model's HJC (positive inside) | 86.5 mm | 70.3 mm | -16.2 mm |
| Lateral skin distance from the HJC at the HJC plane | 88.3 mm | 71.2 mm | -17.1 mm |
| Lateral extent of the right half at the plane: pelvis section -163.6 mm; thigh section placed by the model -180.9 (step **-17.3 mm**), placed by the mesh -164.1 (step -0.5 mm) | | | |

**Flagged: the two frames differ by more than 5 mm (all three).** The cause is the 16.83 mm hip-spacing difference (the sheet's HJC is 92.43 mm from the midline, the mesh's 75.60 mm); the conformed mesh is one surface (the sections meet to 0.5 mm) and the model places the thigh 16.8 mm lateral of where the pelvis body ends. Under the other shear target (the lateral target the mesh's own HJC centroid, -75.60 mm instead of the sheet's -92.43 mm): thigh 6.4198 l and pelvis 5.5325 l, against 6.4198 l and 5.5330 l: **no change** (a translation does not change a section or a length), only the thigh's frame origin moves (y -75.60 against -92.43 mm). Nothing was fixed.

## 6. The shoulder interface (Phase B, reported, not fixed)

Arm segment frames are anchored at the mesh's own SJC (brief 5's patch: x the thorax's centre line at the CJC plane plus the sheet's 13.81 mm, y the plane's 192.33 mm, z 77.57 mm below the CJC). The model's SJC is the thorax stack axis plus the same 13.81 mm. In the conformed mesh frame, relative to the hip line: the mesh's own SJC x = -5.05 mm; the model's -42.91 mm (zero pose), -21.36 mm (design stance), -6.01 mm (stance with the lean): **the mesh's SJC is 37.9, 16.3 and 1.0 mm ahead of the model's; y and z agree.** It is the trunk's x offset seen at the shoulder (memo 37). The arm bodies themselves are in their model frames with no offset (`frames.py`: zero for an arm); in the contract note (`docs/envelope-component-contract.md`) the arm frames, the shoulder and the hip are written down.

## 7. Item 9: the `check --segment a,b` warning (memo 37 defect)

`occupancy.component_skin_margins` now takes the registry's origin offset in the union's frame and shifts the component's points by it; `cli.py` passes it. Test first (`tests/test_envelope_union_skin_warning.py`, 2: a wide component in a wide lower body under a narrow upper one was "sticking out" by -20 mm, +50 mm after); both failed before the change. The verdict and margins were never affected.

## 8. Tolerances and parameters I chose

Yours: the arm gate (2 x 17.3 mm / sheet length, taken on the sheet length as the legs' 398.08 mm was), the hand with no stretch, closure 0.5%, area 1%, h = 25 mm zones, t = 5 mm, d range and step, the 5 mm hip flag. Mine: the bisector plane at the elbow (finding 2); ELBOW_CUT_MM 15 mm for the minimum-radius search; the upper arm's top as the highest girdle or arm vertex plus 6 mm, rounded to a voxel; the shortest-arc rotation (no roll about the axis is defined); the hand's rotation and the connected-component seed window (the mean of the hand's vertices 20 to 60 mm beyond the wrist); arm vertices only below the mesh CJC; the module search: vertical modules, one height, 6 mm centre lattice, heights every 4 mm, margin step 0.5 mm up to 30 mm, 5 mm between module surfaces, margin measured to {skin sd >= m}; the corridor: circle centred on y = 0, the sweep on 2 mm layers; the corridor cylinder with clearance 0; sections for the hip check 1 mm inside each end plane. No check tolerance or geometry value was changed, none tuned toward a result; the one method change made in response to a failing gate is finding 2.

## 9. Proposed (not applied): `done_when` for `roadmap/nodes/rm.v1-volume-extracted.md` (items 7 and 8)

The node is a stub (`blocked_by: [rm.v1-envelope-method]`). The criterion types are `decision`, `manual` and `artifact`; a leaf also needs `estimate_days`. Proposed:

```
done_when:
  type: decision
  record: decisions/0007-envelope-extraction.md
estimate_days: 0.5
```
and the node text (replacing the stub's one line, `stub: true` removed in the same commit): "Done when ADR 0007 is accepted and it is true that (1) the closure gate passes with all ten sheet segments built and no remainder (`data/envelope/leg_R_trial.json`, gate 7: the sum of the conformed bodies within 0.5% of the mesh volume); (2) a section ledger exists for each of the ten: `data/envelope/{thigh_R,shank_R,foot_R,pelvis,abdomen,thorax,head_neck,upper_arm_R,forearm_R,hand_R}.yaml` with its `_sections.csv`; (3) the reservations file `data/envelope/reservations.yaml` is Joe's and its results are in `data/envelope/reservations_result.json` and `data/envelope/corridor_result.json`, with the reserved registries in `data/envelope/reserved/`. Reservations cover v2 spine articulation, actuated hands and facial actuators. The v1 lumbosacral actuators are designed, not reserved." Not applied: the node file is yours to edit.

## 10. ADR 0007 (item 10, after this memo)

Edited in the same commit, status `proposed`: D2's arm clause with the real results (rotation per segment, stretch 1.124 / 1.120 against a gate of 2 sigma / L, the hand's rotation without stretch, the elbow's bisector cut; the sculpt's arms 11% shorter than the sheet's, the forearm 8% shorter than ANSUR-scaled; the optional later re-sculpt of the arm-length sliders); D7 reworded as an observation with one hypothesis (the sculpt is lean against the BMI 24.7 reference), no re-sculpt, revisit with all segments (now in: the lumped region 1.103); D11 with the trunk x offset and the hip registration as open items; the Context gap and the Consequences updated.

## 11. My mistakes and defects

- The first arm build used each segment's perpendicular cut plane and failed gates 3b and 7 (finding 2); I diagnosed it by counting the overlap on the raster before changing anything, but the change is a method change made after a failing gate, which your rule 3 asks me to say.
- Ear vertices inflated the first upper arm (finding 3a); my hand-tip probe in memo 38 picked up non-hand vertices (the figure was discarded there and recomputed here: 182.9 mm).
- My first share table raised a KeyError ("feet": the closure calls them "foots"); fixed. My first `reserve` test margin was off by the 6 mm lattice (the test now says so).
- Shell heredocs dropped or mangled `\n` three times in `cli.py` and once for the arms report (caught by the first import each time); the files were then edited with the editor tool.
- The elbow minimum radius first came out as 12.8 mm on the cut face; I excluded 15 mm at the cut and say so (it is a search range, reported in each ledger header).
- Tests: the arm frame tests were written before the code; the bisector rule and the products were tested against the committed result after the build, not first (I tested the 3b/7 failure by running the gates).

## 12. Tests and files

STATE line above. Known failure: `test_gait_extract.py::test_the_tracked_envelope_is_what_the_tracked_extract_and_run_records_produce`. New: `tests/test_envelope_arms.py` (7), `test_envelope_arm_bodies.py`, `test_envelope_reserve.py` (7), `test_envelope_corridor.py` (6), `test_envelope_union_skin_warning.py` (2); changed: `test_envelope_trunk_bodies.py` (the closure has no remainder). New code: `tools/envelope/arms.py`, `arms_report.py`, `reserve.py`, `corridor.py`, `hipcheck.py`; changed: `anthro.py` (ARM_COLUMNS), `bodies.py` (the leaked-cell grid in the accounting), `bodies_report.py`, `field.py` (`full_ray`), `gates.py`, `occupancy.py`, `plots.py` (z_top), `cli.py` (`reserve`, `corridor`, `hip`; arms in `build`), `docs/envelope-component-contract.md`. New data: `upper_arm_R`, `forearm_R`, `hand_R` ledgers and silhouettes, `arm_bodies.json`, `reservations_result.json`, `corridor_result.json`, `hip_registration.json`, `reserved/`, `corridor/`, the six arm example files. `data/ansur2/ratios.json` regenerated (arm lengths added). `fy thread build` before the suite.

## Follow-ups

1. Joe: the five decisions above (module body and budget reading and orientation; the trunk's zero-pose offsets; the elbow and wrist anchors; the hip; ADR acceptance and the `done_when`).
2. The Stage 4 connector's format; `revision`, `sha256`, `parameter_snapshot` in the registry; the left side's CAD frames.
3. The optional arm-length re-sculpt (the sculpt's arms are 11% short): sliders, then the whole of this brief re-run.
4. A discrete-to-continuous hip sweep, a second sculpt, a structural check (ADR 0007 D11).
