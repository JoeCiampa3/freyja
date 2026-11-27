STATE: base 9cfc2a65bd36 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:7734bf052e9a | snapshot sha256:492fe816e6d8 | tests 2553/2556 | dirty no

# Memo 69: shoulder room, Group B (Amendment 1), stopped at T3: G-B4 fails because the region rule loses flesh at the joint

## Decision summary

- **What it means for Freyja.** The room about axis 1 near the shoulder is about a 29 mm-radius disc (58 mm diameter) over roughly ±20 mm of s. Nowhere along u1 does it reach the 45 mm radius of an AKH70 (90 mm diameter). In the chest, coaxial with the axis's lower end, no motor of 50 mm diameter or more fits at t = 5 mm anywhere from the joint to s = -150 mm. These are **draft numbers**. A gate failed and nothing was committed to `main` but the worker cap.
- **Why I stopped.** G-B4 (r_S ≤ r_N at every s) fails at 25 s positions, from -22 to +20 mm. At s = 0, r_N is 7.9 mm and r_S 28.9 mm. Under Amendment 1 R3's region rule, a sheet of flesh around the SJC is held by neither body's region: 15.5 cm³ within 40 mm, including 8.6 cm³ (8.1 %) of the joint ball. Both fields agree it is deep flesh (sd about 27 to 29 mm). It is the shoulder-girdle zone the thorax gave to the arm in the A-pose, and the arm region, rotated 37° to hanging, no longer covers it.
- **Key numbers** (draft, reservations off unless stated):
  - SJC (envelope, R1): (51.60, -192.33, -77.57) mm. The model's is 37.78 mm behind, with y and z equal to 0.002 mm. G-B1 passes.
  - R_B: 29.33 mm (oracle), against 29.30 mm from the field's skin crossings. G-B3 passes.
  - r_N max 30.5 mm at s = -36, binding on thorax skin at the anterior axillary fold. r_S max 28.94 mm at s = -4: the ball.
  - Candidate N ∪ B: max 34.0 mm at s = -16. R_w = 27.4 mm for w = 20 and 20.8 mm for w = 40.
  - Thorax alone: r ≤ 24.3 mm over s ∈ [-150, -29]. At s = -70 the axis passes 7.8 mm from the axillary skin (r = 2.8 mm).
  - Clavicle capsule, SUP to SJC: radius 11.8 to 13.8 mm with reservations off, 7.9 to 9.5 mm on (spine module m2 binds).
- **Your decisions:**
  1. Repair N near the joint. Recommended: N := (thorax ∪ arm by region) ∪ B. B lies in the arm at every pose, so S ⊂ N holds by construction.
  2. Confirm S is the set thorax ∪ B. The brief's formula takes t off the ball twice: 18.42 against 28.94 mm.
  3. Restate M3. As written it answers 0 for every diameter, because its start disc crosses the thorax's arm-trunk cut. Recommended: report thorax-alone r(s) and the largest coaxial diameter, and extend M3's s range below -150 mm.
- **What would change the conclusion:** relabelling the arm and thorax regions in the hanging pose (a `tools/envelope` change) or a different t. The SJC placement (R5) moves every number with it.

## Findings

1. **G-B4 fails under the region rule (defect; stop).** r_S > r_N at s = -22 to -14 and -10 to +20 mm, in both reservation states: 50 pairs, the same 25 positions twice. The cause:
   - At s = 0, r = 12, the 22 failing samples lie 7.7 to 11 mm anterior of the SJC and 3.9 to 6.2 mm above it, just lateral of the shoulder plane. Neither region holds them. Thorax sd there is 26.7 to 29.6 mm and arm sd 28.4 to 31.1 mm.
   - Measured on a 1 mm lattice within 60 mm of the SJC: 606,709 mm³ is flesh both fields agree on (sd ≥ t in each), and 15,472 mm³ of it is held by no region. All of that lies within 40 mm. 8,593 mm³ lies within the ball (8.1 % of 105,731 mm³). The nearest unheld point is 4.5 mm from the SJC. The unheld set spans x -39 to +39, y -17 to +24 and z -30 to +39 mm relative to the SJC: a thin sheet.
   - Reading: the thorax region excludes the shoulder-girdle cells labelled to the arm in the A-pose (`trunk_bodies.json#/shoulder/shoulder_girdle_assigned_to_the_arm_side_l`, 0.27 l a side). The arm's region is those labels rotated 37° about the SJC onto the hanging axis, so part of the girdle wedge is uncovered.
   - Brief decision 2's premise, that B ⊂ upper_arm_R and so S ⊂ N, holds for the oracle's arm (sd and slab, no region). It does not hold for the region-held arm of R3.
