---
id: adr-0008
status: accepted
date: 2026-10-31
links: [adr-0002, adr-0019, adr-0036, adr-0037, adr-0042]
---
## Context

This record closes rm.v1-elbow-load-basis. It decides which load cases size the elbow and the upper arm, from what sources, with what statistic, and how the fall case enters. Its output is an input to ADR 0009 (rm.v1-actuator-sizing-method): cases, sources, statistic. It sets no safety factor for actuator sizing; that is applied at design time and belongs to 0009.

State of play. ADR 0042 is accepted and v3 is the baseline sculpt: the arms are at the sheet's lengths (upper arm 255.2 mm, forearm 259.4 mm) with joint nodes on the section centre line, and the elbow node carries a 7 mm anteroposterior error bar (0042 D2). Stage 2 excluded arm swing, so the simulation envelope has no dynamic elbow rows. The first CAD part is the upper arm (elbow joint, its actuator, the upper-arm member). The shoulder architecture is open behind the v1 connector (rm.v1-shoulder-concept).

0036 and 0037 set the frame for the fall case. v1 reserves and does not carry (0037 D3: every call in v1 is reserve), credits no protective behaviour, and hands the arm's stroke home and cap to this record under D2(c) (0037 D3). 0037 D1(c) lets a geometric drop lower a zone's energy below E_max and bars sharing a two-handed arrest between the hands.

Sources and their limits. The BSIP rows were checked numerically against Dumas (notebook/2026-10-19-bsip-verification.md). That is a transcription check; it says nothing about whether human segment masses suit a robot. The rows summed to 96.9% and the residual is spread proportionally, so each mass is about 3% above its raw fraction. The forearm and hand masses are used here as budgets the hardware must hold, not as measurements. The static torques and swing inertias are closed-form from params/snapshot.csv. A simulation run reading the same snapshot would be circular and is not offered as validation (CONVENTIONS section 1). Joe does not trust actuator sizing derived from human gait data scaled onto Freyja, so D8 lists every place this record leans on human data.

Tags are as in 0019 and 0037: [source: ...], [design], [derived], [source needed].

## Decision

**D1 Cases.** Static gravity is in (D2). Arm swing is in as three provisional rows that do not govern (D3). The fall case is in as a structural, interface and stroke load that bypasses the actuator, never as an actuator torque (D5, D6). The elbow's range is fixed by D4.

**D2 Static gravity.** The elbow torque depends only on the forearm's orientation relative to gravity, so the maximum over all poses is the forearm horizontal, whatever the shoulder is doing. The statistic is the maximum over pose; there is no distribution.

Torque about the hinge, from the snapshot [source: params/snapshot.csv]:
- Forearm 0.845 kg, centre of mass 106.6 mm from the elbow: 0.88 N·m.
- Hand 0.325 kg, centre of mass 316.7 mm from the elbow (259.4 mm plus 57.3 mm): 1.01 N·m.
- Self-weight total: 1.89 N·m.

The payload sits at the hand's centre of mass, 316.7 mm from the elbow [design: the centre of mass stands in for the grip point; the v1 hand is a placeholder, rebuilt for v2]. Payloads are 1.0 kg design and 0.5 kg nominal at full extension [source: Joe's household task list, per the leaf; design]. The torque is 5.00 N·m at 1.0 kg (payload 3.11) and 3.45 N·m at 0.5 kg (payload 1.55).

Loaded arc. The payload torque is claimed across Morrey's functional arc [source needed: the leaf cites the arc; its bounds are not yet sourced here]. Outside the arc, up to the 157° of D4, only self-weight is claimed, 1.89 N·m. That is a claim, not a bound: the torque depends on forearm orientation, not elbow angle, so an elevated arm can put the loaded torque at any elbow angle, and the record accepts that the payload is not claimed there [design].

Error bar. The self-weight terms carry about 3% from the BSIP residual spread. The payload is a design input and has no error bar. The hardware masses are budgets: this case is valid only while the forearm holds 0.845 kg and the hand 0.325 kg, and a forearm or hand over budget reopens D2 (ADR 0002 rule 7 leaves the tolerance undecided).

**D3 Arm swing.** Swing torque is the inertia about the hinge times the peak angular acceleration, added to the static term at the same payload on the assumption that the forearm is near horizontal at the peak (a conservative sum). The profile is minimum jerk: peak velocity 1.875 A/T, peak acceleration 5.77 A/T² for amplitude A and time T [source: Flash and Hogan 1985 for the profile; constants derived]. Inertia about the hinge axis [derived: snapshot inertias, parallel-axis]: 0.046 kg·m² with no payload, 0.097 at 0.5 kg, 0.147 at 1.0 kg.

