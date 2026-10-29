STATE: base a02d3e1dbf26 | brief architecture sha256:e93e6b785bae, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests not run (--no-run; quick suite 900 passed, 4 skipped, pinned venv) | dirty yes (this memo, uncommitted when generated)

# Memo 50: the B arm nodes against T1 to T3, and the arm-length targets' blast radius (read-only)

Brief: `docs/briefs/architecture/volume-extractor-brief9.md` (sha256 5e075048104b, committed alone as b89b3a2). For rm.v1-arm-joint-anchors-decision (ADR 0042, not written). No recommendation on the arm gate.

## Decision summary

- **T1 trips: B is reopened.** Cross-check (b) at the elbow puts the midpoint of the mediolateral skin extremes at station -230 mm **5.27 mm** from the B elbow node, against 5 mm. It is marginal: over neighbouring stations (-220 to -240) and a mediolateral direction turned by up to ±5 degrees it ranges from 4.13 to 6.78 mm. Every other T1 number passes: elbow line gap 4.30 mm, wrist line gap 1.95 mm, wrist midpoint 2.33 mm.
- **T2 holds: the one-shot definition stands.** A second iteration on frames rebuilt through the B nodes moves the elbow 0.24 mm and the wrist 0.26 mm (limit 1 mm). Changing the fit trim from 40 mm to 30 or 50 mm moves B by at most 0.32 mm.
- **T3 fails: use the anterior-preserving twist.** Over the clean stations of the distal third of the forearm, the line through the mediolateral extremes spreads **9.8 degrees** (stations -175 to -215) and 10.2 degrees (-175 to -250), against 5 degrees. The shape-intrinsic version (largest Feret diameter) spreads 41 to 50 degrees. Caveat: dropping the single station at -175 mm gives 4.4 degrees on -180 to -215. Only the window that stops 40 mm short of the wrist is affected; the full window to -250 still fails.
- **Implied pronation offset:** -8.5 degrees (-6.7 to the wrist), in the supination sense. It is not reliable, because the spread exceeds the 5 degree limit.
- **The model has no pronation-supination joint.** At zero the hand appears to be in neutral forearm rotation (thumb forward, palm facing medially). That is inferred from the wrist hinge axis and the hand ellipsoid; no file documents it.
- **Re-sculpt: either target covers its shortfall alone, with more than 2x margin.**
  - Upper-arm target at full weight: +69.7 mm (+30.7%) on the current 227.0 mm node-to-node, against a 28.2 mm (12.4%) shortfall; weight 0.405 suffices.
  - Forearm target at full weight: +64.8 mm (+28.0%) on 231.7 mm, against 27.8 mm (12.0%); weight 0.428 suffices.
  - Volume change at full weight (both arms): +0.61 l and +0.29 l.
- **Blast radius:**
  - The forearm target moves nothing outside the forearm and hand.
  - The upper-arm target also moves the shoulder girdle (34 of 57 vertices, up to 18.7 mm) and 23 trunk vertices at the axilla and lateral chest wall (up to 14.3 mm, 47 to 58 mm below the SJC), on both sides.
- **Environment finding:** the repo `.venv` has drifted from `requirements.txt`. pytest, scipy and matplotlib are missing, and mujoco is 3.14.0 against the pinned 3.10.0. I did not touch it; every number here comes from a pinned venv built in my scratchpad from `requirements.txt`.
- **Decisions for you:** (1) T1 has tripped on a 0.27 mm excess; whether to reopen B is yours. The rule fired as written, and I have not re-argued it. (2) Which reading of "at the elbow station" in item 2(a) you meant (question 1). (3) Whether to repair `.venv`.
- **What would change the conclusions:** T1 passes if the mediolateral extremes are the largest Feret diameter (2.64 mm), or at station -225 (4.49 mm). T3 passes only on the trimmed window without station -175. T2 would need a different fit window or SJC to change; the margin is 0.74 mm.

## 0. Item 1 (script move): nothing to do

The two memo 43 diagnostics were moved to `analysis/` by `git mv` in a2aee99 (memo 44), and their paths were fixed there. `sim/scripts/` has neither file. No commit.

## 1. Method