2. **N binds on region cuts for s ∈ [-30, +30] mm (stop item).** Its binding sample lies beyond a region boundary there: the wedge, then the arm region's edge. N's maximum (30.5 mm at s = -36) binds on skin. The slab rule gives the same 30.5 mm there, so R3's diagnostic shows no difference at N's maximum. The rules part only in the wedge.
3. **M3 as written gives zero length for every diameter (stop item).** The cylinder starts at s0 = -R_B = -29.33 mm. At that s the thorax-alone disc radius is 11 mm, limited by the thorax's arm-trunk cut, so a 50 to 90 mm disc there crosses the cut. The question has a clear answer all the same: thorax alone, r(s) ≤ 24.3 mm over the whole range s ∈ [-150, -29], and its largest coaxial diameter is 48.5 mm at s = -150 (the range's edge, still rising). The axis passes 7.8 mm from skin at s = -70 (r = 2.8 mm, thorax skin at (82.8, -154.8, -128.2) mm, the axilla). So no 50 mm motor fits coaxially between the joint and s = -150.
4. **The brief's S formula counts t twice.** R_B is defined as already less t (G-B3). The margin "R_B - t - |p - SJC|", tested against t, then credits only |p - SJC| ≤ R_B - 2t. At S's maximum (s = -4) that gives 18.42 mm against 28.94 mm for the set thorax ∪ B. The draft uses the set and reports the literal value as a diagnostic.
5. **The reservations do not limit the room near the joint.** They reduce r_N only for s ∈ [-146, -88], where module m2 sits, and make it zero for s ∈ [-124, -100]. From s = -88 outward, on and off are equal. In M4 they do bind: m2 cuts the clavicle capsule from about 13 to about 8 mm, 112 to 131 mm along it from the node.
6. **`part.arm.upper_member` intrudes up to 1.11 mm** into the discs, for s ∈ [-46, -4] under N and [-34, +10] under S. Reported, not subtracted (decision 4).
7. **The AKH70's diameter and length are not in `catalog/actuators/akh70-48-specs.md`,** which the brief names. They are in the drawing beside it, `akh70-48-tech-drawing.png` (Ø90, 81.5), and in `data/envelope/reservations.yaml#/spine_v2/module`. The draft reads that address.
8. **Memo 68 overstated region coverage.** It said a region-based union "covers [the arm region's holes] with the thorax". I had checked one height, 4 mm below the SJC. Above the SJC the holes lie lateral of the thorax's cut and nothing covers them (finding 1). Mine; listed under mistakes too.
9. **Hook warning (pre-existing):** `rm.v1-upper-arm-char-file` names `work.upper-arm-characterization`, which is not a work item. It belongs to the paused characterization brief. Nothing here caused it.

## Gates

| Gate | Result | Numbers |
|---|---|---|
| G-B1 frames (Amendment 1, R2) | pass (draft) | SJC (51.60, -192.33, -77.57) computed through the trunk map. Against `upper_arm_right` (13.81, -192.33, -77.57): dy -0.0011, dz +0.0021 mm (tol 0.01); dx 37.78 mm. u1 as read has norm residual 7.7e-14; used, normalised, 0.0 (tol 1e-12), at 0.0° from the address. Lateral at station 40 (arm-frame z -4): ray 34.30 mm, skin 226.63 mm from the midline against memo 59's 226.63 (tol 2 mm) |
| G-B2 synthetic | written, not run | `tests/test_shoulder_room.py` on the draft branch: a 45 mm cylinder from `synthetic.frustum`, axes parallel and at 30° |
| G-B3 ball | pass (draft) | 29.33 mm by the oracle (capsule of zero length, bisection to 0.5 mm) against 29.30 mm from the zero crossings of sd between in-region cells; difference 0.04 (tol 2). Field sd at the SJC less t: 29.42. Just above R_B the ball binds on skin at arm frame (1.0, -29.8, 0.0), lateral; no slab overrun |
| G-B4 bound order | **fail** | 25 s positions, -22 to +20 mm, r_S > r_N in both reservation states (finding 1). r(on) ≤ r(off) holds everywhere |
| G-B5 determinism | not run | |

