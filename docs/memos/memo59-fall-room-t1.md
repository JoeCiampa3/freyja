STATE: base b580610f4877 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:fa15c37d9eb1 | snapshot sha256:492fe816e6d8 | tests not run | dirty yes (tests not run: full suite skipped on Joe's instruction; quick 1080 passed, fall room 16 passed)

# Memo 59: fall inputs T1, room at the zone contacts and first caps

Brief: `docs/briefs/ariadne/fall-inputs-brief.md`. Script `analysis/fall_room.py`, output `data/falls/room.json`. T2 not started; it waits for Joe.

## Decision summary

- **What this means for Freyja:** the envelope can now answer five of six zones, but the honest answer for most of them is "it depends on hardware nothing has placed yet". Only the knee gives a cap that survives every variation tried. The arm cannot be answered from the repo at all.
- **Knee: 20 kN.** 28 mm stroke against 51.1 mm along the normal and 41.55 mm inscribed. 10 kN misses by 3.9 mm (55 mm against 51.1).
- **Hip: 40 kN under reading (a), and not robustly.** 35.1 mm of room on the ledger ray against the 29 mm stroke, but 26.4 mm, none fits, at the contact vertex's x, 16 mm forward. Reading (b) says 10 kN, but that 113 mm stroke runs past the hip joint centre, which is 71 to 88 mm from the skin.
- **Buttock and back: 20 kN off the midline, none fits on it, if the modules are in that body.** On the midline, 14.8 mm and 10.2 mm of room against 29 mm. Off it, 97.6 mm and 66.8 mm, but the stroke column has only 4.3 mm and 8.8 mm beside it before module m1.
- **Shoulder: none fits at the skin under (a)**, 14.3 mm against 29 mm, because `part.arm.upper_member` sits 19.3 mm in. (b) gives 10 kN, through the arm and the shoulder joint.
- **Hand and arm: cannot be answered.** No file holds the sternal pivot and no tool sweeps that arc.
- **Mass released if the reading (a) rows were all taken:** 0.60 kg of the 3.10 kg claim; (b): 1.30 kg.
- **Decisions for Joe:**
  1. Confirm the five stations (table below). Recommended: accept.
  2. Pick the meaning of spare. Recommended: (a), with the HJC node also counted as a limit at the hip.
  3. Apply caps now or wait. Recommended: apply the knee, and hold hip, shoulder, buttock and back until rm.v1-spine-reservation-decided and rm.v1-hip-architecture-adr, because a set cap is frozen.
  4. Release T2 or not. Recommended: not yet. Its pose families hang on decision 1, and lower energy helps only once the room above is settled.
- **What would change this:** placing the spine modules outside a body flips that body's rows: hip to 10 kN, or 20 kN with the HJC limit, and back on the midline to 40 kN. A registered hip mechanism can only lower the hip and buttock rows. A flexed-knee contact normal would replace the knee row.

## Gate table

| Gate | Result | Numbers |
|---|---|---|
| G1 provenance | Pass, with one limit | All 10 ledgers carry `freyja-body-v3.obj`. Used: pelvis and thorax `01a6e055b4a5`, thigh_R and shank_R `00fcb645ad2c`, upper_arm_R `770c1272e683`. Limit: `reserved/*.yaml` and `corridor/*.yaml` carry no `mesh_file` or hash. The reserved result's inner volumes equal the ledgers' to 4 decimals (5.0957 and 14.3776 l), so they belong to the current bodies; the corridor's inner volumes also read 14.3776 l for the thorax |
| G2 nothing decided | Pass in substance, not to the letter | No decision, record, node, `CLAUDE.md` or `OVERVIEW.md` changed. The diff holds the script, output and memo, plus two things the gate does not list: `tests/test_fall_room.py` (rule 1) and generated `docs/STATE.md` (rule on `fy state`) |
| G3 reproducible | Pass | No arguments; refuses any (exit 2). Two builds byte-identical, and the committed file equals a fresh build (tests) |
| G4 every zone has an outcome | Pass | Hip, shoulder, buttock, back, knee answered; hand and arm "cannot be answered" |

## Findings

1. **Reading (b) is not a usable meaning of spare at the hip or shoulder.** It reaches the midline, so the "10 kN" rows put the stroke through a joint centre. The hip's limit is the HJC at 71.2 mm from the skin in the pelvis frame, 87.75 mm in the thigh frame: 20 kN in both, 10 kN in neither.
2. **Hip reading (a) straddles the 40 kN stroke.** Ledger ray at x = 0: 45.09 to m2, 35.09 mm of room. Contact vertex at x = 16.04: 36.35 to m2, 26.35 mm. The second misses by 2.65 mm, little more than the 2 mm voxel. The module's 5 mm clearance decides it: without clearance it is 31.35 mm and fits. So "40 kN" is marginal.
3. **The hip's modules end at the HJC plane.** They stop 97.75 mm below the LSJ, the HJC is 97.68 mm. The trochanter is 8.4 mm above that, so it is on the module row; 10 mm below the HJC plane, in D3's hip zone, the ray meets nothing named. A stroke column of real height sees both.
4. **The buttock and back results need a stroke column that does not exist yet.** The rays clear m1 by 4.25 and 8.75 mm after its clearance. Any column wider than about 8.5 mm or 17.5 mm enters the reservation. The rays are lines; no ledger gives a footprint. The symmetric left side has the same gap.
5. **The hip mechanism is not in `components/thigh_R.yaml`,** contrary to the brief and 0037 D3's wording. That file holds two hand-typed worked examples ("not a catalogue part"), the higher ending 40 mm below the HJC, outside the hip zone. Neither is a hip part. No registry holds a hip part, the LSJ actuators, the knee mechanism, the shoulder mechanism or any structure. So every reading (a) here is itself an upper bound on room.
6. **The spine modules are alternatives, not a stack.** `reservations.yaml` lists candidate bodies; the placement is open (rm.v1-spine-reservation-decided). I subtract them from whichever body the ray is in, which counts them twice across pelvis and thorax. This is the conservative side for each zone taken alone. The v2 modules are themselves a reservation, not hardware.
7. **The thorax ledger's lateral ray is a cut plane, not skin.** `hw_right` holds 193.25 mm at the SJC station, the shoulder plane at 192.33 mm. The shoulder's skin is in `upper_arm_R`: 34.3 mm beyond the SJC at station 40, 4 mm below its joint station, the first row with a lateral ray.
8. **The hip registration (0007 D11) sits under the hip numbers.** The ledger frame and the model frame put the hip 16.5 mm apart. It moves the HJC depth from 71.2 to 87.75 mm and changes no cap at that limit. The modules were placed in the ledger frame, so the (a) row is unaffected.
9. **0037 D4(b) is 0.18 mm stale.** It says 41.73 mm for the thigh outside the hip zone; `thigh_R.yaml` t5 says 41.55 mm at station 398.1. The shank's 19.75 mm at station 360 and the hip zone's 81.25 mm stand. No cap moves.
10. **0008 D6(j) and 0037 D1(d) disagree on the arm.** D6(j) says dropping to 10 kN needs a superseding record, "because caps are frozen". D1(d)'s first-cap exception lets a capless zone take its cap by Revisions, and the arm has no cap entered. Your call in the brief already; flagged so the Amendments can settle it.
11. **The knee station assumes the zero pose.** "Forward collapse onto one knee" lands on a flexed knee, where the contact normal runs up the thigh rather than across it. Room along that normal is a different number and no ledger gives it directly. At the KJC plane the thigh's end and the shank's top agree (56.10, 56.11 mm), so the stroke's segment follows the mechanism, and D3 houses it in the thigh.
12. **Stale text.** `CLAUDE.md` still names `thread-sources-brief.md` as the current Ariadne brief, and the brief forbids my editing it, so `docs/STATE.md` hashes that brief and not this one. `tools/state` still says the suite takes about 18 minutes.

## Table

Shell 5 mm (0007 D4), the `hw_` or `r_` ray less t. (a) subtracts the first occupant on the ray and its clearance, with modules present in that body. "Released" is at that cap. Vertex is 0-based in `freyja-body-v3.obj`.

| Zone | Station for Joe to confirm | Skin depth | Occupant | Room (a) | Cap (a), released | Room (b) | Cap (b), released |
|---|---|---|---|---|---|---|---|
| hip | vertex 4296, pelvis s = 90, (16.04, -163.26, -88.42) pelvis ledger frame, normal -y; greater trochanter height, 8.4 mm above HJC | 162.75 `hw_right` | `part.spine.m2`, 45.09, clearance 5 | 35.09 | 40 kN, 0 kg | 157.75 | 10 kN, 0.50 kg |
| shoulder | vertex 1671, upper_arm_R s = 40, (-36.51, -223.19, -84.76) thorax ledger frame, normal -y | 226.63 (192.33 plane + 34.30 `hw_lat`) | `part.arm.upper_member`, 19.31 | 14.31 | none fits | 221.63 | 10 kN, 0.20 kg |
| buttock | vertex 4219, pelvis s = 70, (-112.91, -46.74, -70.64) pelvis ledger frame, normal -x | 110.62 `r_post` | `part.spine.m2`, 107.61, clearance 5 | 97.61 | 20 kN, 0.15 kg | 105.62 | 20 kN, 0.15 kg |
| back | vertex 3839, thorax s = 100, (-100.06, -82.45, -99.14) thorax ledger frame, normal -x | 98.90 `r_post` | `part.spine.m2`, 76.77, clearance 5 | 66.77 | 20 kN, 0.15 kg | 93.90 | 20 kN, 0.15 kg |
| knee | vertex 4605, thigh_R s = 398.1, (56.42, 3.80, -404.25) thigh_R frame, normal +x, zero pose | 56.10 `hw_ant` | none in a file | 51.10 | 20 kN, 0.30 kg | 51.10 | 20 kN, 0.30 kg |
| hand and arm | stroke home, not a contact | n/a | n/a | cannot be answered | n/a | cannot be answered | n/a |

Vertex against ledger, along the normal: hip 0.51, buttock 0.63, back 2.85, knee 0.32 mm, shoulder -3.44 mm. No room number comes from a vertex, except the variant row that says so.

### Variants

| Zone | Variant | Occupant | Room | Cap |
|---|---|---|---|---|
| hip | at the contact vertex's x | m2 | 26.35 | none fits |
| hip | modules not in pelvis | none | 157.75 | 10 kN |
| hip | to HJC, pelvis frame | node | 66.22 | 20 kN |
| hip | to HJC, thigh frame | node | 82.75 | 20 kN |
| buttock | midline `hw_post` | m1 | 14.79 | none fits |
| buttock | modules not in pelvis, midline | none | 83.70 | 20 kN |
| back | midline `hw_post` | m1 | 10.15 | none fits |
| back | modules not in thorax, midline | corridor | 51.15 | 40 kN |
| back | modules not in thorax, off midline | none | 93.90 | 20 kN |
| shoulder | inboard of SJC, arm moves as a block, model SJC x | m1, clearance 5 | 144.14 | 10 kN |
| shoulder | the same, mesh SJC x | m1, clearance 5 | 141.23 | 10 kN |
| knee | inscribed `cheb_r_t5` | none | 41.55 | 20 kN |

The shoulder's inboard rows are the nearest thing to 0008 D6(c)'s lateral arc, and they are straight lines, not that arc. They miss m2 by 9.9 and 1.5 mm (its back face is at x = -33.06), so the second is inside m2's 5 mm clearance and room falls as a column moves forward. They also pass through the unplaced shoulder mechanism. I report them and draft nothing on them.

### Shell sensitivity

No primary row's cap changes across the ledgers' shells.

| Zone | (a) t3 / t5 / t8 / t10 | (b) t3 / t5 / t8 / t10 |
|---|---|---|
| hip | 37.09 / 35.09 / 32.09 / 30.09 | 159.75 / 157.75 / 154.75 / 152.75 |
| shoulder | 16.31 / 14.31 / 11.31 / 9.31 | 223.63 / 221.63 / 218.63 / 216.63 |
| buttock | 99.61 / 97.61 / 94.61 / 92.61 | 107.62 / 105.62 / 102.62 / 100.62 |
| back | 68.77 / 66.77 / 63.77 / 61.77 | 95.90 / 93.90 / 90.90 / 88.90 |
| knee | as (b) | 53.10 / 51.10 / 48.10 / 46.10 |

The ledgers carry a shell only as `cheb_r_t*` and `area_t*`; those inscribed radii are in `room.json` beside each row. At the convex contact points the offset along the normal is t, so I subtract it from the ray.

## Hand and arm

`data/envelope/` cannot answer it, at 45 mm or at 90 mm. The stroke is an arc about the sternal end of the clavicle (0008 D6(c)). The pivot is in no file (0008 D6(c) says so and D9 leaves it to rm.v1-shoulder-concept), no ledger holds the shoulder shell's sweep, and the repo's sweeps cover the model's hinges and the column corridor. Answering needs a new sweep tool and a pivot choice 0007 does not make. Per the brief I stopped there and built nothing. No cap is proposed; 0008 D6(a)'s 20 kN stands as a design judgment, and the 0.15 kg claim stays.

## Draft entries (text only; nothing is applied)

Written for reading (a) with modules counted. Each is in 0037's form; the tests are D1(d)'s first-cap tests. If you pick (b), the hip reads 10 kN, 113 mm, 0.25 kg released per unit, and the shoulder gets an entry at 10 kN, 113 mm, 0.10 kg released per unit. Under (a) the shoulder gets none, as none fits. The arm gets none. Dates are left for whoever applies them.

- *Knee (recommended now).* YYYY-MM-DD. Knee zone, first cap (D1(d), D2(c)). F_cap = 20 kN, s_res = 28 mm, in the thigh. Room: 51.10 mm inside a 5 mm shell along the anterior normal at the KJC plane [source: data/envelope/thigh_R_sections.csv, station 398.1, hw_ant_mm, 56.10 mm; mesh freyja-body-v3.obj; inputs 00fcb645ad2c; data/falls/room.json], with no occupant in any registry; the inscribed radius there is 41.55 mm. Tests: (1) 20 kN is in the D2(c) series. (2) It is the lowest that fits: 10 kN needs 55 mm. (3) It only releases mass: 0.40 to 0.25 kg per unit, 0.30 kg in all. Result: valid. Interfaces in this zone are rated to 30 kN (D4a).
- *Hip (recommended hold).* YYYY-MM-DD. Hip zone, first cap (D1(d), D2(c)). F_cap = 40 kN, s_res = 29 mm, in the pelvis. Room: 35.09 mm inside a 5 mm shell along the lateral normal at the greater trochanter's height, less `part.spine.m2` and its 5 mm clearance [source: data/envelope/pelvis_sections.csv, station 90, hw_right_mm, 162.75 mm; mesh freyja-body-v3.obj; inputs 01a6e055b4a5; data/envelope/reserved/pelvis.yaml; data/falls/room.json]. Tests: (1) 40 kN is in the series. (2) It is the lowest that fits: 20 kN needs 57 mm. (3) It releases nothing: the claim stays at the 40 kN element, 0.40 kg per unit, and does not grow. Result: valid. Interfaces are rated to 60 kN (D4a).
- *Buttock (recommended hold).* YYYY-MM-DD. Buttock zone, first cap. F_cap = 20 kN, s_res = 57 mm, in the pelvis. Room: 97.61 mm inside a 5 mm shell along the posterior normal off the midline, less `part.spine.m2` and its 5 mm clearance [source: data/envelope/pelvis_sections.csv, station 70, r_post_mm, 110.62 mm; mesh freyja-body-v3.obj; inputs 01a6e055b4a5; data/envelope/reserved/pelvis.yaml; data/falls/room.json]. Tests: (1) 20 kN is in the series. (2) It is the lowest that fits: 10 kN needs 113 mm. (3) It only releases mass: 0.40 to 0.25 kg, 0.15 kg in all. Result: valid. Interfaces are rated to 30 kN (D4a).
- *Back (recommended hold).* YYYY-MM-DD. Back zone, first cap. F_cap = 20 kN, s_res = 57 mm, in the thorax. Room: 66.77 mm inside a 5 mm shell along the posterior normal off the midline, less `part.spine.m2` and its 5 mm clearance [source: data/envelope/thorax_sections.csv, station 100, r_post_mm, 98.90 mm; mesh freyja-body-v3.obj; inputs 01a6e055b4a5; data/envelope/reserved/thorax.yaml; data/falls/room.json]. Tests: (1) 20 kN is in the series. (2) It is the lowest that fits: 10 kN needs 113 mm. (3) It only releases mass: 0.40 to 0.25 kg, 0.15 kg in all. Result: valid. Interfaces are rated to 30 kN (D4a).

Proposed Amendments text for 0037:

> YYYY-MM-DD. Factual correction; no number and no decision changes. D3's Room known column says the pelvis, thorax and arm envelopes are not extracted, and Consequences says the same of "not extracted" zones. Those files now exist on the v3 baseline: `data/envelope/pelvis.yaml`, `thorax.yaml`, `abdomen.yaml`, `upper_arm_R.yaml`, `forearm_R.yaml`, `hand_R.yaml` and their section files. The room they give at each contact is in `data/falls/room.json` and memo 59. Cause: fall inputs brief, T1.

D4(b)'s 41.73 mm (finding 9) is a number, so the brief's "no change to any number" keeps it out of this text.

## Tolerances and choices

No tolerance touches a pass. All of these are locators or conventions, in `analysis/fall_room.py`.

- **Hip station:** greater trochanter height from `register.DUMAS_GT_ABOVE_HJC_MM` (Dumas 2007 Table 1B) times the pelvis scale, 8.4 mm above the HJC. The ANSUR trochanterion scaled is 3.0 mm above that (`leg_R_trial.json`). Pelvis row 90 is nearest.
- **Search slabs:** hip ±15 mm, wider than the vertex spacing there. Knee ±10 mm. Buttock and back use the whole body on the right side, within 180 mm of the midline, below the SJC's 192 mm. No slab changes a room.
- **Shoulder vertex:** nearest to the ledger's skin point, because the mesh's arm is in an A-pose and the ledger's at zero, so a support search cannot agree.
- **(a) subtracts the registry's `clearance_mm`.** The oracle's component margin does the same. Without it the hip row reads 40.09 mm: same cap on the ledger ray.
- **A ray within an occupant's axial extent grown by its clearance counts as hitting it.**
- **(b) stops at the body's axis:** the midline for lateral rays, the section's centre near the hip line for posterior ones. A full chord would be larger and less meaningful.
- **Error bar:** the ledgers' voxel is 2 mm, and 0007 D4 calls margins under one voxel marginal. Off-axis rays are analytic against the registries. Volumes do not enter.

## My mistakes

- I first set the hip station at the HJC plane by reasoning and committed that in 81d8601. A later search found the trochanter height already in `register.py`. The correction moved skin depth 163.77 to 162.75 and (a) 36.11 to 35.09. No cap moved. It also ended a real weakness: the first ray grazed the module's end by 0.05 mm.
- A 5 mm hip slab missed the lateral vertex ring by 12 mm, and it silently changed a variant: that ray missed m2 and read 10 kN, where the corrected one reads none fits. I caught it on the vertex-against-ledger column.
- My first design had an `--out` argument, which G3 would not allow. Removed before commit.

## Questions for Joe

1. Are the five stations right? In particular the back at the scapula (off-midline) and the knee in the zero pose.
2. Which reading of spare, and does the HJC count as a limit at the hip?
3. Apply the knee entry now, and hold the rest as recommended?
4. For the buttock and back, must the zone's contact include the midline? If so, with modules in that body, none fits, and D2(c) sends that zone to a superseding record.
5. Release T2?
