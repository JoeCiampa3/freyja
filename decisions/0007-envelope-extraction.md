---
id: adr-0007
status: accepted
date: 2026-10-26
links: []
---
## Context

Volume-extractor briefs 1 to 6 (memos 27 to 36) built a way to take the available volume inside the body from a MakeHuman sculpt, registered to the sheet's joint centres, and to ask the oracle whether a
part fits. This record proposes the rules that work rests on, so that `rm.v1-volume-extracted` can later be signed off against them. It is drafted from Joe's decision list; it is not accepted. Every number
below is copied from the memo or file named beside it.

**Sources and what each is allowed to do.**
- The sheet (Dumas 2007 through the sheet; `params/snapshot.csv`) gives the dimensions and masses: HJC 871.07 mm, KJC 472.99 mm, ankle height 65.45 mm (memo 28), the pelvis and abdomen masses 9.490 and 2.665 kg,
  the thorax 17.095 kg, the head and neck 4.355 kg, a total of 64.935 kg (memos 33, 35, 36).
- The v2 sculpt `data/makehuman/freyja-body-v2.obj` (memo 32): unposed, 13,380 body vertices, the same topology as MakeHuman's `base.obj` body (13,378 faces in the same order; memo 30 for v1, memo 35 for the
  trunk bodies). Its volume is 52.3315 l computed against 52.3331 l in Blender, -0.003% (memo 32).
- ANSUR II (`data/ansur2/ratios.json`, memo 28): landmark height ratios and their SDs, used for the mesh nodes that nothing in the mesh stands for, and as a cross-check.
- Other literature entered the mass base and the realism checks only: Dumas 2015 Table 1 (the abdomen and thorax landmarks, `data/envelope/dumas2015_table1_female.json`), Dumas 2007 section 2.1 (the
  1 g/cm3 uniform-density statement, memo 33), Siri 1956, Deurenberg 1991 (body fat 0.207 at age 22) and Hall 2021 (lung gas 2.787 l, FRC) in `data/envelope/body_density.json` (memos 29, 30), Winter's
  densities (`reference_densities.json`).

**What the work found.**
- Registration (memos 28, 30, 32): the knee anchor settled on the Ruler chords; on v1 the legs needed +6.8% / -6.7% / +0.07% (thigh / shank / foot), on v2 0.9914 / 1.0007 / 0.9997 against the 8% gate (memo 32).
  The thigh volume range was 9.9% against a 10% limit with the wider knee SD (memo 30). The hip diagnostic against Dumas 2007 Table 1B GT (+8 mm times the pelvis scale 1.05035, 8.403 mm) leaves a residual of
  +3.01 mm with a 10 mm flag (memo 34).
- The trunk (memos 34, 35): the CJC from the ANSUR cervicale less the Dumas C7 offset (29.4 mm) gives a thorax stretch of 1.0038 and a head and neck stretch of 0.9754, with the head and neck at the sheet's
  length. The Monte Carlo 95% ranges are 0.898 to 1.147 (thorax) and 0.909 to 1.068 (head) on that anchor, 0.23 and 0.10 of draws beyond 8%: "only known to about +-4%" (memo 34, section 3). Closure of the
  conformed bodies and the remainder against the mesh volume is -0.389% against a gate of 0.5% (memo 36, after the SJC patch; -0.392% in memo 35).
- The mass base (memos 29, 30, 32, 33, 36): sculpt mass 52.10 kg at BMI 18.05 (f = 0.207, lung gas out); the whole-body average density the sheet requires is 1.241 kg/l over the mesh volume (robot basis) and
  1.311 kg/l over the volume less lung gas (tissue basis) (memo 36). The abdomen + pelvis pair needs 1.218 kg/l over its skin volume, 9.982 l for 12.155 kg (memo 35); the pelvis (1.715) and the abdomen (0.599)
  alone are not results, because the frame planes are not the Dumas mass cuts (memo 35).
