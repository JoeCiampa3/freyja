---
id: adr-0002
status: accepted
date: 2026-10-22
links: [adr-0001, "Freyja_Anthropometric_Reference (Google Sheet, v4)"]
---

# ADR 0002: Anthropometric basis

> Markers: **[DECIDE]** = a choice only you can make. **[CONFIRM]** = something I added or inferred that you should check against the sheet. Delete all markers before accepting.

## Context

Freyja is a 170 cm biomimetic humanoid (female reference) built to resemble a human in form and movement, so every design dimension and inertial property traces back to an anthropometric basis. Ideally one rigorous source would supply everything: body segment inertial parameters (BSIP: mass, centre of mass (CoM), inertia), segment lengths, joint centre positions, and joint range of motion (RoM). No such source exists. The basis is therefore assembled from several papers, and this ADR records the rules for assembling it consistently and the error we accept by doing so.

Abbreviations: SCS = segment coordinate system, JCS = joint coordinate system, HJC = hip joint centre, ISB = International Society of Biomechanics.

Scope: this ADR governs which sources supply which quantity, how they are scaled to Freyja, and what authority the basis has relative to CAD and the MakeHuman mesh. Per-quantity values live in the reference sheet, not here.

## Decision

**1. Authority.** The reference sheet (Freyja_Anthropometric_Reference) is the single source of truth for design dimensions and drives CAD and MuJoCo. The ADR owns the rules and rationale; the sheet owns the values. If they disagree, the sheet's committed values win and the ADR is amended.

**2. Stature and mass.**
- Stature is locked at 170 cm.
- Total mass is a target, not a lock. It is updated as CAD and hardware mature.