Durations, with each paper's onset and end definition:
- Schwarz 2022 [source: Table 3, Fig. 5B, p. 6; checked against the PDF]. 26 stroke and 5 healthy subjects pooled (N=31), seated, self-selected speed, hand IMU. Onset and end are 2% of peak hand speed. Gesture reaches to the head (T05, T07, T10) are about 85 to 100° in about 1 s. Grasp transports (T12 to T18) are about 50 to 100° in about 1 to 3 s. These are read by eye from boxplots whose time axis runs to 15 s, so times carry about ±0.3 to 0.4 s.
- Simon-Martinez 2018 [source: Table 1, hand to head 0.89 s; transcribed from the Code analysis of 2026-10-31, not re-checked against the PDF]. 59 healthy children aged 5 to 15. Boundaries are event-based (hand leaves the knee, hand contacts the target) with no velocity threshold. Elbow amplitude is by curve only, about 60° by eye.
- Magermans 2005 reports angles only, no timing.

No source gives a healthy-adult per-stroke elbow time with a numeric threshold, and none gives dispersion usable as a tail. Schwarz's 2% threshold makes a measured duration about 0.927 of the equivalent minimum-jerk duration, so using it as T overstates acceleration by about 16%, the conservative direction [derived]. Simon-Martinez cannot be corrected.

Rows (D7): S1 gesture, no payload, 90° in 1.0 s; S2 grasp transport at the design payload, 90° in 2.0 s; S3 conservative, design payload at gesture speed (no source supports this combination). Simon-Martinez's fastest stroke, 60° in 0.89 s, gives 1.1 N·m at the design payload, below S3. Swing equals the static 5.00 N·m at about 34 rad/s², which is T = 0.52 s for 90° or 0.42 s for 60°. Revisit trigger: a credible 90° elbow stroke under about 0.5 s.

**D4 Range.** The mechanism travels from 4.7° of extension [source: snapshot elbow_extension, Soucie] to 157° of flexion [source: Magermans 2005 Table 4, 95th percentile of maximum flexion in hair combing, 24 healthy women; transcribed from the Code analysis, not re-checked against the PDF]. The sheet's flexion row is 150° [source: snapshot elbow_flexion, Soucie], an anatomical ceiling; ADR 0002 rule 6 allows a functional target above it. The 157° is a sample percentile, not a bound.

**D5 Fall energy for the arm.** The arm zone ("hand and arm", 0037 D3) takes its design energy from the geometric-drop route of 0037 D1(c): the kinetic energy m g (h0 minus h at hand contact) of the body when one hand meets the floor, with no sharing between hands.

