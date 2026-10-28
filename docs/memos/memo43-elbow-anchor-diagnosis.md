STATE: base 1edb28aacf17 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests 2028/2032 | dirty no

# Memo 43: why the elbow node is 4.0 mm from the skin (diagnosis, read-only)

## Decision summary

- **The numbers support one explanation: the skin-vertex anchor.** The elbow node is the midpoint of two Ruler chord vertices that lie on the skin (0.0 mm from it, 43.5 mm apart). It sits 4.0 mm inside the lateral skin and **about 27 to 30 mm lateral of the section's centre line** (half the skin breadth there is about 33 mm). ADR 0007 D2 says the nodes are on or near the skin; this is what that costs at the elbow.
- **Roll does not explain it.** The upper-arm frame's +x is 0.32 degrees from the mesh's anterior (the forearm's is 16.5 degrees, a separate finding). A roll that size moves a 26 mm offset by 0.15 mm between labels.
- **The cap does not explain it.** The signed field is the distance to the whole-body skin, never to the bisector cut. The cut changes the sections only below station -240 mm (the last 15 mm).
- **A slender mesh does not explain it.** The skin's mediolateral breadth at the elbow is 66.8 to 68.3 mm. NHANES III women 20+ (Table 64, n = 8,443): elbow breadth 6.5 cm mean, 5.7 to 7.4 cm 5th to 95th (a bone caliper reading).
- **The centre line is tilted 4.3 degrees against the SJC-EJC line**: 4.0 degrees in y and 1.5 in x, over 36 stations with 0.3 to 0.5 mm rms residual. A linear drift along the whole length, not an end effect.
- **Counterfactual (not applied):** moving the node to the section centre line puts the new EJC 28.6 mm from the skin (14.8 mm with the cut centroid, 29.9 mm uncut); closure stays at +0.23 to +0.33% against 0.5%; the upper-arm stretch stays within its gate (1.115 to 1.116 against 1.1244 now). **The forearm stretch goes to 1.139 (centre line) and 1.160 (uncut), outside its 13.3% gate (1.133).** Only the cut-centroid variant passes (1.080), and that centroid is biased.
- **Decision for you:** approve the decision leaf drafted below (`rm.v1-arm-joint-anchors-decision`, blocking `rm.v1-upper-arm-characterized`). I recommend the centre-line anchor with the forearm gate decided inside the leaf, not here.
- **D11 needs amending:** it says the arm anchors "are no longer open". The elbow node is open. The wrist node sits on the skin as well (0.07 mm).
- **What would change the conclusion:** a different Ruler chord (the node is the mean of two chord ends), or a landmark-picked epicondyle midpoint that lands near the current node.

All computed from a fresh in-memory rebuild (`sim/scripts/diag_elbow_anchor_build.py`, 4 min) that reproduces the committed stretches (1.1244, 1.1198); nothing in the envelope, cache or registration was written. The analysis is `sim/scripts/diag_elbow_anchor.py` (45 s). Frame: the upper-arm segment frame, z down the axis from the SJC, stretched; y positive is **medial** (the nearest skin to the EJC is at y = -3.6 mm).

## 1. Rotation and roll

| | Upper arm | Forearm |
|---|---|---|
| Rotation | 43.174 deg about (0.9998, 0.0203, 0.0) mesh | 56.230 deg about (0.570, 0.822, 0.0) mesh |
| Axis horizontal; perpendicular to segment axis | exactly (0.0, 0.0) | exactly (0.0, 0.0) |
| Node line in the frame (proximal to distal), x and y | 1.6e-14 mm; z = -255.2347 (the sheet length) | 8.8e-15 mm; z = -259.4361 |
| Frame +x against the mesh's anterior (+x), projected onto the plane normal to the axis | **0.32 deg** | **16.5 deg** |

Convention: the shortest-arc (Rodrigues) rotation that turns the proximal-to-distal axis onto -z. Nothing else fixes the roll about the axis. The rotation is rigid, so the upper arm's 0.32 deg is the same at the SJC and the EJC. A shape-based anterior (the smallest caliper width of the section) is ill conditioned (caliper min over max 0.79 at the EJC, 0.81 to 0.82 at stations -190 to -230) and gives 10, 49 and 69 degrees at three stations; it is in the JSON and I do not use it.

Effect on labels: a roll of phi moves an offset d between the x and y labels by d sin(phi). Upper arm: 26.4 mm x sin 0.32 = 0.15 mm. Forearm: 28.6 mm x sin 16.5 = **8.1 mm** of the forearm's "y" offset is really anterior-posterior. The forearm's sections are labelled with a 16.5 degree error; this does not touch the 4.0 mm.

## 2. Centre line against the SJC-EJC line (exact skin sections, no voxel error, no cap)

Sections are cut from the mesh by planes normal to the axis. Centroids (x, y) in mm:

| Station | Centroid, uncut | Area mm2 | Note |
|---|---|---|---|
| 0 | not meaningful | 69,682 | the plane cuts the shoulder and torso; the field's section centroid is (-1.0, -13.5) |
| -50 | (2.2, 14.4) | 5,322 | |
| -100 | (2.5, 18.8) | 4,496 | |
| -150 | (3.9, 21.8) | 4,180 | |
| -200 | (6.0, 25.2) | 3,971 | |
| -230 | (7.3, 25.4) | 3,782 | cut = uncut |
| -255 | (12.5, 24.2) uncut; (-11.7, 25.8) cut | 4,047; 1,144 | the bisector cut leaves 28% of the section |

Fit over stations -40 to -215 (36 stations, step 5): slopes -0.026 (x) and -0.070 (y) per mm. **Tilt against the SJC-EJC line: 4.27 degrees; 1.49 in x and 4.00 in y.** Residual rms 0.48 mm (x), 0.30 mm (y); the last five residuals average 0.41 and -0.25 mm. The centre line passes (0.3, 11.3) mm from the SJC and (7.0, 29.2) mm from the axis at the EJC station: the node is 11 mm off the centre line at the SJC and about 30 mm off at the EJC. A linear drift over the whole length is a tilted line; nothing is confined to the last centimetres, so it is not a cap artefact. (A fit that includes station 0 gives 18.6 degrees; that is the shoulder's section, not the arm's.)

## 3. Caps

The field's `sd` is the distance to the whole-body skin: `signed_distance_grid` queries every skin triangle near the segment, and the bisector, the membership and the slab only set `region`, which masks cells for volumes and sections. A cap is not a boundary of `sd`. Check against a direct nearest-skin query (the skin sampled at 0.5 mm, error at most 0.25 mm):

| Station on the axis | 0 | -50 | -100 | -150 | -200 | -230 | -255 |
|---|---|---|---|---|---|---|---|
| Direct skin distance, mm | 34.39 | 26.10 | 18.25 | 11.95 | 6.59 | 5.45 | 4.04 |

The field gives 34.52 at the SJC and 4.03 at the EJC. The nearest skin to the EJC is at (-1.6, -3.6, -256.0) in the frame, on the upper-arm side of the bisector plane (0.06 mm from it): the lateral skin. The cut changes the sections from station -240 (AP extent 74.9 uncut, 63.9 cut) to the end (80.5 and 28.4 at -255.2); the field's mask perimeter at the EJC is 86.3 mm against 229.9 mm for the skin loop (uncut) and 146.6 mm (cut).

## 4. Symmetry and the forearm's proximal end

The left arm gives the same numbers: SD 4.03 mm at the EJC and 34.6 at the SJC, a direct distance of 4.00 mm, centroids identical with the sign of y reversed, stretches 1.1244 and 1.1198. **This cannot separate an anchor offset from a mesh asymmetry**: the mirror gap is 0.0 mm (the right nodes are the nearest vertices to the mirrored left ones, and the mesh is exactly symmetric). It shows only that the 4.0 mm is not an accident of the right-side extraction.

Forearm proximal end (the same node, so 4.03 mm): centroid (x, y) at stations 0, -15, -30, -50, -100 is (7.9, 28.6) uncut at the cut face, (2.1, 25.2), (-1.4, 23.4), (-3.0, 22.6), (-5.4, 20.4). The forearm's centre line is also 23 to 25 mm medial of its axis at the elbow. The wrist node is 0.07 mm from the skin; the hand's proximal node, -0.06 mm.

## 5. Widths against an independent measurement

| EJC station and just above | AP (x) | ML (y) | Perimeter |
|---|---|---|---|
| -255.2 (uncut; includes forearm overlap on the flexion side) | 80.5 mm | 68.3 mm | 229.9 mm |
| -230 (clean) | 73.7 mm | 66.8 mm | 221.8 mm |
| -255.2 cut by the bisector | 28.4 mm | 61.2 mm | 146.6 mm |

The ML breadth is 66.8 to 68.3 mm along the last 25 mm. Independent: CDC/NCHS, Vital and Health Statistics Series 11 No. 249 (NHANES III, 1988 to 1994), **Table 64**, females 20 years and older, n = 8,443: elbow breadth mean 6.5 cm (SE 0.01), percentiles 5th 5.7, 25th 6.1, 50th 6.4, 75th 6.8, 95th 7.4 cm; ages 20 to 29: mean 6.2, 5.6 to 7.1. The report defines it only as an "indicator of skeletal mass and frame size" measured "with a small sliding caliper"; the landmarks are in the NHANES III Anthropometry manual (its reference 3), which I did not retrieve. So it is a bone-side caliper breadth, and a skin breadth reads above it. The mesh's 6.7 to 6.8 cm is at about the 75th percentile if read as the same dimension and so is **not slender**; the half breadth is 33 to 34 mm, the node is 3.6 mm from the lateral skin and about 30 mm from the medial side. I could not source a landmark definition of this dimension from the repo or the report; I give none.

## 6. Counterfactual: the elbow node at the section centre (right side, in memory, nothing written)

| Variant | Moved | Stretch upper / forearm | Gate | From vertical, upper / forearm | Bend | Axis tilt | EJC to skin | Closure |
|---|---|---|---|---|---|---|---|---|
| Now | | 1.1244 / 1.1198 | 13.56% / 13.34% | 43.2 / 56.2 | 42.4 | | 4.0 mm | +0.333% |
| Centroid, cut by the bisector | 28.4 mm | 1.1157 / 1.0795 | passes both | 36.7 / 62.5 | 48.5 | 7.1 deg | 14.8 mm | +0.234% |
| Centroid, uncut | 27.3 mm | 1.1164 / **1.1597** | **forearm 16.0% > 13.34%** | 37.3 / 59.8 | 38.0 | 6.8 deg | 29.9 mm | +0.333% |
| Centre line extrapolated to the EJC station | 30.0 mm | 1.1147 / **1.1390** | **forearm 13.9% > 13.34%** | 35.9 / 61.4 | 41.1 | 7.5 deg | 28.6 mm | +0.311% |

The closure gate (0.5%) holds in all three. The cut centroid is biased (a 28% slice, outer side); the uncut one is biased by the forearm overlap on the flexion side; the centre line is the cap-free estimate and sits between them. The forearm gate fails because the sheet's forearm (259.4 mm) is already 12.0% longer than the mesh's node-to-node 231.7 mm; the centre-line node shortens the mesh's to 227.8 mm, 13.9%, past the 13.34% gate. That is a second finding and needs its own decision: the gate's sigma (17.3 mm, memo 38 decision 1), the sheet's forearm length, or the node.

**Decisions it would touch.** D2 (the registration: where the nodes are, the angles of the A-pose, the stretches and the gates it checks; the bisector cut moves with the node). D1 is untouched: the sheet still sets every length. D10 (the arms' stretch gate) is where the forearm fails. D11 is amended, below. The ISB joint centres (Wu 2005) put the elbow at the epicondyle midpoint; I did not check the repo's use of it beyond OVERVIEW.

## 7. Inspect bundle

`data/envelope/cache/inspect-elbow/` (gitignored cache, not committed): `original.obj`, `envelope_arms_t5.obj`, `elbow_markers.obj` (octahedra: `sjc`, `ejc`, `centroid_cut`, `centroid_uncut`, `centreline_extrapolated`), `elbow_sections.obj` (the skin loops at the EJC station, uncut and cut, as polylines) and `inspect.json` (`inspect-bundle/1`, MakeHuman axes, decimetres). I have not opened it in the landmark picker; the OBJ writer and axes are the existing bundle's.

## Verdict

Skin-vertex anchor. Not the cap (the field ignores it; sections differ only in the last 15 mm), not the roll (0.32 deg), not a slender mesh (6.7 to 6.8 cm against NHANES III's 6.4 median and 7.4 at the 95th). Compatible with ADR 0007 D2 as written, which is the problem: D2's "on or near the skin" puts the joint centre 4 mm under the lateral skin and about 30 mm lateral of where a joint centre sits. Consequences for Freyja: the available volume around the elbow joint that the oracle reports is one-sided (4 mm lateral, about 30 mm medial); any elbow housing placed on the model's joint axis has 4 mm on one side; and the upper-arm characterization (`rm.v1-upper-arm-characterized`) would carry that in its interfaces.

## Draft decision leaf (for you to approve; not created)

```yaml
---
schema: roadmap-node/2
id: rm.v1-arm-joint-anchors-decision
title: "Arm joint-centre anchors decided: where the elbow and wrist nodes sit in the section, with the forearm stretch gate settled"
short: Arm anchors
parent: rm.v1-volume-extracted
estimate_days: 1.0
tags: ["region:arm"]
done_when:
  type: decision
  record: decisions/0042-arm-joint-anchors.md
---
The elbow node is the midpoint of two skin vertices and sits 4.0 mm under the lateral skin and about 30 mm lateral of the section centre line (memo 43); the wrist node is on the skin (0.07 mm). Options for the record: (A) keep the skin nodes and carry an explicit lateral offset for the joint centre; (B) the section centre line (cap-free), which puts the forearm stretch at 1.139 against a 1.133 gate and so needs the gate or the sheet forearm length decided; (C) landmark-picked epicondyle and styloid midpoints. Recommended: B, deciding the forearm gate in the same record. The record also amends ADR 0007 D2 and D11.
```

and one line in `rm.v1-upper-arm-characterized`: `blocked_by: [rm.v1-elbow-load-basis, rm.v1-bridge-tooling, rm.v1-envelope-method, rm.v1-arm-joint-anchors-decision]`. The id is `rm.v1-arm-joint-anchors-decision` and the record number 0042 is the next free after 0041 in the roadmap's references.

**D11 amendment** (for you, in ADR 0007): replace "and the arm anchors on the skin (the elbow and wrist nodes). The arms are built and the reservations are reported (memo 39); they are no longer open." with the arms built and reported, **the elbow and wrist nodes still on the skin and open (memo 43)**.

## My own mistakes

- My first plane-section run included station 0, whose plane cuts the whole torso; its 18.6 degree full-length tilt was meaningless. I trimmed the fit to -40 to -215 and say so.
- I first took the shape-based anterior as a measurement; it is not (item 1).
- I killed my first build to add the trunk build to the pickle; four minutes lost.

## Questions for Joe

1. Approve the leaf and the blocking edge (I created neither), and the option (A, B or C)?
2. Does the forearm's length gap against the sheet (12.0% now, 13.9% with the centre-line node, gate 13.34%) go to the same leaf, or is it a separate question about the sheet's forearm length?
3. Should the diagnostic scripts stay in `sim/scripts/`?