**3. Scaling method.**
- Each source reports lengths for its own reference population. Every source length is multiplied by 170 cm / (that source's reference stature). Do not apply one global factor across sources. [CONFIRM]
- Segment mass = (source mass fraction) × (total target mass). Mass fractions are normalized to sum to 100%; any residual is distributed proportionally across segments. Record the pre-normalization sum in the sheet. [CONFIRM]
- CoM is stored as a fraction of segment length in the segment frame and scales with length. Inertia comes from radii of gyration normalized by segment length, so inertia scales as m·L². [CONFIRM source normalization]
- Closure: the standing-height segment stack must sum to the locked stature. The residual is absorbed by **[DECIDE: one uniform factor on the standing-height stack / a named segment / ...]**. The sheet reports the residual before and after correction. Known approximation: the stature scale factor treats the stack as vertical, which the pelvis (107 mm chord) is not.
- Arm, forearm, hand and foot lengths use the same factor as the standing-height stack. [CONFIRM]

**4. Coordinate conventions.** Segment and joint coordinate systems follow ISB (Wu 2002 for ankle, hip and spine; Wu 2005 for shoulder, elbow, wrist and hand; Grood & Suntay 1983 for the knee). BSIP data from Dumas is recorded in frames compatible with this convention and is not transformed. RoM is a separate case: see rule 6.

**5. Source hierarchy.** (Snapshot of the sheet's References block.)

| Quantity | Primary | Cross-check / note |
|---|---|---|
| Mass, CoM, inertia | Dumas 2007 (female), from the McConville / Young et al. dataset | Thorax and abdomen: Dumas 2015. Head and neck: Dumas 2007 corrigendum. de Leva (female) for limbs only |
| Segment lengths | Dumas 2007 | Dumas does not report toe, lateral malleolus height, ball-of-foot or foot length. These come from ANSUR II |
| HJC | Dumas-internal (Reed-based), Dumas 2007 Table 1, scaled with the pelvis | Harrington 2007, Hara 2016, Bell 1990 as cross-checks |
| Knee / ankle JC | Landmark midpoints (femoral epicondyles / malleoli) | Not a regression |
| Toe mass and mass fraction | Matsumoto 2022 | Toe stiffness and damping are placeholders (see Open items) |
| RoM, anatomical ceiling | Soucie 2011 | Extremities: Boone & Azen 1979. Lumbosacral: Apti 2023 (whole-lumbar RoM applied to the single L5/S1 joint). Nigro & Arch: **[CONFIRM which joint]** |
| RoM, functional target | Gait / stair / sit-to-stand kinematics | Separate column from the ceiling |
| External dimensions | The sheet | ANSUR II female as cross-check on girths and breadths |

**6. RoM rules.**
- "Anatomical ceiling" means **[DECIDE/CONFIRM: the sourced female population mean]**. It is a reference value, not a hard limit. The functional target column may exceed it where function demands (for example ankle dorsiflexion ≥ 25°, roughly +2 SD).
- Source RoM values are clinical goniometric measurements and are not guaranteed to correspond to ISB Euler-angle limits at multi-DOF joints (hip, shoulder). They are recorded as ceilings, not transformed.
- Where the Freyja column deliberately deviates from the literature, the sheet carries a provenance note (example: hip extension 31°, dataset peak plus about 10% margin).
- Placeholders must be unmistakable as non-data: use an explicit sentinel (empty cell plus a TODO flag, or NaN), never a plausible number. Shoulder adduction is a pose-dependent quantity, to be replaced by a model built from a known horizontal flexion value, and is tracked in Open items.

**7. Segment masses versus CAD.** The basis defines target segment masses. Fusion mass properties are a derived read-out and are not an independent target. When CAD segment mass diverges from the basis by more than **[DECIDE: tolerance, e.g. ±10% per segment, ±5% total]**, the response is to **[DECIDE: update the basis target / rebalance hardware / log a waiver]**, recorded in the sheet. Segment density is a sanity check only.

**8. MakeHuman.** The mesh is a visual aid and envelope check (external appearance, volume characterization, component fit visuals). It is layered over the CAD model and aligned by external landmarks. It is not authoritative and its proportions do not define Freyja's dimensions. Spot reads from the mesh during derivation work are allowed per instance.

## Consequences

**Accepted costs**

- *Mixed RoM sources.* No single source covers every joint. The mismatch introduces error, and ceiling RoM tolerates a few degrees of it.
- *Subject mismatch.* Boone & Azen's subjects are male, age > 19, while the reference is female. This error is directional rather than random: as far as I recall, female RoM is typically greater at most joints. Where a male source is the primary, the sheet flags the joint, and the ceiling is read as a conservative estimate. [CONFIRM direction per joint against Soucie]
- *Mixed length sources.* ANSUR II supplies lengths Dumas does not report. Error is unavoidable. The sheet flags every ANSUR-sourced length.
- *Multiple Dumas papers for BSIP.* Acceptable only if the 2007, 2015 and corrigendum segment definitions are compatible. This is a check, not an assumption: adjacent segment boundaries must be contiguous and mass fractions must sum to a known total (see rule 3).

**What must change when this is accepted**

- The sheet implements the scaling and closure rules, and carries the residual report, the pre-normalization mass sum, and the flags above.
- CAD and MuJoCo are regenerated from the sheet, not edited by hand.
- Any value in CAD or MuJoCo that is not traceable to a sheet row is a defect.

**Revisit this decision if**

- The closure residual cannot be absorbed without a segment visibly leaving its source's range.
- CAD mass divergence exceeds the rule-7 tolerance on more than a few segments.
- A single dataset covering BSIP, lengths and RoM for a female population becomes available.

## Rejected options, and why each one died

**Chosen:** basis derived from literature, assembled under the rules above.

**MakeHuman mesh as the basis.** Measure segment lengths from external landmarks on the mesh. Consistent with the external skin envelope sizing. Rejected: external measurements on the mesh carry significant error, and many landmarks, such as the lumbosacral joint, cannot be located from the surface. [CONFIRM completion of your truncated sentence, and add any further reasons]

**Single-source basis (Dumas only, or de Leva only).** Removes mixing error. Rejected: Dumas does not report foot and toe dimensions or RoM, and de Leva (female) covers limbs only. **[CONFIRM / expand: the mixing costs above are accepted because no single source is complete.]**

**Harrington 2007 as primary HJC.** Regression-based and widely used. Superseded 2026-09 by the Dumas-internal (Reed-based) HJC so the HJC shares the pelvis frame and scaling with the rest of the BSIP data. Harrington is retained as a cross-check. **[CONFIRM reason]**

## Open items

- Shoulder adduction RoM: placeholder pending the pose-dependent model. Replace the current 0° with an explicit sentinel.
- Toe stiffness and damping: placeholders in the sheet.
- Closure rule, ceiling statistic, and CAD tolerance: the **[DECIDE]** markers above.
- Pelvis non-verticality in the stature scale factor.

## References

Full citations and per-quantity notes are in the reference sheet's References block. Cited here: Dumas et al. 2007 (and corrigendum), Dumas et al. 2015, McConville et al. / Young et al. (underlying dataset), de Leva 1996, ANSUR II, Matsumoto 2022, Soucie 2011, Boone & Azen 1979, Nigro & Arch, Apti 2023, Wu et al. 2002 and 2005, Grood & Suntay 1983, Harrington 2007, Hara 2016, Bell 1990, Reed (HJC).