- The realism finding (memo 33): on the uniform-density basis the sculpt carries 9.0% less volume share than the sheet's mass share in the abdomen + pelvis + thighs region (raw ratio 1.099, MSR10 to KJC
  planes), 4.8% more in the shank (0.954) and 8.0% more in the foot (0.926). The reference subjects behind the sheet's shares averaged 63.9 kg and 1.61 m (BMI 24.7), the sculpt 18.05 at 1.699 m. Memo 33
  (section 4) reports the comparison as context and draws no inference; D7 below does.
- The oracle (memos 35, 36): bodies and joint zones with h = 25 mm; the shoulder plane and spheres from the sheet's SJC (192.33 mm lateral, 77.57 mm below the CJC); a component registry, `check`, `free` and
  `foreign` on the MuJoCo model; the thigh's three-component worked example (skin 6.4198 l, free 5.6516 l, occupied 0.7682 l).
- A gap: no Stage 4 document or ADR exists to align the registry's `id` and pose fields with (memo 36, finding 3).
- The arms and reservations (memo 39, brief 8): each arm segment is registered by a rigid rotation about its proximal joint centre and an axial stretch; the arms are built (the upper arm with the shoulder
  girdle) and the closure has no remainder, +0.333% against the 0.5% gate. The spine modules of `data/envelope/reservations.yaml` fit the pelvis and the thorax and not the abdomen.

## Decision

D1. **Authority.** The sheet (Dumas via the sheet) sets every dimension and mass. The v2 sculpt (`data/makehuman/freyja-body-v2.obj`, unposed, 13,380 body vertices, topology identical to `base.obj`'s body)
supplies shape only. ANSUR II (already in `data/`) only places mesh features and cross-checks. No other source.

D2. **Registration.** Piecewise axial stretch onto the sheet's joint-centre nodes, never a uniform scale; cross-sections unchanged. Legs get a horizontal shear, arms a rigid rotation per segment about its
proximal joint centre onto the model's zero-pose axis (the mesh is in an A-pose: the upper arm 43.2 deg and the forearm 56.2 deg from vertical; a shear would inflate sections by 1/cos of the angle), then an
axial stretch; the hand takes the forearm's rotation and no stretch, and is the whole hand (the sheet's 74.6 mm is the SCS length). An 8% stretch gate per leg and trunk sub-segment; **the arm gate is
2 x sigma / sheet length with sigma = 17.3 mm (the knee anchor SD, a stated assumption set before the result: 13.6% for the upper arm, 13.3% for the forearm).** The arm result: upper arm 1.1244, forearm 1.1198, so
the sculpt's arms are about 11% shorter than the sheet's (the forearm 8% shorter than the ANSUR II radiale-stylion length scaled to stature); the nodes are the Ruler chord vertices (the SJC the sheet's, through
the trunk registration), on or near the skin, so an arm segment's axis runs near its lateral surface. The elbow is cut on the bisector plane of the two axes (a cell goes to one body); an optional later
re-sculpt of the arm-length sliders would remove the stretch (memo 39). Anchors: knee chords; hip crotch apex + ANSUR (Dumas GT +8 mm check); CJC ANSUR cervicale less the Dumas C7 offset; ankle on the ANSUR malleolus ratio (unmeasured); trunk map slope 1; head
and neck keeps the sheet length.

D3. **Uncertainty.** Anchor SDs from ANSUR; Monte Carlo N = 200; results reported nominal and robust; volume range gate 10%. The thorax and head stretches are known to about +-4%.

D4. **Available volume.** Signed distance to the skin on a 2 mm grid. The inner envelope is the skin offset by the shell thickness t, a design parameter (default 5 mm; the sheet has none). Margins under one voxel
are "marginal".

D5. **Bodies.** Frame cuts at joint-centre planes (horizontal in the zero pose for the trunk, normal to the axis for limbs). A plane is accounting: hardware may straddle it. Neutral-pose containment uses the
union of adjacent bodies; ROM interference belongs to the sim. Joint zones (hip, LSJ, TJC, CJC, shoulder; h = 25 mm) are owned jointly.