## T0 and T0a

- **T0.**
  - Brief sha256 7734bf052e9a, the prompt's prefix. C: had 170 GB free.
  - Thread build clean: 70 files, 0 changed.
  - Cache current: thorax 01a6e055b4a5 and upper_arm_R 770c1272e683 equal their ledgers.
  - `fy test --quick`: 1129 passed in 83.45 s, under the T0a cap.
- **T0a (9cfc2a6).**
  - `testkit.parallel_args()` = ("-n", min(os.cpu_count(), 12), "--dist", "loadfile"); `os.cpu_count()` None counts as one. It replaces `PARALLEL = ("-n", "auto", ...)` in `fy test` and `fy state`.
  - Tests first: mocked CPU counts 32 → 12, 4 → 4, 12, 1 and None → 1, plus the argv tests of `fy` and `state`. 7 failed before, 101 passed after.
  - Full suite: 12 of 12 workers; 2553 passed, 3 skipped in 683 s. It took longer than 205 s because `tools/testkit` is in every `inputs` key, so every cached test reran.
  - `fy state` reused that run (tree key ae9e375fed3f). It is a full run on this exact tree with nothing skipped for unchanged inputs.

## Draft measures (not gated; branch `wip/shoulder-room-b-draft`, 41ce06c)

These come from the draft script, which writes no `data/shoulder/room.json` on `main`. The method:

- **Frame and centre:** the thorax model frame; the envelope SJC (R1).
- **u1:** `axis_search.json#/basins/1/u1`, normalised.
- **t:** 5 mm from `data/characterization/inputs/upper_arm.yaml#/shell/value` (adr-0007 D4).
- **Bisection:** to 0.5 mm, on `oracle.sample_shape` discs 1 mm thick at 1 mm sampling.
- **N:** `occupancy.skin_field` of thorax and upper_arm_R, the arm at the SJC unrotated, queried by region.
- **S:** thorax by region ∪ B.
- **Reservations on:** `reserved/thorax.yaml` m1 to m3, minus their 5 mm clearance, by `occupancy.Body`.
- **Build time:** 229 s.

### M1: r(s), mm (every 10 mm; N ∪ B is the candidate of decision 1, not ruled)

| s | N off | N on | S off | S on | N ∪ B off | N ∪ B on | thorax alone |
|---|---|---|---|---|---|---|---|
| -150 | 24.27 | 24.27 | 24.27 | 24.27 | 24.3 | 24.3 | 24.3 |
| -140 | 22.32 | 14.53 | 22.32 | 14.53 | 22.3 | 14.5 | 22.3 |
| -130 | 19.20 | 4.01 | 19.20 | 4.01 | 19.2 | 4.0 | 19.2 |
| -120 | 16.09 | 0 | 16.09 | 0 | 16.1 | 0 | 16.1 |
| -110 | 12.19 | 0 | 12.19 | 0 | 12.2 | 0 | 12.2 |
| -100 | 7.90 | 0 | 7.90 | 0 | 7.9 | 0 | 7.9 |
| -90 | 5.18 | 3.23 | 5.18 | 3.23 | 5.2 | 3.2 | 5.2 |
| -80 | 3.62 | 3.62 | 3.62 | 3.62 | 3.6 | 3.6 | 3.6 |
| -70 | 2.84 | 2.84 | 2.84 | 2.84 | 2.8 | 2.8 | 2.8 |
| -60 | 12.97 | 12.97 | 7.90 | 7.90 | 13.0 | 13.0 | 7.9 |
| -50 | 22.71 | 22.71 | 18.81 | 18.81 | 22.7 | 22.7 | 18.8 |
| -40 | 28.55 | 28.55 | 15.31 | 15.31 | 28.6 | 28.6 | 15.3 |
| -30 | 23.88 | 23.88 | 12.19 | 12.19 | 23.9 | 23.9 | 12.2 |
| -20 | 11.41 | 11.41 | 20.76 | 20.76 | 20.8 | 20.8 | 7.1 |
| -10 | 25.05 | 25.05 | 27.39 | 27.39 | 27.4 | 27.4 | 7.5 |
| 0 | 7.90 | 7.90 | 28.94 | 28.94 | 28.9 | 28.9 | 0.9 |
| 10 | 0.5 | 0.5 | 27.39 | 27.39 | 27.4 | 27.4 | 0 |
| 20 | 0.5 | 0.5 | 20.76 | 20.76 | 20.8 | 20.8 | 0 |
| 30 | 2.06 | 2.06 | 0 | 0 | 2.1 | 2.1 | 0 |
| 40 to 60 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Summary:

