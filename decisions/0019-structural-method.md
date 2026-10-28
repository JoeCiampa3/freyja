---
id: adr-0019
status: accepted
date: 2026-10-28
links: []
---
## Context

This is the structural counterpart of 0009 (actuator sizing), which is not decided. v1's interfaces and load paths are final (0036), so an under-built segment cannot be thickened later without moving an interface. The method therefore has to be fixed before any segment's design is.

This record settles five things: the load statistic taken from a load envelope; the factors on yield and fatigue and how stress concentration is handled; the stiffness limits; whether verification is analysis alone or also a test on rm.v1-load-rig, and at what load; and how a requirement record becomes a structural spec. The Oct 2026 arm discussion proposed four inputs (static factor 2 on yield at peak stress including concentration under the actuator-peak case, fatigue factor 1.5, an advisory 1 mm at the hand, sizing to actuator peak rather than payload). They are adopted below where stated.

The load envelope (`sim/runs/ENVELOPE.md`) reports per joint the 95th percentile across subject-strides with the maximum beside it. It labels the acceptance speed "not for sizing" and says it is not a complete sizing basis. Which rows enter a segment's basis is for the load-basis records (0008 for the elbow and upper arm), not for this one. 0036 allows no credit for fall behaviour and leaves fall cases and their factors to 0037. The approach recorded on the sizing-method nodes is to lock a trusted demand and put the factor on top, never to lower the factor to cover a doubtful number.

Every number below carries a tag. **[design]** is a choice with no source behind it. **[source]** is a cited value. **[source needed]** has not been cited yet and is not to be relied on until it is.

## Decision

**D1 Design load.** A segment's design loads are a set of cases, each checked on its own and never netted against another.

(a) *Actuator-peak case, for static strength.* For every actuator j that acts across or is mounted on the segment, the segment carries the load that arises when j delivers T_pk,j at its output with the distal chain unable to move. T_pk,j is the peak output torque as 0009 defines it, read by address from that actuator's record once 0009 and the selection exist [source: 0009]. It is never typed here or in a spec. All actuators loading the segment are taken at T_pk together, with the signs that maximise stress at each section [design]. The reaction acts at the segment's distal interface unless its spec names another point [design]. The weight of the segment and everything distal acts at the orientation within ROM that maximises stress. The payload is not the sizing basis. It is a case like any other and governs only where it exceeds this one.

(b) *Envelope cases, for loads no actuator bounds and for all fatigue cycles.* Loads no actuator bounds are ground reaction through foot and shank, and trunk and head inertia. Static strength takes the envelope's maximum and fatigue takes its 95th percentile [design: the choice of statistic; source: the rows, Camargo et al. 2021 through the sim]. Only rows the segment's load-basis record accepts enter, and rows labelled not for sizing never do. Fatigue uses in-service cyclic loads (arm swing and payload cycling for the arms, walking cycles for the legs), not the actuator-peak case, which is a rare static event. If a drive can reach it routinely, for instance by striking a hard stop in normal operation, its cycles enter too.

(c) *Stumble and fall cases.* A stumble case governs the static strength of the legs and pelvis where it exceeds (a) and (b). Its magnitude is not set here. It is a load case (`lc.*`) with `independent_source_required: true`, taken from the independent bracket of 0037, with a working range of 3 to 5 times body weight [source needed]. Fall cases enter only as 0037 assigns them, with the factor and independent source 0037 gives.

*No credit for behaviour (0036).* T_pk,j is what the hardware can deliver. A firmware current limit, a controller torque limit, braking, bracing or unlocking reduces no load in any case.

**D2 Factors, life and stress concentration.**

*Static.* The factor on yield is 2 [design]. It is the specified minimum yield strength of the temper and product form [source: catalog stock entry, not yet entered], divided by the peak local von Mises stress including concentration, under the governing case of D1.