Model. A rigid body pivots about a point on the ground at the toe. Inputs:
- Mass 65 kg [source: target_mass].
- Standing centre of mass 0.942 m [derived: snapshot segment masses and centres, vertical stack, pelvis tilt ignored; replaces 0037's 0.935 m [design]].
- Shoulder joint at 1.347 m [source: snapshot].
- Reach from the shoulder to the contact point 0.515 m, the wrist [design: the v1 hand is a placeholder; reach to the end of the hand node, 0.589 m, lowers the energy by about 25 to 30 J].
- Toe hinge 0.128 m and toe tip 0.195 m ahead of the ankle [source: snapshot].
- Stack axis 0.09 to 0.195 m behind the pivot [design: not yet pinned from the snapshot's standing pose].

Pose family. The arm is straight at angle β from vertical in the fall plane with the hand on the floor. The family is bounded by the friction cone: the arm acts as a strut only while β ≤ arctan μ at the hand, with μ = 1.0 [design; no source; elastomer on common floors plausibly reaches or exceeds 1, so this is a design choice, not a bound; source needed], so β ≤ 45°. Beyond the cone the hand skids, the arm earns no credit, and the other zones keep E_max.

Results [derived]. Forward fall: arm straight down at contact 302 to 355 J; β = 27° (μ = 0.5) 331 to 380 J; β = 45° (μ = 1.0) 378 to 422 J. A lateral fall about the outer foot edge gives 238 to 331 J across the same cone, 65 to 105 J below the forward fall at the same angle, so it never governs the arm. The design energy is 422 J rounded to 430 J (0037 D3 rounds up to the next 10 J), against 320 J in 0037 D3. Gravity's work through the stroke adds about 6.4 J per centimetre of further centre-of-mass drop, at most about 29 J over 45 mm, and is covered by the 1.25 margin on stroke (0037 D2d).

Limits. The error bar is about ±6 J per 10 mm of drop from the pivot and stack assumptions, and the pivot bracket above is the stated spread. The model does not cover foot slip. A sliding fall is not constrained to the pivot's arc and can reach the same hand contact at a larger drop, up to E_max = 540 J (0037 D1b). So 430 J is the upper edge of the pivot model, not a bound on the arm's loading in a slipping fall. Energy above what the stroke absorbs reaches the end stop, the shoulder interface and the rest of the body, and v1 claims nothing about it (0036).

**D6 Fall cap, stroke home and load path.**

(a) Cap. F_cap = 20 kN [design], from the series 10, 20, 40 kN (0037 D2c). This is a design judgment, not the D2(c) result: 0037 D2(c) takes the lowest cap whose stroke fits room judged from data/envelope/, and no room has been extracted for the shoulder. 20 kN is the lowest cap for which a plausible arc exists.

(b) Stroke. s_res = 1.25 E / (η F_cap) at η = 0.6 (0037 D2a, D2d). For E = 430 J this is 45 mm at 20 kN (90 mm at 10 kN, 23 mm at 40 kN).

(c) Stroke home. The shoulder girdle, at the thorax-shoulder interface, as a compliant arc about the fixed (sternal) end of the clavicle. A forward fall moves the shoulder posteromedially (the ground pushes the hand up and back), a backward fall anteromedially. This record owns 45 mm in those two directions. The lateral fall's superomedial arc is the shoulder zone's own case (E_max, 57 mm at 20 kN) and belongs to 0037. Whether one guideway serves both is open to rm.v1-shoulder-concept. The arc is not confined to the human clavicle's range of motion, because it acts only in an unintended impact. The limit is geometry: the swept clearance, including the shoulder shell. As an illustration only, at a 0.16 m lever from the sternal pivot [design: no SC joint position in the repo] 45 mm is about 16°, 57 mm about 20°, and 90 mm (the 10 kN case) about 32°.

(d) The compliant element is generic. The requirement on it is η ≥ 0.6 over the reserved stroke and a force cap enforced at 20 kN, whatever the mechanism. A linear spring alone gives about η = 0.5 and returns energy to the body (0037 B9 hazard), so it is not the requirement.

(e) The shoulder actuator and drivetrain are not in the fall load path. The shoulder architecture is left to rm.v1-shoulder-concept.

(f) Elbow and upper arm. The elbow extension stop and the upper-arm column carry the cap as axial compression along the hand-to-shoulder line, rated 1.5 × 20 = 30 kN (0037 D4a), with the bearings bypassed by the stop faces (0037 D5 level 1) and given no credit. First-order check, not a design [derived, illustrative]: the column area is at least 30 kN / 240 MPa = 125 mm² [source needed: σ_y as 0037], which a 32 mm tube meets with about a 1.3 mm wall (the narrowest inner section of the upper arm is about 32.5 mm across at a 5 mm shell, a value that may move by about 0.1 mm with brief 11; no decision depends on it). Buckling, the stop faces and the couple are not sized here. At the 4.7° stop the hand-to-shoulder line misses the elbow by about 10 mm, so about 210 N·m at the cap and 320 N·m at the rating must be reacted across the stop faces. The first CAD part must carry that.

(g) An elbow slip element gives a torque cap, not a force cap [derived]. In the straight-arm strut pose the lever from the elbow to the force line goes to zero, so a slip torque never engages and the load goes into the stop. 0036 gives no credit for bracing, so the arm's pose at contact is not assumed. The elbow is therefore not the stroke home.

(h) Moment on the shoulder mounts. 0037 D3's illustrative case (10° off the force line over 0.515 m) gives about 1.3 kN·m at a 15 kN rating and about 2.7 kN·m at 30 kN. This is a requirement on the shoulder interface and is set when the shoulder concept exists.

(i) Mass claim. The hand-and-arm claim stays at the 40 kN element, 0.15 kg per unit (0037 D7). It is released to the 20 kN element, 0.10 kg per unit, only by a 0037 Revisions entry that cites the room, as D1(d) requires.

(j) Room check. No stroke room exists in `data/envelope/` for the shoulder (`reservations.yaml` has no entry). If 45 mm cannot be found, the arm cannot meet 0036's principle in the current envelope and needs a superseding record. If more room is found (about 90 mm), the cap could drop to 10 kN, which also needs a superseding record because caps are frozen (0037 D1d).

**D7 What ADR 0009 receives.** The fall case does not size the actuator. It sizes the stop, the column, the interfaces and the stroke requirement.

| Case | Basis | Elbow demand | Peak speed | Status |
|---|---|---|---|---|
| Static, design payload | forearm horizontal, 1.0 kg at hand centre of mass | 5.00 N·m | 0 | maximum over pose; payload is design |
| Static, nominal payload | 0.5 kg | 3.45 N·m | 0 | as above |
| Static, outside loaded arc | self-weight only | 1.89 N·m | 0 | claim, not bound |
| Swing S1: gesture, no payload | 90° in 1.0 s | 0.42 N·m inertial, 2.3 with self-weight | 2.95 rad/s | provisional |
| Swing S2: grasp transport, 1.0 kg | 90° in 2.0 s | 0.33 inertial, 5.3 with static | 1.47 rad/s | provisional |
| Swing S3: 1.0 kg at gesture speed | 90° in 1.0 s | 1.33 inertial, 6.3 with static | 2.95 rad/s | provisional; no source for this combination |
| Fall | 430 J, one arm, μ = 1.0 cone | no actuator load; stop and column 30 kN axial | none | D5, D6 |

Statistic. Static: maximum over pose. Fall: maximum over a bounded pose family, stated as a band with its design edge. Swing: no statistic; provisional rows from means, no tail source. The statistic over the swing tail, the safety factor, duty cycle and thermal sizing belong to ADR 0009.

**D8 Where this record leans on human data, and what it costs.**
- D2: BSIP masses and centres of mass, human and scaled, used as budgets. If the hardware is heavier or its centre of mass is further out, torque rises roughly in proportion. The budget holds or D2 reopens. The payload is design, not human data.
- D3: comfortable-speed ADL timings from stroke patients and children. They are not a bound on the speed Freyja needs. The record claims only that swing is small next to gravity at these timescales. A faster requirement is a design choice for 0009, and the break-even above is the trigger.
- D4: Magermans (24 women) and Soucie are population values used as ceilings for a mechanism. Movement beyond them is not covered.
- D5, D6: no human data in the demand. Energy comes from mechanics and μ is [design]. The human fall rows in data/falls/sources.md calibrate only and lower nothing here.

**D9 Left to later records.**
- ADR 0009: safety factor, swing statistic, duty cycle, thermal sizing.
- rm.v1-shoulder-concept: the shoulder architecture, the compliant-element mechanism, the sternal pivot position, the stroke room check and the mount moment rating.
- The wrist, pronation and supination, upper-arm structural sizing under 0019, and the cable path.
- 0037 D1(d) Revisions entries: the arm's energy basis and, when the room is cited, the first cap.

## Consequences

- The arm's interfaces and the elbow stop and column are rated to 30 kN axial (0037 D4a) from now on. Moment ratings follow the shoulder concept and the upper-arm design. The first CAD part is sized to these.
- rm.v1-fall-load-cases stays a blocker of rm.v1-upper-arm-characterized (0037). The load cases lc.fall-* are created there, not here.
- Quantities in the upper-arm characterization file that derive from the elbow node's position carry 0042 D2's 7 mm anteroposterior bar. The torques here use the sheet's lengths and the snapshot's centres, not the sculpt's node positions, so they do not inherit it.
- Nothing here depends on envelope volumes, so brief 11's raster-grid change (about 0.1 mm) leaves every decision intact.
- The stroke requirement lands on the thorax-shoulder interface and is a prose volume reservation until rm.v1-thread-budgets exists (0036).
- 0037's arm energy of 320 J is superseded in practice by D5 once a Revisions entry is made. Until then the two numbers coexist and this record governs the arm.
- The record states what it cannot cover: a slipping fall, a swing faster than the sources, and any loaded pose outside the arc.
- No tested claim is made: the fall case is a reservation and a rating (0036).

## Rejected options, and why each one died

- *Literature contact forces as the arm demand.* They describe other bodies and skins (0037 D1).
- *Sharing the arrest between two arms.* One arm can land first or alone, and 0036 forbids crediting behaviour. The band is a single-arm number.
- *Sizing the arm to E_max.* The arm supplies cap times stroke; the rest of the energy goes to other zones, which keep E_max.
- *An unbounded pose family.* The maximum runs to E_max.
- *Pivoting about the ankle.* It rotates a flat foot into the floor; the pivot is at the toe on the ground.
- *An elbow slip element as stroke home.* It caps torque, not force, and the lever vanishes in the straight-arm strut pose (D6g).
- *A radial skin layer on the forearm or hand.* The forearm's skin radius is 16.25 mm at the wrist and its sheet mass already needs about 1.99 kg/l averaged over the inner volume at a 5 mm shell, about 74% of solid aluminium, so there is no spare volume for a stroke.
- *Linear springs along the clavicle, specified.* Mechanism-generic with η ≥ 0.6 instead (D6d).
- *Carrying the cap through the elbow bearings.* A 40 to 47 mm deep-groove bearing has a static rating in the mid single-digit kN [source needed: catalog] against a 20 kN cap.
- *Setting the cap by D2(c) room-first.* No room has been extracted; the cap is a stated design judgment with the room check outstanding (D6j).
- *Claiming the payload torque across the whole 157° range.* Simpler, but the claim beyond Morrey's arc has no source. Self-weight only is claimed there.
- *Taking Schwarz's dataset to split healthy from stroke.* Five subjects, mean age about 63, non-dominant arm, no speed instruction, and the published rows are per-task means that include holds and returns. A noisier mean, still no tail.
- *Treating swing as governing.* At the sourced timescales it is 7 to 27% of the static term.