- **Maxima:** N 30.5 mm at s = -36 (thorax skin at (94.95, -184.37, -96.23)); S 28.94 mm at s = -4 (the ball); N ∪ B 34.0 mm at s = -16.
- **r ≥ 20 mm:** N at s ∈ [-150, -134], [-54, -24] and [-12, -6]; S at [-150, -134] and [-20, 20]; N ∪ B at [-150, -134], [-54, -24] and [-20, 20].
- **r ≥ 30 mm:** N at [-36, -32]; S nowhere; N ∪ B at [-36, -32] and [-18, -14].
- **r ≥ 40 mm:** none, in any combination.
- **Reservations on:** the lower-end run [-150, -134] shrinks to [-150, -146].
- **The upper end:** r is 0 from s = +30 (S) or +38 (N) outward. The axis leaves the body about 30 to 40 mm above and behind the joint.

### M2: R_w, mm (window in s)

| w | N off | N on | S off = S on | N ∪ B |
|---|---|---|---|---|
| 10 | 27.78 [-42, -32] | 27.78 | 28.55 [-6, 4] | 28.55 [-6, 4] |
| 20 | 22.71 [-50, -30] | 22.71 | 27.39 [-10, 10] | 27.39 [-18, 2] |
| 30 | 20.37 [-54, -24] | 20.37 | 23.88 [-16, 14] | 26.22 [-18, 12] |
| 40 | 12.19 [-150, -110] | 11.41 [-60, -20] | 20.76 [-20, 20] | 20.76 [-20, 20] |
| 50 | 7.90 [-150, -100] | 4.79 [-64, -14] | 12.19 [-26, 24] | 18.81 [-54, -4] |
| 60 | 5.18 [-150, -90] | 4.79 [-64, -4] | 11.02 [-56, 4] | 18.81 [-54, 6] |

Scale marks, printed and not compared: the AKH70 is Ø90 × 81.5 mm (radius 45), from `reservations.yaml#/spine_v2/module` and the catalog drawing.

### M3

- **Coaxial cylinders, s0 = -29.33 mm:** length 0 for D = 50, 60, 70, 80 and 90, reservations off and on. All bind on the thorax region cut; from 70 mm, thorax skin too; at 90 mm with reservations on, m2 as well (finding 3).
- **Thorax-alone diagnostic:** the largest coaxial diameter in the range is 48.5 mm, at s = -150.
- **Free sphere (free field, region rule, reservations on, centre within 150 mm of the SJC):** radius 42.5 mm (diameter 85) at (30.66, -52.33, -31.00) mm. That is 149.0 mm from the SJC, at the search limit, and 144.0 mm off the axis.
- **The union:** the sphere is the same with the arm in the union.
- **What it is:** a hint at room for a belt or cable drive, not a fit. It sits in the upper chest, medial of the right shoulder, and is limited by the search radius.

### M4: clavicle corridor (c rows sensitivity only; none is basis)

The node and its scaling:

- **Scale:** the sheet thorax length is 328.76 mm (`snapshot#/thorax_length`), so the scale is 1.0503.
- **Dumas SUP:** (49, -35, 0). From the mesh thorax centre line at the CJC (x 1.70, z 1426.51, `trunk_bodies.json`) it lands at mesh (53.16, 0, 1389.75). Through R1's chain that is model (89.25, 0.00, -36.90).
- **Registration:** it does not place SUP. It uses SUP's height only, as a CJC cross-check (`trunk_registration.json#/mesh/sup_below_cjc_mm`, 36.76; the chain here gives 36.90 below the model CJC).
- **The node is inside:** it lies 17 to 19 mm inside the thorax skin.
- **No switch to S:** the segment from the node to the SJC never leaves the thorax region, so there is no switch point. S matters only through the ball at the SJC end.

| c | length | capsule r off (binds) | capsule r on (binds) | node ball off = on |
|---|---|---|---|---|
| 15 | 185.8 | 13.75 (thorax skin at the node) | 7.90 (m2, 130.6 mm from the node) | 13.75 |
| 25 | 176.3 | 13.36 (thorax skin at the node) | 8.68 (m2, 121.2) | 13.36 |
| 35 | 166.8 | 11.80 (thorax skin at the node) | 9.46 (m2, 111.8) | 11.80 |

