STATE: base af763eecd33f | brief architecture sha256:bd2d997fe5e8, ariadne sha256:92fdab47007d | snapshot sha256:492fe816e6d8 | tests 2577/2580 | dirty no

# Memo 70: shoulder room, Group B close-out (Amendment 2)

## Decision summary

Three answers for adr-0025. All are basis (memo 66 basin 2) unless marked, with shell t = 5 mm, in the thorax model frame. N is the neutral bound, S the pose-proof bound.

1. **A serial roll actuator cannot ride on the axis-1 stage inside the skin.**
   - An AKH70-class actuator lying along axis 2 is 90 mm thick along u1 (its diameter) and reaches at least 81.5 mm from the axis (its length).
   - The room over a 90 mm window is a disc of radius 6.7 mm (N) or 6.3 mm (S). Over 60 mm it is 18.8 mm (N) or 11.0 mm (S).
   - Even the joint ball alone is only R_B = 29.33 mm.
   - The comparison basin is worse: 0 mm (N) and 4.0 mm (S) over 60 mm.
2. **A motor coaxial with axis 1 cannot sit in the chest or the back with a shaft to the joint, on either basin.**
   - Basis: a coaxial chest run exists from s = -154 to -202 mm, where r ≥ 25 mm. Its widest point is Ø56.3 mm at s = -190, which is in the right breast of this mesh. The run is the same with reservations on.
   - Basis shaft test: no 5 mm shaft reaches that run. The axis passes the axillary skin with r = 2.84 mm at s = -74. With reservations on, spine module m2 closes s = -100 to -124 (r = 0).
   - Comparison (basin 1): the lower end leaves the thorax skin at s = -67.8 mm through the posterior wall of the axilla, not the upper back. Thorax-alone r is at most 10.2 mm (Ø20.5) before that. r = 0 under every bound from s = -62. It finds no back room.
3. **The joint-local transmission envelope:**
   - R_20 = 27.4 mm and R_40 = 20.8 mm, under N and S alike, reservations on or off.
   - Comparison: R_20 = 27.8 (N) or 27.4 (S); R_40 = 25.4 (N) or 20.8 (S).
   - For scale, the AKH70 radius is 45 mm.
   - The pose-proof bound around the joint is the joint ball on both basins: S max 28.94 mm at s = -4, against R_B 29.33.

Against the references: the SJC is the envelope's, 37.78 mm ahead of the model's (memo 68). R_B is 29.33 mm by the oracle and 29.30 mm from the field. Memo 69's draft r_N max of 30.5 mm becomes 34.0 mm once the ball is credited.

All six gates pass. Nothing needs a ruling before adr-0025. One question (Q1, the breast volume) matters only if a chest motor is reconsidered.