- **Input.** An in-memory rebuild by `analysis/diag_elbow_anchor_build.py` (2 min 50 s, pickle in the scratchpad). It reproduces the committed stretches, 1.1244 and 1.1198 on both sides.
- **The diagnostic.** `analysis/diag_arm_anchors_b.py` (new, read-only, about 4 s) reuses memo 43's exact plane sections of the skin (no voxels, no cap) and builds every frame in memory. It writes one JSON, to the scratchpad, and nothing to `data/envelope`, the registration, `tools/` or `checks/`.
- **Stations** are segment-frame z in mm, stretched; section x and y are unstretched.
- **Loop selection.** At each station the loop is the one containing the previous centroid, else the nearest one with area above 300 mm². Loops within 80 mm with area above 20 mm² are counted, to detect the fingers splitting.
- **Current right-side nodes** (mesh frame, mm): SJC (15.6, -192.3, 1349.2), elbow (18.7, -347.6, 1183.7), wrist (177.0, -457.4, 1054.9).

**Tolerances and choices I made.** None was tuned toward a result; each was fixed before I read the T1 to T3 numbers.

| Choice | Value | Why |
|---|---|---|
| Fit window | -40 to -(L - 40) mm, step 5 mm | The brief's "as in memo 43 section 2". The step-5 grid from -40 ends at -215 for both segments (36 stations each). |
| Mediolateral direction | The anterior-preserving y: mesh +x projected onto the section plane, turned by +90 degrees | The anatomical ML. The largest Feret diameter is reported beside it. |
| Wrist station for 2(b) | -254.4 mm, 5 mm above the wrist plane | See 2(b). |
| Distal third (item 4) | From -175 mm, the first 5 mm station past 2/3 x 259.4 = 173.0 mm | The grid's first station inside the distal third. |
| Hand fit window | -10 to -55 mm | The fingers split at -65 mm, and the window stops 10 mm short of the split. |

## 2. B nodes and cross-checks (right side, current Ruler-chord frames)

| | Mesh frame, mm | Segment frame x, y at the joint station | Offset from the current node |
|---|---|---|---|
| B elbow (upper-arm centre line at -255.2) | (25.8, -326.3, 1163.8) | (6.96, 29.18) | 30.0 mm |
| B wrist (forearm centre line at -259.4) | (172.8, -449.3, 1043.0) | (-9.39, 11.68) | 15.0 mm |

How well each centre line fits:

| Fit | Residual rms, mm (x, y) | Residual max, mm (x, y) | Tilt against the node line | Quadratic coefficient, per mm |
|---|---|---|---|---|
| Upper arm | 0.48, 0.30 | 0.82, 0.57 | 4.27 deg | ≤ 1.7e-4 |
| Forearm | 0.38, 0.21 | 0.92, 0.43 | 3.44 deg | ≤ 1.4e-4 |

Both are straight lines. B elbow reproduces memo 43's centre-line point (7.0, 29.2).

### (a) Gaps between the extrapolated lines

| Joint | Measure | Gap | T1 (5 mm) |
|---|---|---|---|
| Elbow | The forearm's line where it crosses the upper arm's joint plane (B's own station) | **4.30 mm** | passes |
| Elbow | The forearm's line at its own elbow station (forearm z = 0) | 7.08 mm (4.64 along the upper-arm axis, 5.35 in-plane) | fails if this is the reading |
| Elbow | Closest approach of the two lines | 4.17 mm | n/a (no station) |
| Wrist | The hand's line at the wrist station (same plane: the hand takes the forearm's axis) | **1.95 mm** (linear fit) | passes |
| Wrist | The hand's line, quadratic fit | 2.79 mm | passes |
| Wrist | The measured hand section 5 mm distal | 3.29 mm | passes |

**The hand's sections do not fit a line cleanly.** On ten stations (-10 to -55) the residual rms is 0.46 and 0.79 mm and the maximum 1.17 mm. The centroid curves: its y step per 5 mm falls from 2.3 to 0.85 mm, the quadratic coefficient is -4.3e-3 per mm, which gives about 2 mm of sag over the window, and the tilt is 20.5 degrees. Beyond -60 mm the fingers split; at -110 mm the plane reaches the thigh. The linear wrist gap is therefore an estimate with roughly ±1.5 mm of model spread (1.95 linear, 2.79 quadratic, 3.29 measured).