## R5: the 37.78 mm SJC disagreement, logged, not fixed

The model's SJC x is `snapshot#/upper_arm_right_pos_x` = 0.0138137 m. Its sheet source is `'MuJoCo Positions '!B9`, the sheet's scaled Dumas 2007 torso value. Dumas 2015 gives none (`dumas2015_table1_female.json`, `SJC_note`: "the X coordinate was not supplied"). The envelope's SJC is 37.78 mm ahead of it, because the model's trunk stack stands 50.3 mm behind the mesh's centroid at that height (`trunk_offsets.json`). The offset touches three things downstream:

1. **The sim:** the upper arm and everything below it hang 37.8 mm behind where the body's shoulder is. The arm's CoM, inertia and the gravity moment it puts on the trunk are placed accordingly.
2. **CAD:** the upper arm's CAD frame origin is the sheet's SJC. So the thorax-to-shoulder interface, once drawn, would sit 37.8 mm behind the envelope's joint, 8.5 mm from the back skin (memo 68).
3. **Memo 59's shoulder fall rows:**
   - The lateral row (226.63 mm) is unaffected: G-B1 reproduces it.
   - The inboard "model SJC x" row (144.14 mm to m1) is taken at the model's x.
   - The "mesh SJC x" rows are also off by the shear (memo 68 finding 3).
   - No cap rests on them.

I edited none of the model, the sheet, `analysis/fall_room.py` or `data/falls/room.json`.

## Tolerances and choices

None tuned. Each was set before any number was seen.

- **From the brief:** step 2 mm, bisection 0.5 mm, disc 1 mm, t 5 mm, the 0.01 mm, 1e-12 and 2 mm gate tolerances, the W, D and c lists, the 150 mm sphere limit.
- **Brackets:** 200 mm for radii, 400 mm for M3's length. A feasible bracket stops instead of reporting the bracket; none did.
- **Disc roll:** the roll about u1 is fixed by a cross product with the world axis least aligned with u1, so it is deterministic.
- **N's region:** `Segment.in_region`'s 0.49 threshold, the library's own.
- **G-B3's independent figure:** linear zero crossings along each grid axis between cells both in the arm's region.

## My mistakes

1. Memo 68 said the region union covers the arm region's holes with the thorax, from one scan 4 mm below the SJC. It does not cover them above the SJC (finding 8). Had I scanned three heights then, Amendment 1's R3 could have been written with this in view.
2. I began the full suite for T0a expecting about 205 s. Changing `tools/testkit` invalidates every `inputs` key, so it took 683 s. That was foreseeable from the testkit docstring (ALWAYS); no harm beyond the time.

## Open, not this session's work

- Memo 67 finding 4: `fy state` should error on a Current-brief line without a backticked path.
- Memo 66 finding 5: `fy test`'s serial-fallback warning.
- Memo 68 finding 3: memo 59's two "mesh SJC x" rows. Due before adr-0025 sets the shoulder fall arc.
- R5: the model-versus-envelope SJC reconciliation. Due before the thorax is designed in CAD.
- The branch `wip/shoulder-room-b-draft` holds the draft script and tests. Delete it, or say to build on it.

## Questions for Joe

1. **N near the joint (finding 1).**
   - (a) Recommended: N := (thorax ∪ arm, by region) ∪ B. S ⊂ N then holds by construction, and B is arm flesh at every pose. The draft table above shows it.
   - (b) Hold the arm by its slab only. This credits the rotated extended solid, the same objection R3 made for the thorax.
   - (c) Relabel the regions in the hanging pose. That is a `tools/envelope` change and outside this brief.
2. **S (finding 4):** confirm S is the set thorax ∪ B, and the literal formula is not used.
3. **N's cut bindings (finding 2):** under (1a), do N's region-cut bindings inside the ball count as the ball, as S's do? They do in the candidate's table.
4. **M3 (finding 3):**
   - Recommended: replace the s0 = -R_B cylinders by thorax-alone r(s), giving the largest coaxial diameter and where.
   - Extend M3's s range below -150 mm, where r is still rising (24.3 mm at the edge).
   - Or keep M3 as written and accept "0 for every diameter, the cut binds".
5. **Draft branch:** build on `wip/shoulder-room-b-draft` next session, or start clean?
