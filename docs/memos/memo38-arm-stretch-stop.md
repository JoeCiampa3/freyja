STATE: base 651bda1d96b2 | brief architecture sha256:e93e6b785bae, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1742/1746 | dirty yes

# Memo 38: brief 8 stopped at Phase A item 1, arm stretch over 8%

Brief: `docs/briefs/architecture/volume-extractor-brief8.md`. Step 0 done (brief saved verbatim, CLAUDE.md repointed). Item 1's stop rule fired: **the upper arm and the forearm each need about 12% axial stretch.** Nothing else was built. No code, data or generated file changed.

## Decision summary

- **What it means for Freyja.** With the brief's anchors, the mesh arm is about 12% shorter than the sheet's arm, so a rigid rotation plus axial stretch would exceed the 8% gate on two of three segments. Reading the brief literally, I stop here.

| Segment | Mesh node-to-node (mm) | Sheet (mm) | Stretch | Angle from vertical (zero-pose axis is straight down) | Reference |
|---|---|---|---|---|---|
| Upper arm, SJC to elbow | 227.0 | 255.23 | **1.124** | 43.2 deg | gate 1.08 |
| Forearm, elbow to wrist | 231.7 | 259.44 | **1.120** | 56.2 deg | gate 1.08 |
| Hand, wrist to fingertip | not computed (my fingertip selection was unreliable, see mistakes) | 74.57 (SCS length only) | | | |

- Mesh nodes (right arm; the Ruler chords belong to the left arm, y mirrored): SJC (x 15.57, y -192.33, z 1349.24) from the trunk registration (brief 5 patch: sphere centre x, sheet lateral, `tm.inverse` of the sheet height). Elbow = mean of the upper-arm chord end (vertex 10037) and the forearm chord start (10040) = (18.73, 347.62, 1183.69) left. Wrist = chord end 10548 = (176.96, 457.39, 1054.91) left.
- ANSUR II female ratios times the mesh stature 1698.95 mm (surface landmarks, not joint centres, so context only): shoulder-elbow 348.8, radiale-stylion 251.8, forearm-hand 458.9, hand length 188.9 mm. The Ruler forearm chord is 223.5 mm against the ANSUR 251.8 (radiale-stylion): the mesh forearm is short on that measure too (-11%). The mesh upper-arm chord (shoulder landmark to elbow) is 267.6 mm. `data/ansur2/ratios.json` has no arm columns yet; the cross-check needs `anthro.py` extended (columns `shoulderelbowlength`, `radialestylionlength`, `forearmhandlength`, all in the raw CSV).
- **Decisions for you.**
  1. Which way to resolve it. (a) Accept an arm stretch gate above 8% for the arms, say 13%, stated as a finding: the sheet's arm (Dumas scaled, 255/259 mm) is longer than the sculpt's. (b) Re-anchor: the wrist at the Ruler chord end may sit short of the joint; a picked radial-styloid vertex and an olecranon/humeral-epicondyle pick via the landmark picker would move the nodes, and I can report what they give. (c) Re-sculpt the arms longer (your call; ADR 0007 D7 says no re-sculpt, but that is about the trunk). **Recommended: (b) first, then (a) if the picked nodes still give over 8%.** I did not change any tolerance.
  2. If (a): the stretch inflates nothing in cross-section (axial only), but arm volume grows about 12% against the mesh, and closure uses that conformed volume; expect the closure to move by about +0.3% of the mesh volume (arms are about 3.1 l of 52.3 l, 12% of that is 0.37 l, 0.7%), which alone can break the 0.5% gate. Please say if closure should then be quoted against the conformed total.
- **What would change the conclusion.** A different SJC (the sheet's SJC is 192.33 mm lateral and 77.57 mm below the CJC; the mesh acromion is at y 185.8, z 1388.7, so the mesh SJC is 39 mm below it); a different elbow or wrist vertex; a rotation axis other than the node-to-node line.

## Mistakes and caveats

- The fingertip selection in my probe took the farthest arm-labelled vertex, which picked up non-hand vertices (a head vertex at z 1589 first, then forearm vertices); the hand figure is discarded. The two arm numbers above do not use it.
- The probe is a scratch script, not committed. The SJC x/z uses the build's sphere centre (x 15.567) and `tm.inverse(1347.035)` = 1349.238; the left side is the mirror.
- `fy state` and a trunk build ran in parallel on the machine; the build took 243 s.

## Follow-ups

1. Joe: choose (a), (b) or (c) above. On (b), picks via `tools/landmark-picker` (radial styloid, olecranon or humeral epicondyle points, optionally acromion), or tell me the vertex ids.
2. After that I resume at item 1 with the report of stretches and angles for all three segments, then items 2 to 5 of Phase A.
