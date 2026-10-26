STATE: base d93d201b8320 | brief architecture sha256:61e4b1bc4023, ariadne sha256:155afbaa35f6 | snapshot sha256:492fe816e6d8 | tests 1616/1620 | dirty yes

# Memo 33: memo 32 decisions applied (row roles, limbs on the uniform-density basis, Dumas 2007 Table 2 check)

Follows memo 32 and your six decisions. No mesh, cut, gate or tolerance changed; `fy envelope gates` on v2 reproduces memo 32's numbers and all six gates pass.

## Decision summary

- **What it means for Freyja.** The reported result set is now the one you asked for: the lumped region, the shank, the foot and the whole body. On the basis that Dumas 2007 section 2.1 establishes (1 g/cm3 for all 17 segments, so every sheet mass is a volume share), the sculpt's abdomen + pelvis + thighs region carries 9.0% less volume share than the sheet's mass share (raw ratio 1.099), the shank 4.8% more (0.954) and the foot 8.0% more (0.926). The sheet itself reproduces the paper's Table 2 to 0.03 percentage points, so the sheet is not the source of any of this.

| Number | Value | Reference |
|---|---|---|
| Lumped (MSR10 to KJC planes) raw ratio | 1.099 | 1.00; Dempster-normalised 1.058 kept as the cross-check |
| Shank / foot raw ratio (primary and only) | 0.954 / 0.926 | 1.00 |
| Dempster lumped share vs sheet | 48.10% vs 47.95% | unchanged |
| Sheet thorax + abdomen share | 30.43% | Dumas 2007 Table 2 female, 30.4% (+0.03 points) |
| Sheet pelvis / thigh / shank / foot share | 14.61 / 14.61 / 4.50 / 1.00% | 14.6 / 14.6 / 4.5 / 1.0% |
| Whole body: volume, M_mesh, BMI | 52.331 l, 52.10 kg, 18.05 | reference subjects 63.9 kg at 1.61 m (BMI 24.7) |

- **Decisions for you.** None open from this memo. The one choice I made without asking is the role labelling below (item 3); say if you want thigh x2 + pelvis promoted back to a result.
- **What would change the conclusion.** Nothing in this memo moves a number; it only changes which are reported.

## 1. Row roles (decision 3)

Every share row now carries a `role` in `leg_R_trial.json`: `result` for `lumped_msr10`, `shank`, `foot`; `diagnostic` for the abdomen rows (decision 3); `non_result` for pelvis alone and thigh alone in every variant (they trade volume with each other as the lower cut moves: pelvis 1.003 at the hip-centre cut against 0.674 at the crotch apex); `sensitivity` for everything else, including thigh x2 + pelvis and the +-10 mm, RR10, ANSUR and lumbosacral variants of the lumped region. The `fy envelope gates` printout tags each row. I classed thigh x2 + pelvis as a sensitivity rather than a result because you listed only the lumped region, shank, foot and whole body; its numbers (1.121 hip-centre cut, 1.120 crotch cut) are unchanged and remain in the file.

## 2. Limbs on the uniform-density basis (decision 4)

Dumas et al. 2007 (J Biomech 40:543-553), section 2.1: McConville et al. (1980) and Young et al. (1983) computed the BSIPs "assuming a uniform density of 1 g.cm-3", with the same 17 segments in both. `reference_densities.json` now cites it (`uniform_density_basis`: source, section 2.1, the statement, 1 g/cm3, all 17 segments). The shank and foot rows no longer carry an expected tissue ratio or a normalised ratio; the raw ratio is their only share number (`ratio`), with sheet mass / skin volume and the implied density unchanged. The lumped row keeps both columns and the Dempster lumped-share cross-check stays as it was (48.10% against 47.95%). Winter's densities (thigh 1.05, leg 1.09, foot 1.10) still feed the thigh rows and the lumped reference density, which are non-results and a cross-check respectively.

Page: section 2.1 is on journal page 544 in the PDF I read (`data/literature/Dumas et al 2007 BSIP Data.pdf`); I cited the section, not the page.

## 3. Table 2 check (decision 5)

Sheet masses (snapshot, one side for the limbs) over the sheet's total of 64.935 kg, against Dumas 2007 Table 2, female column:

| Segment | Sheet kg | Sheet % | Table 2 % | Difference (points) |
|---|---|---|---|---|
| Thorax + abdomen | 17.095 + 2.665 = 19.760 | 30.43 | 30.4 | +0.03 |
| Pelvis | 9.490 | 14.61 | 14.6 | +0.01 |
| Thigh | 9.490 | 14.61 | 14.6 | +0.01 |
| Shank | 2.925 | 4.50 | 4.5 | 0.00 |
| Foot | 0.650 | 1.00 | 1.0 | 0.00 |

The differences are the rounding of Table 2's one-decimal percentages. The sheet therefore uses Table 2's female shares as printed, which supports reading its masses as the paper's volume shares. The check is computed (`masses.table2_check`, output `mass_base.table2_check` in `leg_R_trial.json`) from the snapshot and the reference values stored in `reference_densities.json`, not typed into the memo.

## 4. Context note (decision 6; not a conclusion)

The reference population behind the sheet's shares (Young et al. 1983, 46 females) averaged 31.2 years, 63.9 kg and 1.61 m (Dumas 2007 section 2.1), a BMI of 24.7. The sculpt's BMI is 18.05 at 1.699 m (mass from body fat 0.207 and lung gas removed). Dumas 2007 section 2.1 reports the original technique's segment-mass errors, against six cadavers, as under 5% for head, forearms, legs and feet and under 10% for the trunk (neck + thorax + abdomen + pelvis), arms, thighs and hands. For scale, the differences above are 4.8% (shank), 8.0% (foot) and 9.0% (lumped region); I draw no inference from the comparison.

## 5. Tests and files

Tests: 1616 passed of 1620 by `fy state`: the one failure is the known, out-of-scope gait-extract test; 3 skipped. New tests in `tests/test_envelope_dumas_cuts.py` (4: roles, no normalised column for shank and foot, the citation, the Table 2 check). One test changed: the densities test now requires the edition and page you filled in. `SheetNodes` gained `thorax_mass_kg`. Changed: `masses.py`, `gates.py` (printout), `register.py`, `reference_densities.json`. `CONVENTIONS.md` needed no change.

Mistake: my first printout edit for the shank and foot rows had a precedence error that I caught when reading the file back, before running it.

Landmark file used: none. Mesh `data/makehuman/freyja-body-v2.obj`; knee anchor `chords`; shear kept; voxel 2 mm; topology reference `base.obj` sha 8e761e66....
