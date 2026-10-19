---
id: adr-0001
status: proposed
date: 2026-10-19
links: []
---
## Context

Freyja's foot is a rigid, flat, toeless box. Stage 2 asked whether that can represent walking and, if not, what a toe would have to do. This record was first written on 2026-10-11 with the decision open; the numbers below are the ones after Stage 2c to 2e (memo 12) and are stamped with snapshot e5cc96ceed7e, taken before the BSIP re-verification and the scaling and posture decisions. They are interim until `rm.v1-stage2-closed`.

- **The measured centre of pressure leaves the box in late stance.** Counting stance from each foot's own heel strike (memo 12), at 1.4 m/s the CoP is outside the contact polygon in 98.2% of single-support frames at 80 to 90% of stance (median 17 mm) and in 99.9% and 100% of double-support frames at 80 to 90% and 90 to 100% (median 31 and 78 mm); at 1.6 m/s in 100% (30 mm), 100% (43 mm) and 99.9% (93 mm). In early and mid stance 25.9, 19.8, 14.7 and 14.9% of single-support frames fail at 10 to 50% (median 15 to 34 mm); without the ankle offset these are 32.3, 31.6, 34.4 and 29.5%. The early-stance failures in double support (56% at 0 to 10%, median 33 mm; 80% without the offset) happen with the heel down and are not a toe effect.
- **The torque argument for a toe no longer holds.** `docs/briefs/stage2-brief.md` T3b estimated that a toeless box caps the late-stance ankle torque at about 140 N m (peak ground force times the foot's 165 mm reach; not recomputed here). `A_filtered`'s ankle plantarflexion 95th percentile is 124.8 and 140.0 N m (right, left) at 1.4 m/s and 132.7 and 144.6 at 1.6 m/s: 11% below to 3% above that estimate (maxima 139.4 to 180.6 at 1.4 and 147.7 to 174.1 at 1.6). The geometric argument (the CoP leaves the box) stands; the claim that a toeless box caps a load the human exceeds does not.
- **B is not rescued by a toe.** B's CoP sits 73 to 76 mm behind the measured one at 1.4 m/s (hip-referenced, memo 10). A toe addresses late-stance foot geometry, not that offset.
- **The dataset cannot supply the toe's own loads.** Its OpenSim model locks the joint: over 17 subjects, 988 strides and 1976 stride-feet the largest `mtp_angle` is exactly 0 degrees and each subject's largest `mtp` moment is 0.13 to 0.30 N m (`python sim/scripts/gait_diag.py toe`). The numbers in the Decision section therefore come from the literature, below.

## Decision

Joe decided on 2026-10-19 that Freyja v1 has a **passive toe**: one hinge joint between the foot and a toe body, with a spring, a damper and hard stops at both ends, and no drive. It goes into the sheet and the model together with the standing-posture and segment-scaling changes, in one snapshot change, so that the full simulation suite runs once on the final snapshot.

The literature supports a passive element. In normal walking the metatarsophalangeal (MTP) joint absorbs net energy (peak about 1 W/kg absorbed; Matsumoto 2022) and its moment is small, 0.06 to 0.18 N m/kg across the studies below, 4 to 12 N m for a 65 kg body and about a tenth of the ankle's. Walking at 0.5 to 1.6 m/s needs no energy supplied at this joint.

**Design inputs for `rm.v1-toe-in-model`.** Each is tagged sourced, derived (my arithmetic on a sourced number) or open.

| Parameter | Value | Tag and source |
|---|---|---|
| Joint | one hinge, mediolateral axis, at the midpoint of the first and fifth metatarsal heads | sourced: Matsumoto 2022 defines the MTP joint there; the sheet gives the same landmarks as Dumas's foot endpoint. **Verify** (open item 1) |
| Extension range | 0 to 80 deg; hard stop at 0 (toe flat) and at 80 | sourced and derived: Nigro and Arch 2022 mean peak 54, 58, 65, 70 deg at 0.68, 1.03, 1.37, 1.71 m/s (SD 6 to 7); 80 is about the 1.71 m/s mean plus 1.5 SD |
| Peak moment to carry | 5.7, 7.7, 10.2, 12.8 N m at those speeds for 65 kg; 0.06 to 0.18 N m/kg across sources (4 to 12 N m) | sourced: Nigro and Arch 2022 (0.009 to 0.020 N m per body weight); the 2012 Int J Precis Eng Manuf study of 22 adults (0.13 +/- 0.04 N m/kg); Bruening and Takahashi (0.06 N m/kg, quoted secondhand in an exoskeleton paper, PMC8830714); Matsumoto 2022 (0.18 +/- 0.04) |
| Peak power absorbed | about 1.0 W/kg, 65 W for 65 kg, at 1.33 m/s | sourced: Matsumoto 2022 |
| Stiffness | **not fixed.** Sweep 0.1 to 0.7 N m/deg in the model; the upper end is the human early-rocker slope (0.45 to 0.70 N m/deg at 65 kg), the lower end reaches the human peak moment at full range | sourced slope, derived bracket: Nigro and Arch 2022. The human joint is spring-like only in the early rocker and its late-rocker slope is negative, so a linear spring at the early slope would reach about 38 N m at 65 deg, four times the human peak: copy nothing |
| Damping | **open**, set with the stiffness in simulation | no source |
| Toe mass | 14.4% of the foot mass, 0.094 kg of 0.650 kg | sourced and derived: Matsumoto 2022 (CT of one man, density 1.1 g/cm^3) times the sheet's foot mass |
| Toe centre of mass | 43.6% of the toe length from the hinge | sourced: Matsumoto 2022 |
| Toe length | about 70 mm (56 to 74 mm for a 245 mm foot) | derived and open: foot length is 1.3 times the heel to first metatarsal head distance (SD 0.04; Selected foot length ratios, Rev Int Cienc Podol), so the first head is at 77% and the toes are 23% of the foot; the midpoint of the first and fifth heads sits nearer 70%, giving up to 30%. The 245 mm foot length is my assumption |
| Toe inertia | of order 4e-5 kg m^2 about the hinge axis through its centre of mass (block 65 x 80 x 20 mm); replace with the CAD value | derived, rough |

**Rules the model change must keep.**

- The split conserves the whole foot: the toe and the remaining foot together reproduce the sheet's foot mass, centre of mass and inertia (parallel axis theorem) to 1e-9, with a mutation test. The sheet keeps Dumas's published foot row as the input and derives "foot without toe" and "toe" by formula.
- The dataset's foot is rigid and has no toe angle. In method A the toe is held at its flat angle (dataset-consistent). In B and H it moves passively. Both are reported.
- The polygon test is repeated with the toe's footprint, and the change attributed separately from the scaling and posture changes.
- The thread's coverage check requires the toe body to be bound to the foot segment and the toe hinge to a joint record, in the same commit.

**Open items before the model is built.**

1. **Foot geometry.** The sheet gives Dumas's foot length as 165 mm, ankle joint centre to the midpoint of the first and fifth metatarsal heads. If that is literal, heel to toe tip comes to about 290 mm with a 70 mm toe, against about 245 mm for the anatomical ratios. One of the two is wrong. Check Dumas's table, and the dataset's heel and toe-tip markers in the static trials, before the hinge position is fixed.
2. **Foot mass.** Confirm that Dumas's 0.650 kg includes the toes (the length is landmark-based, the mass may be whole-foot).
3. **Stiffness and damping** from the simulation sweep.
4. **A toe length** chosen in design, not left to the ratio above.

## Consequences

- The foot rows of Stage 2 reopen: the polygon test, the ankle lever and B and H run again, in the final regeneration of `rm.v1-stage2-closed`.
- The sheet gains a toe row, the derived foot row, a toe joint row (axis, range of motion) and body-position entries; the preprocessor and the template gain a toe body, a hinge and two new placeholders for stiffness and damping. `rm.v1-toe-in-model` makes these changes, which are listed in its brief.
- The hinge axis, its bearing and housing, and the stops are v1-final interfaces. No volume or mass is reserved for a later actuator. If a later version wants an actuated toe (running, jumping), the foot's interior has to be redesigned; walking does not need it.
- `rm.v1-toe-actuation` becomes the fabrication and bench qualification of the passive toe: spring, damper, stops and bearing, against the moment and range above.
- The toe does not reduce B's CoP offset and does not change A's loads beyond the mass redistribution; its effect is on the feasibility polygon, the ankle lever and the controller project's foot.

## Rejected options, and why each one died

**Chosen: passive toe** (a spring, a damper and stops on one hinge).

**No toe.** Rejected: the CoP is outside the contact polygon in 98% of single-support frames at 80 to 90% of stance at 1.4 m/s and in every double-support frame from 80%. The torque argument is gone, but a foot that cannot roll over its forefoot gives the controller project a foot that cannot walk like a person, and Joe has decided a toe goes in. Humanoid precedents add passive toes for the same reason: Sellaouti and colleagues (IROS 2006, doi 10.1109/IROS.2006.282449) report in simulation smoother walking up to 1.5 times faster on HRP-2, and a passive spring and damper toe on SURENA III (Robotica) reports ankle and knee energy reductions of 15.3% and 9.0%.

**Actuated toe.** Rejected: the MTP joint absorbs net energy in walking, the moment to carry is 4 to 13 N m, and a drive adds power electronics, mass and volume inside the slim-leg envelope for a demand the dataset cannot supply. Nothing in v1's scope (walking at 0.5 to 1.6 m/s) needs it.

## References

- Nigro L, Arch ES (2022). Metatarsophalangeal joint dynamic stiffness during toe rocker changes with walking speed. J Appl Biomech. doi 10.1123/jab.2021-0385.
- Matsumoto Y, Ogihara N, Hanawa H, Kokubun T, Kanemura N (2022). Novel multi-segment foot model incorporating plantar aponeurosis. Front Bioeng Biotechnol 10:894731. doi 10.3389/fbioe.2022.894731.
- Kinetic role of the metatarsophalangeal joint in normal walking: joint moment and power (2012). Int J Precis Eng Manuf 13(8):1481-1485.
- Sellaouti R, Stasse O, Kajita S, Yokoi K, Kheddar A (2006). Faster and smoother walking of humanoid HRP-2 with passive toe joints. IROS. doi 10.1109/IROS.2006.282449.
- Adding low-cost passive toe joints to the feet structure of SURENA III humanoid robot. Robotica (Cambridge).
- Selected foot length ratios in a non-pathological sample. Rev Int Cienc Podol.