D6. **Mass cuts.** Realism checks use the source's tissue boundaries (Dumas 2015 Table 1: MSR10, iliocristale) and the uniform-density reading (Dumas 2007 section 2.1: sheet masses are volume shares). The
results are the lumped abdomen-to-thigh region, the shank and the foot (later segments with two known cuts); the pelvis, abdomen and thigh alone are not results. Abdomen + pelvis share one budget (12.155 kg).

D7. **Observation.** Against the reference women (63.9 kg, 1.61 m, BMI 24.7) the sculpt (BMI 18) carries about 9% less volume share than the sheet's mass share in the lumped abdomen-to-thigh region (raw ratio
1.103 on the frame bodies, 1.099 on memo 33's MSR10 region); with all segments in, the thorax is the other way (0.873), the whole arm 1.054, the shank 0.957 and the foot 0.929. One hypothesis, not tested: the
sculpt is lean against a BMI 24.7 reference, so its soft tissue is thinner where the reference's is thickest. No re-sculpt; revisit with all segments (they are in, memo 39).

D8. **Mass base.** Siri 1956 density, fat fraction 0.207 (Deurenberg), lung gas removed (Hall). Comparators: 1.24 kg/l (robot, skin volume) and 1.31 kg/l (tissue basis).

D9. **Oracle and registry.** A component registry per segment; `check`, `free`, `foreign`. Model body frames everywhere (pelvis origin at the LSJ), the mesh-to-model trunk shift a named design parameter. Foreign
parts from MuJoCo forward kinematics. Fine fits belong to CAD.

D10. **Gates.** Topology and watertight; stretch within 8%; area change within 1%; synthetic solids within 2 mm; the oracle examples; volume against Blender and closure within 0.5%.

D11. **Open.** The left side, discrete hip sweeps, single sculpt, no structural check; **the trunk's x offset** (the model's zero-pose stack is 56.7 mm behind the hip line, 38.6 mm behind the mesh thorax's centre
line at the CJC, and 52 mm behind the column that fits best, the corridor sweep's d = -5 mm; the design stance brings it to 30 mm; memos 37 and 39), **the hip registration** (the mesh's hip joint centres are 75.6 mm from its midline, the sheet's 92.43 mm: in the
model frames the two bodies are 17 mm apart at the hip plane; memo 39); the arms are built and the reservations reported (memo 39); the elbow and wrist nodes are still on the skin and open, and the forearm frame's roll is 16.5 degrees from the mesh's anterior (memo 43); both are decided in rm.v1-arm-joint-anchors-decision.

## Consequences

- The envelope is advisory geometry: it says whether a part fits the sculpt registered to the sheet, with the margin and the confidence the oracle reports, and nothing about strength or fatigue (D11).
- A change to a sheet dimension or mass moves the envelope (D1, D2): the registry and every free-space ledger carry the inputs hash that makes a stale result visible.
- The realism finding (D7) stays attached to every volume-share claim: hardware designed to the envelope fits a body that is about 9% lighter in the abdomen-to-thigh region than the sheet's reference subjects,
  until all segments are in and the question is revisited.
- Stage 4 components are placed in the model body frames (D9); `docs/envelope-component-contract.md` is the draft of what the connector would emit. The trunk's mesh-to-model shift is computed at build time and
  printed in every trunk result, not typed.
- The open list (D11) is the work not done: the left side, continuous hip sweeps in place of discrete ones, a second sculpt, any structural check, the trunk's x offset and the hip registration.
- `rm.v1-volume-extracted` stays pending until this record is accepted.

## Rejected options, and why each one died

Taken from the decision list and the memos, not new: a uniform scale of the whole body (D2: the sheet sets lengths, the sculpt sets cross-sections); a re-sculpt to close the 9% (D7: no, revisit with all segments);
reading the pelvis, abdomen or thigh alone as a mass result (D6: the frame planes are not the Dumas mass cuts, memo 35); a CJC taken from the brief's anchor (memo 34: 0.62 and 0.89 of draws beyond 8%, against 0.23
and 0.10 for the cervicale).
