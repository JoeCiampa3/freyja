# Stage 2g sheet spec: what Joe edits in the Freyja Anthropometric Reference

Authored. Owner: Joe. This is the contract between the sheet and `docs/briefs/ariadne/stage2g-brief.md`. Code reads it for key names and units and never edits the sheet. If the sheet and this file disagree, Code stops and asks. Values are for a 1700 mm stature, a 12.0 degree standing pelvic tilt and the ADR 0038 closure; Joe may change an input, but the formulas stay.

I could not see the sheet's cell layout, so rows and cells are named by label. Keep every existing named range (`bsip`, `pos`, `rom`, `targets`) pointing at the same kind of rows. Adding or removing rows inside a range means resizing its named range.

## 1. Posture and scaling (BSIP Reference)

Inputs, once, on a visible input cell each:

| Name | Value | Source |
|---|---|---|
| `stand_pelvis_tilt_deg` | 12.0 | memo 23 D2: static Dumas-frame tilt, 17 subjects, mean 12.43, SD 3.90; ADR 0004 |
| Dumas HJC rel LJC, reference, X and Y (mm) | 54 forward, 93 down | Dumas 2007 Table 1B, pelvis |

**ANSUR II inputs** (summary statistics only; the dataset stays outside the sheet and the repo). One cited block, cells that the formulas below and the `design` range point at:

| ANSUR II female (Gordon et al. 2014, NATICK/TR-15/007; public CSV; n = 1986) | mean mm | SD mm | Measurer's Handbook definition |
|---|---|---|---|
| stature | 1628.5 | 64.2 | |
| foot length | 246.3 | 12.4 | back of the heel (pternion) to the tip of the longest toe (acropodion), Brannock device, standing (6.4.37) |
| ball of foot length | 182.1 | 9.6 | back of the heel to the first metatarsophalangeal protrusion, same device and stance (6.4.8) |
| lateral malleolus height | 62.7 | 5.1 | vertical distance from the standing surface to the lateral malleolus landmark (6.4.60) |

Footwear is not stated in those entries. Code reproduced the four means from the CSV (memo 23, D8); the existing 62.7 cell already cites this report.

Formulas (all lengths mm, Dumas reference lengths as already in the sheet: shank 388, thigh 379, pelvis 107, abdomen 121, thorax 313, head and neck 253, upper arm 243, forearm 247, hand 71, foot 165):

- ankle height = ANSUR lateral malleolus height x `target_stature` / ANSUR stature (62.7 x 1700 / 1628.5; the current 62.7 cell is the ANSUR mean for a 1628.5 mm stature)
- pelvis vertical drop (reference) `v` = 54 x sin(tilt) + 93 x cos(tilt)
- stack (reference) = shank + thigh + abdomen + thorax + head and neck + `v`
- **`k` = (`target_stature` - ankle height) / stack**
- column D (length) of **all ten** segments = Dumas reference length x `k`, the pelvis included (it keeps 107 x `k` as its normaliser, not its vertical drop)

Expected values: ankle height 65.45; `v` 102.195; stack 1556.195; **`k` 1.05035**; shank 407.54, thigh 398.08, pelvis 112.39, abdomen 127.09, thorax 328.76, head and neck 265.74, upper arm 255.23, forearm 259.44, hand 74.57, foot 173.31.