### (b) Midpoint of the mediolateral skin extremes

| Joint, station | Section | ML breadth | Midpoint x, y | In-plane distance from the B node | From B's line at that station | T1 |
|---|---|---|---|---|---|---|
| Elbow, -230 (brief) | 3,782 mm², 1 loop | 66.9 mm | (11.11, 25.93) | **5.27 mm** | 5.03 mm | **fails, by 0.27 mm** |
| Elbow, Feret variant | | 77.6 mm | (9.13, 27.68) | 2.64 mm | 2.84 mm | passes |
| Wrist, -254.4 | 1,235 mm², 1 loop | 33.7 mm | (-10.03, 13.93) | **2.33 mm** | 2.12 mm | passes |
| Wrist, Feret variant | | 45.8 mm | (-7.97, 13.02) | 1.96 mm | 1.68 mm | passes |

The in-plane distance carries the midpoint parallel to the frame axis to the joint station. The 3D distances (23 mm at the elbow, 5 mm at the wrist) are dominated by the axial separation and are not the cross-check.

**Why -254.4 at the wrist.** The wrist has no cap: forearm and hand share one plane (the `arms.py` docstring), so every section proximal to that plane is the forearm's skin alone. The table from -219.4 to -254.4 is one loop throughout, with area falling smoothly from 1,476 to 1,235 mm² and ML breadth from 39.7 to 33.7 mm. -254.4 is the nearest station on the 5 mm grid strictly above the plane. Over that whole range the y-extremes distance is 1.96 to 4.57 mm, all under 5. The Feret distance is 1.96 to 5.45 mm; it exceeds 5 only at -219.4.

**Sensitivity of the elbow result**, distance from the B node, mm:

| Station | ML -5 deg | ML 0 | ML +5 deg |
|---|---|---|---|
| -220 | 4.59 | 5.00 | 5.00 |
| -225 | 4.82 | 4.49 | 4.82 |
| -230 | 5.27 | 5.27 | 4.58 |
| -235 | 5.98 | 5.98 | 4.33 |
| -240 | 6.78 | 6.78 | 4.13 |

The extremes jump between mesh vertices, so the result moves in steps. Distally it grows by about 0.75 mm per 5 mm; the cap starts below -240 (memo 43).

## 3. Second iteration (T2)

I rebuilt the frames on the B nodes (upper arm from the SJC to B elbow, forearm from B elbow to B wrist), refitted on the same station window, and extrapolated to the joint stations. The stretch was computed internally and is not reported.

| Node | Moves | T2 (1 mm) |
|---|---|---|
| Elbow | **0.24 mm** | holds |
| Wrist | **0.26 mm** | holds |

The refit residual rms is 0.50 and 0.22 mm (upper arm) and 0.35 and 0.20 mm (forearm).

## 4. Forearm roll (T3)

Frame rolls (memo 43): upper arm 0.32 degrees, forearm 16.55 degrees; the anterior-preserving x lies at +16.55 degrees in the current forearm frame. Line directions are in degrees from the frame's +x, modulo 180:

| Station | Through the ML extremes | Largest Feret |
|---|---|---|
| -175 | 106.1 | 53.8 |
| -180 | 96.3 | 46.6 |
| -185 | 96.3 | 47.0 |
| -190 | 96.2 | 47.2 |
| -195 | 96.3 | 47.3 |
| -200 | 96.4 | 30.3 |
| -205 | 96.5 | 12.5 |
| -210 | 98.0 | 13.0 |
| -215 | 100.6 | 13.5 |
| -220 | 103.4 | 3.7 |
| -225 | 97.2 | 4.1 |
| -230 | 98.9 | 4.5 |
| -235 | 100.3 | 4.6 |
| -240 | 102.9 | 4.7 |
| -245 | 105.6 | 4.8 |
| -250 | 106.4 | 5.1 |