*Fatigue.* The factor is 1.5 [design] on the modified Goodman line with a load line through the origin [source: Shigley's, as the method; design: the choice]. The fatigue strength is the cited median S-N value at N cycles [source: catalog stock entry, not yet entered], reduced by surface, size and loading factors and by the reliability factor below. Aluminium has no endurance limit, so a life is part of the number. This method covers metallic members. Steel stressed below its endurance limit needs no N, and CFRP needs a method of its own before it is used.

*Working life.* 10 years, 8 powered hours a day, every day (29,200 powered hours), with 50% of powered time walking [design]. At about 115 steps per minute [source needed] a leg takes about 3,400 strides per walking hour. The cycle counts N follow:
- Thighs, shanks and feet: 5e7 [design, from the working life], once per stride.
- Pelvis, torso, head and neck: 1e8 [design, from the working life], once per step. Low load goes into the stress amplitude, never into a smaller N, because these segments are bounced every step.
- Arms, swing: 5e7, once per stride [design].
- Arms, payload lifts: 1e6 [design], from 200 lifts a day [design].

Each load block is checked against its own N. Where two blocks on one member both come within a factor of two of the limit, they are combined by Miner's rule, with the sum of n/N below 1.

*Reliability.* 99% for the legs (thigh, shank, foot) and pelvis, and 95% for the arms, torso, head and neck [design]. The factors are read from Shigley's reliability table [source] and cited in the stock entry. A 90% level is a fleet figure; across the five critical leg and pelvis members it leaves about a 41% chance that one falls short of the life.

*Concentration.* It enters one of two ways and never both. One is Kt from a cited chart for the actual feature, applied to the nominal stress. The other is the peak local stress from a mesh-converged FEA that models the real feature radius, with the convergence tolerance set in the study record. Stresses at singularities (sharp re-entrant corners, point loads, rigid constraints) are not read. For fatigue, Kf = Kt (notch sensitivity 1) unless a cited q for that material, temper and radius is entered [design].

The factors are not reduced for any behaviour (0036), and not lowered to make a result pass. Fall cases take 0037's factor instead.

**D3 Stiffness.** A limit is a deflection of a named point under a named case. An advisory limit is reported and blocks nothing. Both limits below are [design]. They are checked on the structure only: members and connectors carry real section stiffness, joints are rigid, and no controller compensation is credited. Joint compliance and backlash belong to the joint's own requirement.

*Arm.* The wrist interface (the forearm's distal interface) deflects no more than 1 mm, advisory. The chain is the upper-arm member plus the forearm member, with the shoulder, elbow and wrist joints rigid. The load is the design payload (1.0 kg at full extension, as 0008 records it) and the hand's reserved mass, applied through the wrist interface as a force and a moment, plus the arm's own weight, at the pose that maximises the deflection. 1 mm over the 0.515 m reach to the wrist is about 0.111 degrees. No member gets an authored fraction of the limit. Each member's spec carries the deflection and rotation at its distal interface that the chain model gives.

*Legs.* The thigh and the shank are separate segments for stiffness, with the measured points at the knee joint centre (KJC) and the ankle joint centre (AJC). A member's contribution is its distal translation plus its distal rotation times the lever to the ankle joint centre (the shank's length for the thigh, about zero for the shank), checked in the sagittal and frontal planes. Each member's contribution is at most 1 mm, so the total at the AJC is at most 2 mm, advisory. The load is the 95th percentile walking load at the 1.6 m/s sizing speed [source: envelope rows]. The stumble case is a strength case (D1c) and is not used here. The 2 mm is 0.25% of the 806 mm hip-to-ankle length, the same order as the arm's 0.19%. It has no source. The sim's sensitivity of foot-placement and stance-estimate error to compliance should replace it once a walking controller exists, and the limit stays advisory until then.

*Other segments.* No stiffness limit is set for the pelvis, torso, head or feet. The pelvis tilts both legs at once, so its contribution to the foot error is open.

**D4 Verification.** Every segment is verified by analysis against D1 to D3. A test on rm.v1-load-rig is also required for two things:
- the upper-arm member, as the Ariadne benchmark;
- the torso's harness hardpoints with their load path into the structure, because their failure releases the robot from the catch rig of 0036.

Every other segment is verified by analysis alone, on the condition that the benchmark's measured values agree with prediction within ±8% on deflection and ±10% on strain in uniform-stress regions [design]. Regions at a notch are excluded from the pass/fail. The band is provisional until the rig has an uncertainty budget, and it must not be tighter than the test's own noise. Outside the band, analysis-only is withdrawn for all untested segments until the cause is found and this record is amended.

*Test load.* The proof multiple is k = 1.25 [design]. The proof load is 1.25 times the segment's governing static load of D1, applied through the real load path in steps, with deflection and strain read at each step against prediction. The steps below proof are the benchmark's elastic points. At the factor limit the peak stress including concentration at proof is k/2 of yield, which is about 63%.

*Acceptance.* There must be no permanent set beyond the rig's calibrated resolution after unloading from proof, and the agreement above must hold, with the error recorded either way.

*Scope of the test.* It covers static strength and stiffness only. Fatigue is verified by analysis, and no fall behaviour is applied or claimed (0036). The largest proof load among tested segments sets the rig's capacity.

**D5 From requirement to spec.** A requirement record states a demand (value, unit, source, rationale) and carries no factor and no margin. The structural spec of a part is generated, not authored. It has one row per case and check, each resolved by address:
- the load, from a load case (`lc.*`), the actuator's record (T_pk,j) or the envelope row its load-basis record names;
- the interface (`if.*`) where it acts;
- the check (yield, fatigue or stiffness);
- the factor, from this record;
- the allowable, from the stock entry in `catalog/`.

Nothing in a row is typed, so a change to any source makes the spec stale through the thread's hash mechanism. A row that misses its factor is a finding with the measured number, and the factor is not adjusted. A row on a load case with `independent_source_required: true` is marked and is not closed on simulation magnitudes alone (0036). Where the generated spec is stored (a dossier section or an `fea/` study record) is settled with the first one, the upper arm's, in rm.v1-upper-arm-characterized. This record adds no record kind.

## Consequences

- D1(a) is abstract until 0009 is accepted and a segment's actuator is selected. No actuator-bearing segment's static check closes before then, and the upper arm also waits on 0008.
- Stock entries in `catalog/` need a minimum yield, an S-N value and the reliability factors, each cited, before the first check.
- k must stay below 2, or the no-permanent-set criterion contradicts the factor of 2.
- If leg members are ever tested, the stumble case at 1.25 times its magnitude would set the rig's capacity. The hardpoint proof load comes from the arrest load in rm.v1-trial-rig-concept.
- The choice among aluminium, steel and CFRP for the critical leg members is not made here. The D3 numbers decide it, and a CFRP member needs a fatigue method added to this record first.
- Open: the stumble magnitude (0037), the pelvis stiffness limit, and sources for the cadence and the 3 to 5 times body weight working range.
- v1 still makes no tested fall-survival claim (0036).
- Changing any factor means superseding this record.

## Rejected options, and why each one died

**D1.**
- *Sizing to the payload.* A stall, a jam or a hard-stop strike loads the structure at T_pk whatever it carries, so a payload-sized structure is sized to a case that cannot govern.
- *Crediting a controller or firmware torque limit.* That is credit for behaviour, which 0036 rules out.
- *The 95th percentile for static strength.* Yield is a single event, and one stride in twenty would exceed the design load.
- *The maximum for fatigue.* The statistic is the demand and the factor is the margin. The maximum on top of 1.5 stacks margin into the demand.

**D2.**
- *Ignoring Kt on static yield, as textbook practice allows for ductile material.* It relies on ductility the record cannot check for every temper, section and machined notch. A notch that yields in v1 cannot be cured later by thickening an interface.
- *Kt on top of an FEA peak stress.* That counts the concentration twice.
- *Lowering the factor to cover a doubtful load.* That is against the approach recorded on the sizing-method nodes.
- *Reliability at 90% (the L10 convention).* It is a fleet figure. There is one robot and no spare.
- *Setting N by how hard a segment works.* The low-load segments are bounced every step, so load belongs in the amplitude, not in N.

**D3.**
- *Counting joint compliance in the arm limit, or measuring at the hand's centre.* The wrist joint's compliance would enter, and the hand is a reserved claim in v1, so its structure doesn't exist yet.
- *Using the stumble load for the leg stiffness limit.* Foot-placement error comes from the loads seen every step, and a stumble is a strength case.
- *One limit for the whole leg.* The thigh and shank deflect separately, and the thigh's rotation is amplified by the shank's lever.
- *Making any limit blocking.* Both numbers are design choices with no source.

**D4.**
- *Analysis alone everywhere.* The benchmark needs a measurement, and a hardpoint failure drops the prototype.
- *Testing every segment.* The benchmark exists to say whether analysis can be trusted, so it conditions the other segments rather than being repeated on each.
- *Proof at k = 2.* That is the yield stress at the notch, which contradicts the permanent-set criterion.
- *A tighter agreement band.* It could withdraw analysis-only verification through test noise alone.

**D5.**
- *A new `structural_spec` record kind.* It needs a schema and CONVENTIONS change, and an authored spec would hold typed copies of values that exist elsewhere.
- *Factors written into requirement records.* That splits the factor across many files and mixes demand with margin.