**What would change these answers:**
- relabelling the arm and thorax regions in the hanging pose (N's peaks next to the unheld sheet);
- a thinner shell;
- moving the SJC in the R5 reconciliation, which moves every profile with it;
- ruling breast tissue out of the usable volume, which would remove the basis chest run.

## Findings

1. **Gates G-B1 to G-B6 pass on both axes** (table below). The draft's G-B4 failure is gone by construction under R6: 0 violations on either axis.
2. **The basis axis reaches room only past the axilla, and that room is in the breast.**
   - Thorax alone, r(s) runs: 18.8 mm at s = -50; down to 2.84 at s = -74 (axilla skin at (79.85, -159.55, -125.67) mm); back up to ≥ 25 over s ∈ [-154, -202].
   - Its widest point is Ø56.33 mm at s = -190, bound by thorax skin at (144.84, -107.33, -222.49). The axis point there is (134.8, -83.9, -209.5). That is 97 mm ahead of the mesh's thorax centre line, 84 mm right of the midline and 132 mm below the SJC: the right breast on this female mesh.
   - The axis leaves the skin at s = -295.15 mm, at (180.90, -23.84, -282.51).
   - With reservations on, m2 takes s = -100 to -124 to zero. The far run is the same either way.
3. **Basin 1's lower end goes into the axilla, not the back.**
   - The axis leaves the thorax skin at s = -67.78 mm, at (18.85, -159.58, -127.05). That is 19 mm behind the mesh centre line, 33 mm medial of the SJC and 50 mm below it: the posterior axillary wall.
   - Between s = -24 and -60, thorax-alone r is bound by the thorax's arm-trunk region cut, not skin. The largest diameter there is Ø20.5 at s = -54. That is a cut binding outside B, the stop-list kind.
   - It blocks nothing. N, which credits the arm's flesh there, still gives r = 0 from s = -62 outward, and the axis has left the skin by -67.8. Comparison only.
4. **The basis reservations-on run s ∈ [0, -98] also binds on that cut.** Its largest diameter is Ø37.6 at s = -50. The shaft verdict does not rest on it: it rests on skin at s = -74 (r = 2.84 mm).
5. **N exceeds S only where the arm region adds flesh beside the joint.**
   - Basis: s ∈ [-64, -24], peak 30.5 mm at -36 (thorax skin); s ∈ [-18, -12], peak 34.0 mm at -16 (upper_arm_R skin at (87.74, -201.24, -85.27)); and s ∈ [30, 36], where N is at most 2.1 mm.
   - Comparison: s ∈ [-60, -30] and [-26, -10], peak 33.2 mm at s = -14.
   - These peaks sit next to the unheld sheet and depend on the A-pose labels. That is why the answers above quote S beside N.
6. **The unheld sheet (R6):** 15.10 cm³ within 40 mm of the SJC, 2.30 cm³ within 20 mm, and 8.34 cm³ inside B (7.9 % of the ball's 105.73 cm³). The nearest unheld point is 4.47 mm from the SJC.
   - Memo 69 gave 15.47 and 8.59 cm³. Those used each body's own region; these use R3's union-grid region, as N does. The difference is that grid's trilinear region on the thorax lattice.
   - This is a region artefact. Relabelling in the hanging pose is a `tools/envelope` follow-up.
7. **`part.arm.upper_member` intrudes up to 1.14 mm into the discs.**
   - Basis: N at s ∈ [-46, 10], 1.14 mm; S at [-34, 10], 1.11 mm.
   - Comparison: N at [-42, 10] and S at [-28, 10], 1.08 mm each.
   - Reported, not subtracted.
8. **The free-sphere hint sits at its search limit.** It is radius 42.52 mm at (30.66, -52.33, -31.00), 149.02 mm from the SJC, against a 150 mm limit. Its position:
   - basis: s = -38.4 along u1, 144.0 mm off the axis;
   - comparison: s = -43.8, 142.5 mm off the axis.
   - It is the same with the arm in the union.
9. **The rim-first check is exact and halves the build.** A disc's two rim rings are checked before its interior, and any failure is a failure of the whole, so results are unchanged. One build of both axes takes about 225 s. The G-B5 test rebuilds once (230 s on one worker), and the full suite took 350 s on 12 workers.
10. **Hook warning (pre-existing):** `rm.v1-upper-arm-char-file` names `work.upper-arm-characterization`, which is not a work item.

## Gates

| Gate | Result | Numbers |
|---|---|---|
| G-B1 frames | pass | SJC (51.60, -192.33, -77.57) through the trunk map; dy -0.0011 and dz +0.0021 mm (tol 0.01) from `upper_arm_right`, dx 37.78. u1: as read, norm residual 7.7e-14; used, normalised, within 1e-12, on both axes. Lateral at station 40: 226.63 mm against memo 59's 226.63 (tol 2) |
| G-B2 synthetic | pass | 45 mm cylinder from `synthetic.frustum`, axes parallel and at 30°: within one voxel at s = -40 to 40 |
| G-B3 ball | pass | R_B 29.33 mm (oracle) against 29.30 mm (zero crossings of the arm field, in region), difference 0.04 (tol 2). Binds on lateral skin, arm frame (1.0, -29.8, 0.0); no slab overrun |
| G-B4 order | pass | Both axes: r_S ≤ r_N and r(on) ≤ r(off) at every s (0 violations), and thorax-alone on ≤ off over R9's range |
| G-B5 determinism | pass | Two consecutive builds byte-identical (sha256 cb275bc36dd9). The test's fresh build equals the committed file |
| G-B6 ball | pass | S max 28.94 mm at s = -4, bound by the ball, against the ball's disc there, sqrt(29.33² - 4.5²) = 28.99: residual 0.042 mm (tol 0.5), both axes. B ⊂ S at every s it reaches: worst shortfall 0.39 mm at s = -26 (within the bisection) |

## M1: r(s), mm (every 10 mm; full 2 mm profiles in `data/shoulder/room.json`)

| s | basis N off | N on | S off | S on | comparison N off = on | S off = on |
|---|---|---|---|---|---|---|
| -150 | 24.27 | 24.27 | 24.27 | 24.27 | 0 | 0 |
| -140 | 22.32 | 14.53 | 22.32 | 14.53 | 0 | 0 |
| -130 | 19.20 | 4.01 | 19.20 | 4.01 | 0 | 0 |
| -120 | 16.09 | 0 | 16.09 | 0 | 0 | 0 |
| -110 | 12.19 | 0 | 12.19 | 0 | 0 | 0 |
| -100 | 7.90 | 0 | 7.90 | 0 | 0 | 0 |
| -90 | 5.18 | 3.23 | 5.18 | 3.23 | 0 | 0 |
| -80 | 3.62 | 3.62 | 3.62 | 3.62 | 0 | 0 |
| -70 | 2.84 | 2.84 | 2.84 | 2.84 | 0 | 0 |
| -60 | 12.97 | 12.97 | 7.90 | 7.90 | 1.67 | 1.28 |
| -50 | 22.71 | 22.71 | 18.81 | 18.81 | 16.48 | 7.12 |
| -40 | 28.55 | 28.55 | 15.31 | 15.31 | 21.93 | 3.62 |
| -30 | 23.88 | 23.88 | 12.19 | 12.19 | 5.96 | 4.79 |
| -20 | 20.76 | 20.76 | 20.76 | 20.76 | 31.67 | 20.76 |
| -10 | 27.39 | 27.39 | 27.39 | 27.39 | 28.94 | 27.39 |
| 0 | 28.94 | 28.94 | 28.94 | 28.94 | 28.94 | 28.94 |
| 10 | 27.39 | 27.39 | 27.39 | 27.39 | 27.39 | 27.39 |
| 20 | 20.76 | 20.76 | 20.76 | 20.76 | 20.76 | 20.76 |
| 30 | 2.06 | 2.06 | 0 | 0 | 0 | 0 |
| 40 to 60 | 0 | 0 | 0 | 0 | 0 | 0 |

Summary:

- **Maxima:**
  - Basis: N 34.01 mm at s = -16 (upper_arm_R skin); S 28.94 mm at s = -4 (the ball).
  - Comparison: N 33.23 mm at s = -14 (upper_arm_R skin); S 28.94 mm at s = -4.
  - Reservations change no maximum.
- **r ≥ 20 mm:**
  - Basis N: [-150, -134], [-54, -24], [-20, 20]. Basis S: [-150, -134], [-20, 20]. With reservations on, the first run shrinks to [-150, -146].
  - Comparison N: [-42, -40], [-26, 20]. Comparison S: [-20, 20].
- **r ≥ 30 mm:** basis N at [-36, -32] and [-18, -14]; comparison N at [-24, -12]; S nowhere.
- **r ≥ 40 mm:** nowhere.

The plot is `data/shoulder/map/room_profiles.png` (gitignored). It has two panels, one per axis, with N and S, reservations off (solid) and on (dashed), and the AKH70 radius.

## M2: R_w, mm [window in s]

| w | basis N (off = on) | basis S (off = on) | comparison N | comparison S |
|---|---|---|---|---|
| 10 | 28.55 [-6, 4] | 28.55 [-6, 4] | 31.28 [-22, -12] | 28.55 [-6, 4] |
| 20 | 27.39 [-18, 2] | 27.39 [-10, 10] | 27.78 [-26, -6] | 27.39 [-10, 10] |
| 30 | 26.22 [-18, 12] | 23.88 [-16, 14] | 27.78 [-26, 4] | 23.88 [-16, 14] |
| 40 | 20.76 [-20, 20] | 20.76 [-20, 20] | 25.44 [-26, 14] | 20.76 [-20, 20] |
| 50 | 18.81 [-54, -4] | 12.19 [-26, 24] | 16.09 [-26, 24] | 12.19 [-26, 24] |
| 60 | 18.81 [-54, 6] | 11.02 [-56, 4] | 5.57 [-58, 2] | 4.01 [-34, 26] |

The window-90 figures in answer 1 are memo arithmetic: `window_budget` applied to the committed profiles at w = 90, not a gated output. They are 6.73 (N) and 6.34 (S) on basis, and 0 and 0 on comparison. At w = 82 they are 15.70 and 11.02 on basis.

Scale marks: AKH70 Ø90 × 81.5 mm (radius 45), from `data/envelope/reservations.yaml#/spine_v2/module` and the catalog drawing. The spec `.md` has no dimensions (memo 69 finding 7).

## R9: thorax alone, from the SJC to the axis's skin exit

| | basis off | basis on | comparison off = on |
|---|---|---|---|
| skin exit | s = -295.15 mm, thorax skin, (180.90, -23.84, -282.51) | same | s = -67.78 mm, thorax skin, (18.85, -159.58, -127.05) |
| runs of r > 0 (largest diameter at s; binds) | [0, -282]: Ø56.33 at -190 (thorax skin) | [0, -98]: Ø37.63 at -50 (region cut); [-126, -282]: Ø56.33 at -190 (thorax skin) | [0, -60]: Ø20.48 at -54 (region cut) |
| r ≥ 25 mm | s ∈ [-154, -202] | s ∈ [-154, -202] | none (r ≥ 20 nowhere) |
| 5 mm shaft from the ball to r ≥ 25 | **no**: first block at s = -64 (r 4.79, axilla skin); least r on the way 2.84 at -74 | **no**: least r 0 at -100 (m2) | **no**: first block at s = -30 (r 4.79, region cut); least r 0 at -62 |

Basis thorax-alone r(s), mm, every 10:

| s | 0 to -20 | -30 | -40 | -50 | -60 | -70 | -80 | -90 | -100 | -110 | -120 | -130 | -140 | -150 | -160 | -170 | -180 | -190 | -200 | -210 | -220 | -230 | -240 | -250 | -260 | -270 | -280 | -290 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| off | 0.9 to 7.5 | 12.2 | 15.3 | 18.8 | 7.9 | 2.8 | 3.6 | 5.2 | 7.9 | 12.2 | 16.1 | 19.2 | 22.3 | 24.3 | 26.6 | 27.8 | 27.8 | 28.2 | 25.8 | 22.3 | 18.4 | 15.3 | 13.8 | 12.6 | 9.9 | 6.3 | 2.1 | 0 |
| on | same | same | same | same | same | same | same | 3.2 | 0 | 0 | 0 | 4.0 | 14.5 | 24.3 | same | same | same | same | same | same | same | same | same | same | same | same | same | same |

The shaft rule:

- **Start:** the shaft walks from s = 0.
- **In the ball:** a grid point passes while the shaft's 5 mm disc fits in the joint ball, which is arm flesh at every pose.
- **Beyond it:** it passes when the thorax-alone r is at least 5.
- **Success:** it succeeds on reaching r ≥ 25 before any failure.
- **Robustness:** the least r on the way is recorded, so a verdict never rests on one block within the 0.5 mm bisection.

## Free-sphere hint (as written)

The largest free sphere has radius 42.52 mm (diameter 85.0) and centre (30.66, -52.33, -31.00) mm. The search used the free field, region rule, reservations on, with the centre within 150 mm of the SJC.

- **Distance:** 149.02 mm from the SJC, so it is limited by the search radius.
- **Basis axis:** s = -38.4 along u1, 144.0 mm off the axis.
- **Comparison axis:** s = -43.8, 142.5 mm off the axis.
- **The union:** the same with the arm in the union.

It is room for a belt or cable drive, off the axis, in the upper chest medial of the shoulder.

## M4: clavicle corridor (unchanged from memo 69; c rows sensitivity only)

The node:

- **Scale:** 1.0503 (sheet thorax length 328.76 mm over Dumas's 313).
- **SUP:** at model (89.25, 0, -36.90), through R1's chain from the mesh thorax centre line at the CJC.
- **Registration:** it uses SUP's height only (36.76 mm), so it places no SUP point.
- **Region:** the segment to the SJC never leaves the thorax region, so there is no switch to S.

| c | length | capsule r off (binds) | capsule r on (binds, mm from node) | node ball |
|---|---|---|---|---|
| 15 | 185.8 | 13.75 (thorax skin at the node) | 7.90 (m2, 130.6) | 13.75 |
| 25 | 176.3 | 13.36 (thorax skin at the node) | 8.68 (m2, 121.2) | 13.36 |
| 35 | 166.8 | 11.80 (thorax skin at the node) | 9.46 (m2, 111.8) | 11.80 |

The corridor is tight: a 24 to 28 mm bar over 170 to 190 mm with the spine reservation off, 16 to 19 mm with it on.

## Tolerances and choices

Every constant was set before the closing run, and none was moved after it.

- **From the brief:** step, bisection, disc thickness, t, gate tolerances, the W and c lists, the 150 mm sphere limit, the shaft's 5 and 25 mm.
- **AXIS_STEP_MM = 0.25:** the march to the skin exit uses `Section.ray`'s step.
- **EXIT_REACH_MM = 600:** no exit within it stops the build.
- **The exit point:** the first point past entry that is not both held and inside the skin. It is interpolated on sd when it is still held, which is a skin exit. The thorax region extends at most 4 mm past the skin (no region cell has sd < -4), so a skin exit is found before the region ends.
- **R9's grid:** stops at the last 2 mm point on the inside of the exit.
- **The unheld sheet:** measured on memo 69's lattice (±60 mm, 1 mm).
- **Rim-first check:** an exact reordering, not an approximation.

## My mistakes

1. The first closing build's R9 grid ran one step past the skin exit (-296 against -295.15). The output test I had written caught it before the commit.
2. The first closing build's shaft verdict rested on a block within the bisection tolerance (r 4.79 against 5 at s = -64). It was right, but not shown to be. I added the path's least r (2.84 mm at -74), tests first, and rebuilt.
3. The unheld-sheet numbers changed by 0.4 cm³ from memo 69 because the measure changed: each body's region there, the union grid here. I am naming the change rather than presenting either figure as the other.

## Open, not this session's work

- Memo 67 finding 4: `fy state` on a Current-brief line without backticks.
- Memo 66 finding 5: the serial-fallback warning.
- Memo 68 finding 3: memo 59's "mesh SJC x" rows. Due before adr-0025 sets the shoulder fall arc.
- R5: the model-versus-envelope SJC reconciliation. Due before the thorax is designed in CAD.
- R6: relabel the arm and thorax regions in the hanging pose (`tools/envelope`), which removes the unheld sheet.
- The draft branch `wip/shoulder-room-b-draft` is deleted (it was 41ce06c). Its content is on `main` in af763ee.

## Questions for Joe

1. **The breast volume.** The basis axis's only coaxial chest room (s = -154 to -202, Ø up to 56 mm) lies in the right breast of the female mesh. Is breast tissue usable volume for the robot's shell? It does not change answer 2: no shaft reaches that room.
2. **Basin choice inputs.** N gives basin 1 the wider joint-local window (R_40 25.4 against 20.8 mm). The pose-proof bound is the joint ball on both basins, so S is identical there. Is anything else wanted from this brief for adr-0025, or does Group B close here?