| Window | ML extremes: spread, sd | Feret: spread, sd | T3 (5 deg) |
|---|---|---|---|
| -175 to -215 (centre-line window) | **9.8 deg**, 3.1 | 41.3 deg, 16.3 | fails |
| -175 to -250 (to the wrist) | **10.2 deg**, 3.7 | 50.1 deg, 19.3 | fails |
| -180 to -215 (not the rule; shown because it flips) | 4.4 deg | 41 deg | ML would pass |

The Feret direction is ill-conditioned: the section's breadth and depth are close, and the direction jumps by about 35 degrees between -195 and -205. That is the same failure memo 43 found with the shape-based anterior.

**(b) Implied x against the anterior-preserving x.** From the ML-extremes line, x lies at +8.1 degrees in the frame (centre-line window) or +9.9 degrees (to the wrist). That puts it -8.5 or -6.7 degrees from the anterior-preserving x.

- **Sign.** The angle is about the forearm frame's +z, which points proximally. For the right arm, a positive rotation carries anterior toward medial, and the radial (lateral) side toward anterior: pronation. A negative value is therefore supination. In words, the sculpt's forearm reads as about 7 to 8 degrees supinated relative to the mesh's anterior.
- **Not a measurement.** The spread fails T3, and the extremes are taken along the anterior-preserving y itself, which biases the line toward that axis. The Feret estimate (-72 to -85 degrees) is meaningless.

**(c) `sim/models/freyja_template.xml`.**

- The forearm body carries one joint, `elbow_right`, a hinge about (0, -1, 0); the hand carries `wrist_right`, a hinge about (1, 0, 0). The left side mirrors this, with the wrist about (-1, 0, 0). There is **no pronation-supination joint**; forearm rotation is fixed.
- What the zero means is not stated anywhere. I infer it from two features:
  - The hand ellipsoid is 0.04 m along x and 0.015 m along y (marked "design choice, no sheet source"), so the palm's broad dimension lies along the anterior axis and the palm faces ±y.
  - A positive rotation about +x carries the hanging right hand (-z) toward +y, which is medial, so wrist flexion moves the hand medially.

  Both fit the forearm held in **neutral rotation at zero (thumb forward, palm facing the thigh)**, not the anatomical position (palm forward, full supination).
- At zero, then, the model's forearm is about 90 degrees pronated from anatomical. The sculpt's x offset (item 4b) is small against that, if it is meaningful at all.

## 5. Re-sculpt blast radius (MakeHuman arm-length targets)

**Reachability.** The targets are not in the pinned manifest (`data/makehuman/mhm_sources.json`: 161 files, none for the arm) or the gitignored cache. I fetched the four files read-only from the manifest's pinned upstream commit into the scratchpad; the manifest and cache are unchanged. All are CC0.

| Target | sha256 (first 12) |
|---|---|
| measure-upperarm-length-incr | 274fef021ec8 |
| measure-upperarm-length-decr | abe56f2b05ed |
| measure-lowerarm-length-incr | 6a5c5d34fbc5 |
| measure-lowerarm-length-decr | 87287a154623 |

**How they were applied.**

- Each target was applied at full weight (slider ±1) on the v2 body as delta × 1. The v2 `.mhm` has neither slider set, and MakeHuman targets are linear in weight.
- Deltas on helper vertices (index ≥ 13,380) were ignored: 524 to 804 per target.
- Labels come from the current frames' planes. The arm label has only 227 forearm vertices per side; the hand has 1,606.
- The SJC is held fixed, since the trunk registration was not rerun. No vertex within 40 mm of it moves more than 0.14 mm under any target.

| Target, full weight | Moved > 0.1 mm (of label), max | Outside the arm | Volume, both arms | Upper-arm node-to-node | Forearm node-to-node |
|---|---|---|---|---|---|
| upper arm incr | upper_arm 197/198, forearm 227/227, hand 1606/1606 per side; max 69.7 mm (a translation below the elbow) | **girdle 34/57 per side, up to 18.7 mm; not_arm 23 vertices, up to 14.3 mm** | +0.612 l | **+69.69 mm, +30.7%** | 0 |
| upper arm decr | the same pattern, max 48.5 mm | girdle 33/57, 13.0 mm; not_arm 19, 9.9 mm | -0.426 l | -48.47 mm, -21.4% | 0 |
| forearm incr | forearm 178/227, hand 1606/1606; max 65.9 mm | none | +0.294 l | 0 | **+64.83 mm, +28.0%** |
| forearm decr | forearm 219/227, hand 1606/1606, upper_arm 4/198 (≤ 0.22 mm) | none | -0.209 l | 0 | -44.59 mm, -19.3% |