Integrity check (replace E2's "top of head minus stature"): ankle height + k x (shank + thigh + abdomen + thorax + head and neck) + k x `v` - `target_stature` = 0.000 mm. Keep the old figure beside it, relabelled "chord closure, upright pelvis", so the change is visible.

Fix the foot row's note: Dumas's L = 165 mm is the distance from the calcaneus to the midpoint of the first and fifth metatarsal heads (Table 1B: 59 + 106.5 = 165.5; male 46 + 137 = 183), not from the ankle joint centre; it is the BSIP normaliser only. Fix the B3 summary labels ("Pelvis scale factor" is now the general `k`).

## 2. Foot and toe geometry (new named range `design`)

A new two-column range, key in the first column and a number in the second, named `design`. Keys are exact. The preprocessor converts units.

| Key | Value | Formula or source |
|---|---|---|
| `stand_pelvis_tilt_deg` | 12.0 | the input cell above (link) |
| `foot_heel_behind_ankle_mm` | 61.97 | 59 x `k` (Dumas Table 1B, calcaneus x; the dataset's shoe markers give 65.5 +/- 2.4) |
| `foot_length_total_mm` | 257.11 | ANSUR foot length x `target_stature` / ANSUR stature (246.3 x 1700 / 1628.5) |
| `foot_ball_length_mm` | 190.10 | ANSUR ball of foot length x `target_stature` / ANSUR stature (182.1 x 1700 / 1628.5): heel to first MTP |
| `toe_hinge_ahead_ankle_mm` | 128.12 | `foot_ball_length_mm` - `foot_heel_behind_ankle_mm` |
| `toe_tip_ahead_ankle_mm` | 195.14 | `foot_length_total_mm` - `foot_heel_behind_ankle_mm` |
| `foot_half_width_mm` | 50 | design choice; moved from the template, no source |
| `toe_height_mm` | 25 | design choice, no source |
| `toe_mass_fraction` | 0.144 | Matsumoto 2022 (CT, one man); toe mass = this x the whole-foot mass |
| `toe_com_fraction` | 0.436 | Matsumoto 2022; fraction of the toe length from the hinge |
| `toe_stiffness_nm_per_deg` | 0.25 | **placeholder** in the 0.1 to 0.7 bracket of ADR 0001; not a design value |
| `toe_damping_nm_s_per_rad` | 0.05 | **placeholder**; not a design value |
| `ansur_female_stature_mm` | 1628.5 | provenance input (the block in section 1); Code only compares it with the CSV |
| `ansur_female_footlength_mm` | 246.3 | provenance input |
| `ansur_female_balloffootlength_mm` | 182.1 | provenance input |
| `ansur_female_malleolusheight_mm` | 62.7 | provenance input |

Derived by the preprocessor, for information: toe length 67.02 mm (hinge to tip), toe mass 0.0936 kg, its centre 29.2 mm from the hinge, the foot box 62.0 mm behind and 128.1 mm ahead of the ankle for the remainder foot, and 257.1 mm in all.

When `data/ansur2/raw/ANSUR_II_FEMALE_Public.csv` is present, a test recomputes the four ANSUR means and compares them with these keys; nothing else reads them.

The whole-foot BSIP row (mass, centre of mass, inertia) stays exactly as Dumas published it, scaled by `k`: Code splits it, the sheet does not.

## 3. Joint ROM (Joint ROM sheet and MuJoCo Reference section D)

Add the toe, and fill the seven. Every new row needs the same columns as its neighbours (ceiling, functional demand, Freyja target, hard constraint, MuJoCo limit FINAL).

| Joint | Movement | Ceiling | Functional | Target | FINAL | Source |
|---|---|---|---|---|---|---|
| Toe | Extension | - | 54 to 70 | 80 | 80 | Nigro and Arch 2022 (peak toe angle, 0.68 to 1.71 m/s, SD 6 to 7); ADR 0001 |
| Toe | Flexion | - | - | 0 | 0 | hard stop at flat; ADR 0001 |
| Lumbosacral | Flexion | 69.9 | | | 69.9 | Apti, Colak, Akcay 2023 (below) |
| Lumbosacral | Extension | 40.0 | | | 40.0 | same |
| Lumbosacral | Lateral bending | 36.3 | 8.9 to 10.7 (counter-rotate maxima) | | 36.3 | same (right 36.3, left 36.2); one-sided |
| Lumbosacral | Axial rotation | 38.5 | 16.4 to 20.7 (counter-rotate maxima) | | 38.5 | same (right 38.4, left 38.6); one-sided |
| Shoulder | External rotation | 94.5 | | | 94.5 | Moromizato et al. 2016, females (n = 36), passive (below) |
| Shoulder | Internal rotation | 67.4 | | | 67.4 | same |
| Shoulder | Adduction | **to source** | | | | open: define the motion first, then read it from Moromizato Table 1 (females) or Boone and Azen 1979 |

The ROM keys the preprocessor reads are `toe_extension`, `toe_flexion`, `lumbosacral_flexion`, `lumbosacral_extension`, `lumbosacral_lateral_bending`, `lumbosacral_axial_rotation`, `shoulder_adduction`, `shoulder_external_rotation`, `shoulder_internal_rotation`.

Soucie et al. (Haemophilia 2011) measured hip, knee, ankle, shoulder flexion and the elbow only, so none of the new rows comes from it.

**Lumbosacral: Apti, Colak and Akcay 2023** (J Turk Spinal Surg 34(3):113-117, doi 10.4274/jtss.galenos.2023.33042). v1's single trunk joint stands in for all trunk motion relative to the pelvis, so the ceiling must be a regional trunk-on-pelvis range (the sheet's "regional" convention), not the lumbar segments alone. That paper measures exactly that, by the AAOS method with a two-arm digital goniometer, active motion, 300 volunteers aged 18 to 29 (198 women): flexion with the pivot at the lumbosacral joint and the moving arm along the trunk to the axilla, the hip held still; lateral bending with the pivot at the lumbosacral joint and the moving arm along the spine to C7; rotation seated, the shoulder line against the pelvis. Means (SD): flexion 69.9 (14.5), extension 40.0 (10.2), lateral bending 36.3 (6.4) right and 36.2 (6.6) left, rotation 38.4 (8.7) right and 38.6 (9.4) left. It quotes AAOS 80, 25, 35, 45 and Kendall 90, 35, 40, 35 for the same four, which bracket these. Pooled values are used because it finds a sex difference only for flexion (women higher; its Figure 2 has the split). Limits: a Turkish sample, active not passive, goniometry on the trunk. Cross-check, not a source: Moromizato et al. 2016 (passive, a different whole-body protocol, females n = 36) give trunk flexion 32.9, extension 28.3, rotation 43.9 and lateral bending 21.3, so flexion differs by a factor of two with the protocol; the sheet takes the larger so that no Stage 2 demand is clipped. Troke et al. 2005 (Man Ther 10:198-206) is lumbar only and Dvorak et al. 1991 is one segment: neither is the joint v1 builds.

**Shoulder rotations: Moromizato et al. 2016** (J Physiol Anthropol 35:23, doi 10.1186/s40101-016-0112-8). Sex-matched (females, mean height 156.9 cm), passive like Soucie, one protocol for the whole body. Female external rotation 94.5 (SD 8.2), internal rotation 67.4 (SD 9.2); AAOS gives 90 and 65 to 70, within 5 degrees. Cross-check against Boone and Azen 1979 (male, over 19 years, already in the sheet for shoulder extension and abduction) when you have the paper: a difference over 10 degrees is worth a note, not a change. Define adduction before sourcing it: from anatomical neutral (arm at the side) past the midline, or from an abducted position back to the side.

Add a note on the hip extension row: "Dumas pelvic frame (ISB), side-lying; ADR 0004".

## 4. What the sheet must show before `fy build`

- Top of head minus stature, vertical closure: 0.000 mm.
- Segment lengths as listed in section 1, ten of them.
- The `design` range with all sixteen keys.
- No empty cell in the nine new ROM rows (Part B stops otherwise); shoulder adduction is the one still open.

## 5. What Code does not read

The foot width default, the toe stiffness and damping sweep, and any note column. Positions in 'MuJoCo Positions' and the BSIP block in 'MuJoCo Reference' follow from the lengths as they do today; resize their named ranges only if you add rows.
