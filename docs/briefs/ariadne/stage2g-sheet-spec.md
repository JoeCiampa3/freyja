# Stage 2g sheet spec: what Joe edits in the Freyja Anthropometric Reference

Authored. Owner: Joe. This is the contract between the sheet and `docs/briefs/ariadne/stage2g-brief.md`. Code reads it for key names and units and never edits the sheet. If the sheet and this file disagree, Code stops and asks. Values are for a 1700 mm stature, a 12.0 degree standing pelvic tilt and the ADR 0038 closure; Joe may change an input, but the formulas stay.

I could not see the sheet's cell layout, so rows and cells are named by label. Keep every existing named range (`bsip`, `pos`, `rom`, `targets`) pointing at the same kind of rows. Adding or removing rows inside a range means resizing its named range.

## 1. Posture and scaling (BSIP Reference)

Inputs, once, on a visible input cell each:

| Name | Value | Source |
|---|---|---|
| `stand_pelvis_tilt_deg` | 12.0 | memo 23 D2: static Dumas-frame tilt, 17 subjects, mean 12.43, SD 3.90; ADR 0004 |
| ANSUR II mean female stature, mm | 1628.5 | ANSUR II female, n = 1986 |
| Dumas HJC rel LJC, reference, X and Y (mm) | 54 forward, 93 down | Dumas 2007 Table 1B, pelvis |

Formulas (all lengths mm, Dumas reference lengths as already in the sheet: shank 388, thigh 379, pelvis 107, abdomen 121, thorax 313, head and neck 253, upper arm 243, forearm 247, hand 71, foot 165):

- ankle height = 62.7 x `target_stature` / 1628.5 (the current 62.7 cell is the ANSUR mean for a 1628.5 mm stature)
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
| `foot_length_total_mm` | 257.11 | 246.3 x `target_stature` / 1628.5 (ANSUR II female foot length, mean 246.3) |
| `foot_ball_length_mm` | 190.10 | 182.1 x `target_stature` / 1628.5 (ANSUR II ball-of-foot length: heel to first MTP) |
| `toe_hinge_ahead_ankle_mm` | 128.12 | `foot_ball_length_mm` - `foot_heel_behind_ankle_mm` |
| `toe_tip_ahead_ankle_mm` | 195.14 | `foot_length_total_mm` - `foot_heel_behind_ankle_mm` |
| `foot_half_width_mm` | 50 | design choice; moved from the template, no source |
| `toe_height_mm` | 25 | design choice, no source |
| `toe_mass_fraction` | 0.144 | Matsumoto 2022 (CT, one man); toe mass = this x the whole-foot mass |
| `toe_com_fraction` | 0.436 | Matsumoto 2022; fraction of the toe length from the hinge |
| `toe_stiffness_nm_per_deg` | 0.25 | **placeholder** in the 0.1 to 0.7 bracket of ADR 0001; not a design value |
| `toe_damping_nm_s_per_rad` | 0.05 | **placeholder**; not a design value |

Derived by the preprocessor, for information: toe length 67.02 mm (hinge to tip), toe mass 0.0936 kg, its centre 29.2 mm from the hinge, the foot box 62.0 mm behind and 128.1 mm ahead of the ankle for the remainder foot, and 257.1 mm in all.

The whole-foot BSIP row (mass, centre of mass, inertia) stays exactly as Dumas published it, scaled by `k`: Code splits it, the sheet does not.

## 3. Joint ROM (Joint ROM sheet and MuJoCo Reference section D)

Add the toe, and fill the seven. Every new row needs the same columns as its neighbours (ceiling, functional demand, Freyja target, hard constraint, MuJoCo limit FINAL).

| Joint | Movement | Ceiling | Functional | Target | FINAL | Source |
|---|---|---|---|---|---|---|
| Toe | Extension | - | 54 to 70 | 80 | 80 | Nigro and Arch 2022 (peak toe angle, 0.68 to 1.71 m/s, SD 6 to 7); ADR 0001 |
| Toe | Flexion | - | - | 0 | 0 | hard stop at flat; ADR 0001 |
| Lumbosacral | Flexion | **to source** | | | | |
| Lumbosacral | Extension | **to source** | | | | |
| Lumbosacral | Lateral bending | **to source** | | | | |
| Lumbosacral | Axial rotation | **to source** | | | | |
| Shoulder | Adduction | **to source** | | | | |
| Shoulder | External rotation | **to source** | | | | |
| Shoulder | Internal rotation | **to source** | | | | |

The ROM keys the preprocessor reads are `toe_extension`, `toe_flexion`, `lumbosacral_flexion`, `lumbosacral_extension`, `lumbosacral_lateral_bending`, `lumbosacral_axial_rotation`, `shoulder_adduction`, `shoulder_external_rotation`, `shoulder_internal_rotation`.

**Sourcing, and what Soucie 2011 does and does not give.** Soucie et al. (Haemophilia 2011) measured hip, knee, ankle, shoulder flexion and the elbow only, so none of the seven is in it (the sheet already says so for the spine). Candidates, to be checked against the papers before any number is entered:

- Shoulder adduction, external and internal rotation: Boone and Azen 1979 (J Bone Joint Surg Am 61:756-759), the paper the sheet already uses for shoulder extension and abduction (male, over 19 years; log the population mismatch as elsewhere); or the AAOS reference values. Define "adduction" before sourcing it: from anatomical neutral (arm at the side) past the midline, or from an abducted position back to the side.
- Lumbosacral, four motions: v1 has one trunk joint (thoracic and cervical rigid), so the sheet's "regional" convention applies: trunk relative to pelvis, summed over levels, not the L5-S1 segment alone. Use a regional source for the trunk (thoracolumbar), and say which. Stage 2's trunk modes need it to exceed the demand: counter-rotate peaks reach 8.9 and 10.7 degrees of lateral bending and 16.4 and 20.7 of axial rotation (maxima, 1.4 and 1.6 m/s). Frames beyond a new limit are reported, not clipped.

Add a note on the hip extension row: "Dumas pelvic frame (ISB), side-lying; ADR 0004".

## 4. What the sheet must show before `fy build`

- Top of head minus stature, vertical closure: 0.000 mm.
- Segment lengths as listed in section 1, ten of them.
- The `design` range with all twelve keys.
- No empty cell in the nine new ROM rows (Part B stops otherwise).

## 5. What Code does not read

The foot width default, the toe stiffness and damping sweep, and any note column. Positions in 'MuJoCo Positions' and the BSIP block in 'MuJoCo Reference' follow from the lengths as they do today; resize their named ranges only if you add rows.