**Where the outside-arm vertices are.** The not_arm vertices sit at |y| 152 to 248 mm, z 1291 to 1302 mm, x -20 to 60 mm, against the SJC at |y| 192 and z 1349: the axilla and lateral chest wall, 47 to 58 mm below the SJC. The girdle vertices lie between z 1298 and 1358 mm. The targets are bilateral, so every count is per side and appears on both.

**Shortfall coverage.** Current lengths are upper arm 227.0 mm and forearm 231.7 mm, against the sheet's 255.2 and 259.4 mm.

| Segment | Shortfall | Full weight gives | Covers | Weight that closes it | Volume at that weight, both arms |
|---|---|---|---|---|---|
| Upper arm | 28.2 mm (12.4%) | +69.7 mm (+30.7%) | 2.47x | 0.405 | +0.25 l |
| Forearm | 27.8 mm (12.0%) | +64.8 mm (+28.0%) | 2.34x | 0.428 | +0.13 l |

The weight and volume are linear interpolations; MakeHuman sums targets linearly. The maximum lengthening available (weight 1) is the "full weight gives" column. Both cover the shortfall with margin. The upper-arm target is the one that reaches outside the arm.

## What would change each conclusion

- **T1 (tripped).**
  - It passes if the mediolateral extremes are defined by the largest Feret diameter (2.64 mm), if the station is -225 (4.49 mm), or if the ML direction turns by +5 degrees (4.58 mm).
  - It also trips on 2(a) if "at the elbow station" means the forearm's own station (7.08 mm).
  - A landmark-picked epicondyle pair would replace both cross-checks.
- **T2 (holds, margin 0.74 mm).** Only a change of the fit window or of the SJC; the trim moves B by 0.32 mm or less.
- **T3 (fails).** It passes only on the trimmed window without station -175 (4.4 degrees). Picked styloid landmarks would replace the skin construction altogether.
- **Item 5.** The SJC hold is good to 0.14 mm. A re-registered SJC under the upper-arm target, whose axilla vertices move up to 14 mm, could shift the upper-arm number by a few mm. That is not computed.

## My mistakes

- **Step 0 was not committed "before computing anything".** I wrote the brief file first. But `fy test --quick` failed under `.venv` (no pytest), and I built the pinned venv and ran the arm rebuild and the diagnostic before the commit. The brief text is unchanged (sha256 above), but the order was wrong.
- **My first diagnostic run crashed.** The loop count included sections of the torso and legs. I fixed it to count loops within 80 mm of the arm.
- **Item 4 first used a window ending at -219.** That conflicted with my own 2(b) argument that the wrist sections are clean to the plane. I now report both windows; both fail T3.
- **The brief's item 1 was already done.** I checked the history before acting, so nothing was moved twice.

## Questions for Joe

1. **Item 2(a), "at the elbow station":** did you mean the upper arm's joint plane, where B is defined (4.30 mm), or the forearm's own elbow station (7.08 mm)? T1 has tripped on 2(b) either way.
2. **"Mediolateral skin extremes":** is the anatomical ML (anterior-preserving y) the intended direction for 2(b) and item 4? The Feret alternative passes T1 at the elbow, but it is ill-conditioned for the roll.
3. **`.venv`:** reinstall from `requirements.txt`? It has pytest, scipy and matplotlib missing and mujoco 3.14.0 against 3.10.0, which matters for every sim result.
4. **Arm targets in the manifest:** if the re-sculpt route is taken, should the four arm targets be added to `mhm_sources.json` (`makehuman_fetch.py --pin`)?
5. **Model zero:** should the forearm's neutral-rotation zero (inferred in 4c) be written down where the CAD frame is defined (CONVENTIONS, CAD frame), given the ISB forearm frame assumes a different reference posture?
