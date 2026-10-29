---
id: adr-0037
status: accepted
date: 2026-10-28
links: [adr-0036, adr-0019, adr-0007]
---
## Context

0036 fixed the protocol (nothing but the feet touch the floor in v1 trials) and the principle (every segment carries its governing fall case or reserves the mass and space to carry it later without moving an interface). It left the magnitudes, factors and reservations to this record. 0019 defers two more things here: the stumble magnitude (D1c, working range 3 to 5 times body weight, [source needed]) and the factor on fall cases (D2). Interfaces and load paths are final in v1, so the cost this record guards against is an interface or load path that cannot take a fall load later.

The literature bracket (`data/falls/sources.md`, 34 rows) does not supply a demand, and verifying its rows has not changed that:
- Every rigid-floor hip force in it is a rigid floor under a compliant body. S10's model is a single spring of 71 kN/m: its 9.99 kN point-mass bound is that spring compressed about 141 mm, and its realistic variant (3C, 2.90 to 4.26 kN) compresses it 41 to 60 mm. S1 runs through 9 to 50 mm of trochanteric soft tissue and S11 through 31 to 34 mm of surrogate gel. The force in each row is a property of that layer.
- The hand numbers are placed no better. F1 is 2.4 cm foam with the arms pre-positioned to arrest. F4 is a lumped-parameter model extrapolated about 40 times beyond its 5 cm tests.
- Knee, trunk, back, elbow, upper arm, shank and foot have no source at all, and the head has only dummy contact force.

Freyja's contact force will be set by her own skin stiffness and stroke, and neither exists in v1. What does transfer across bodies is energy. The kinetic energy a 65 kg body has when a zone meets the floor depends on its mass and geometry, not on what the contact is made of. Force then follows from the stroke that absorbs that energy. This record sizes by energy and stroke and uses the literature only to calibrate.

The v1 envelope is the skin surface of the MakeHuman mesh, and the inner envelope is the skin offset by a shell thickness (5 mm default) [source: 0007 D4]. A compliant layer sits between the skin and the shell, so every millimetre of linear stroke comes out of the radius the structure has, one for one. An angular stroke at a joint (D2a) comes out of joint range instead.

Tags are as in 0019. BW = 65 kg × 9.81 = 638 N [source: target_mass, snapshot].

## Decision

**D1 What a fall case is.**

(a) A fall case is a load case `lc.fall-<slug>`, created as proposed by rm.v1-fall-load-cases. It is defined by a zone, a direction, a design energy E (J) and, where one is needed, a contact velocity or effective mass. Its force is not an input. It is the output of D2.

(b) *Energy bound.* No single zone can receive more than the energy the whole body loses falling from standing to the end of the stroke:

E_max = m g (h_standing − h_end), with m = 65 kg [source: target_mass], the centre of mass at 0.55 × 1.70 m = 0.935 m standing [design: replace with the thread's centre of mass] and h_end = 0.10 to 0.20 m [design].

h_end is the centre-of-mass height when the stroke is used up, not at first contact, so gravity's work during the stroke is inside the bound. The 0.10 m lower edge holds for any stroke that leaves the centre of mass at least 0.10 m above the floor. The bound assumes no actuator adds energy during the fall. The range is 469 to 532 J, and the design value is its upper edge rounded up: 540 J.

This is energy conservation. It holds for any floor, any skin and any later version, and needs no simulation and no literature. Leg buckling and bracing lower the real energy and get no credit (0036). [design: the credit rule; the bound itself is mechanics]

(c) *Design energy per zone.* E_design = E_max for every zone unless one of the following lowers it. Whichever is used is stated as a number in the case record.
- *A geometric drop.* The centre of mass falls less before that zone's stroke is used up.
- *Freyja's own effective mass, for a reservation only.* m_eff is taken at the contact from the mass matrix with all joints welded, and the contact velocity v_n from the rigid-body fall: E_design = min(E_max, ½ m_eff v_n² + m g s_res). Welding the joints gives the largest m_eff, so no behaviour is credited. These are configuration-space mass properties, not soft-contact magnitudes, so 0036's limit on simulation does not bar them.
- *A Verified row of `data/falls/sources.md`, for a reservation only.* An abstract-level, excerpt or secondary row may cross-check and lowers nothing.

No energy is partitioned between zones or between limbs without a verified source. In particular, a two-handed arrest gets no sharing between hands, because one arm can land first or alone (S4 is a one-arm impact). The sim may rank which zone lands first and may set no soft-contact quantity (0036).

(d) *Zones and scenarios.* The D3 table is the current list. Each zone's cap, housing segment, mass claim and reserved stroke or range are frozen for v1 and change only by a superseding record. Everything else in the table is open to amendment: adding a zone or scenario, changing an energy basis, changing a drop height. An amendment is a dated entry under Revisions and is valid if it loads no interface in a direction D4a has not already rated, leaves every set cap unchanged, and fits its stroke inside what is already reserved in the housing segment. A change that fails any of the three needs a superseding record, and reopens only the roadmap nodes that read the quantity it changes.

The one exception is a zone's first cap. A zone that has no cap yet may take one by a Revisions entry if the value is in the D2(c) series, is the lowest value whose s_res fits the room the entry cites from `data/envelope/`, and only releases claimed mass: the zone's claim drops from the 40 kN element to the element at the new cap (D7) and never grows. Once set, the cap is frozen like any other.

**D2 Cap and stroke.**

(a) *The pair.* A zone absorbs E over a reserved stroke against a cap:
- For a linear stroke, s = E / (η F_cap).
- For an angular stroke at a joint, Δθ = E / (η T_cap), with T_cap a passive slip or yield torque (D5).

η is the absorber's efficiency, 1.0 for an ideal constant-force absorber. η = 0.6 [design] is a requirement on the absorber a later version fits, not a property of any material. The later part must meet it inside the reserved stroke, and it is checked against it when it exists.

The cap is the force or torque the zone's load path is designed to see, and its interfaces are rated to it (D4a). A linear stroke takes radius from the structure. An angular stroke takes joint range: the reservation is Δθ of travel beyond the pose at contact, inside the joint's mechanical range.

(b) *No stroke.* Without a stroke, the force is set by the stiffness of whatever touches the floor. For a linear contact of stiffness k and effective mass m_eff at velocity v, F = v √(k m_eff) over a deflection x = v √(m_eff / k). For m_eff = 30 kg and v = 3 m/s (135 J) [design, illustrative]:

| contact stiffness k | peak force | deflection |
|---|---|---|
| 7.1e4 N/m (S10's hip soft tissue) | 4.4 kN | 62 mm |
| 1e6 N/m | 16 kN | 16 mm |
| 1e7 N/m | 52 kN | 5.2 mm |
| 1e8 N/m (rigid shell on a hard floor) | 164 kN | 1.6 mm |

The first row reproduces the literature's hip range: the 3 to 6 kN in the sources is what tens of millimetres of human tissue give. A rigid structure has no stroke to speak of, so its force is set by a stiffness nobody has designed. Bottoming out is a cliff: past the stroke, force jumps to the structure's own stiffness. The margin therefore goes on the stroke (d).

(c) *Choosing the cap.* For a linear zone, F_cap is the lowest value in the series 10, 20, 40 kN [design] whose s_res fits the radial depth the zone's structure can spare, judged from `data/envelope/`. The load path from the contact to the zone's interfaces is rated to that cap (D4a).

Raising the cap is cheap at a flange (D7) but not along the load path. Everything between the contact and the zone's bulk mass sees about F_cap, so a 40 kN cap puts 60 kN of rating through the pelvis box, not only through a bolt pattern.

A zone whose room is not yet known has no cap. Its interfaces and load path cannot be finalized until it has one, and its mass claim stays at the 40 kN element (D7). If no cap in the series fits, the zone cannot meet 0036's principle and needs a superseding record that says so. An angular zone's T_cap and Δθ are set by the record that designs the joint, under the same margins.

(d) *Margin.* Static strength only, once. The factor is n = 1.5 on yield, on the peak local stress including concentration, at the cap [design: below 0019's 2 because the cap is an upper edge the absorber enforces and the event is single]. The reserved stroke is s_res = 1.25 s, or 1.25 Δθ [design]. Bearings are checked against the static rating C0 with s0 = 1.0 [design]; C0 already carries ISO 76's small permanent deformation [source needed, cite in the catalog entry]. Yield strength comes from the catalog stock entry [source needed].

(e) *One budget, several mechanisms.* E_design is the energy a zone must dissipate, whatever dissipates it. Passive linear stroke, passive angular stroke and, in a later version, protective behaviour (bracing with the arms, yielding the spine, crouching before contact) all draw on the same E. The zone's E_design, less what behaviour removes before contact, must not exceed Σ η_i × cap_i × stroke_i over the mechanisms acting on the zone.

v1 credits only passive elements with stated characteristics (0036). A later version credits behaviour by a superseding record, and the reserved stroke then shrinks or the cap drops. Stroke is a parameter that versions tune against behaviour, not a fixed allocation.

Behaviour moves energy between zones as well as removing it. In B9, a simulated controlled backward fall struck the hip harder than an uncontrolled one. A record that credits behaviour therefore re-checks every zone it routes energy into. Energy an actuator absorbs is returned to the bus (Consequences).

**D3 Zones, energy, stroke and calls.**

Energies are E_design (D1c), rounded up to the next 10 J. s_res = 1.25 E / (η F_cap) at η = 0.6, rounded up to the next millimetre. "Room known" is from `data/envelope/` and is open where no envelope file exists yet. Every call in v1 is reserve: no compliant part exists, so no zone has a stroke and none carries (D2b, D5).

| Zone | Scenario | Energy basis [design] | E_design | s_res at 10 / 20 / 40 kN | Room known | Housed in (units) | Call |
|---|---|---|---|---|---|---|---|
| hip | lateral, hip first | E_max | 540 J | 113 / 57 / 29 mm | hip zone (top 40 mm of thigh) 81.25 mm radius, which also holds the hip mechanism [`thigh_R.yaml`]; pelvis envelope not extracted | pelvis (2) | reserve; cap by D2(c) when the pelvis room is known |
| shoulder | lateral, shoulder first | E_max | 540 J | 113 / 57 / 29 mm | not extracted | thorax (2) | reserve; as hip |
| buttock | backward, buttock first | E_max | 540 J | 113 / 57 / 29 mm | not extracted | pelvis (1) | reserve; as hip |
| back | backward, back first | E_max | 540 J | 113 / 57 / 29 mm | not extracted | thorax (1) | reserve; as hip |
| knee | forward collapse onto one knee | centre of mass drops 0.40 m | 260 J | 55 / 28 / 14 mm | thigh 41.73 mm inside the shell outside the hip zone; knee region not extracted; no stroke along the shin at its bottleneck (D4b) | thigh (2) | reserve |
| hand and arm | arrest on one arm, forward or sideways; no sharing (D1c) | centre of mass drops 0.50 m | 320 J | 67 / 34 / 17 mm if linear | no forearm or hand envelope file; an angular stroke takes elbow or shoulder range instead | upper_arm (2) | reserve; stroke home and cap set by rm.v1-elbow-load-basis (below) |
| head and neck | any | rotational, not an energy-stroke problem | open | open | | — | none for v1; neck interface open (D4a) |
| foot | none | the foot is the only part allowed on the floor | | | | — | not by a fall case; stumble (0019 D1c) |

The hip is where D2(c) has teeth. At 20 kN it needs 57 mm from an 81 mm radius that also holds the hip mechanism. At 40 kN it needs 29 mm, with 60 kN of rating through the pelvis box. Which cap it takes waits on the pelvis envelope. The table exists to show which zones cannot be protected rigidly, and how much volume or range the later skin and joints have to be allowed.

*Calibration, hip.* S1 (Verified) gives effective masses of 31 kg relaxed and 37.6 kg active for its female subjects, free-falling at 3.7 m/s from a 0.7 m pelvis height with no arm or knee contact. That is 212 to 257 J. S11 (Verified) ran its cadaver rig at 107 and 163 J. Both sit well below 540 J, and D1(c) would let them lower the hip reservation. The hip nevertheless keeps E_max until Freyja's own m_eff at the trochanter exists (D1c): S1's effective mass rises with muscle activity, and a welded robot is stiffer than an active human. S5 cannot calibrate the hip because its mat stiffness and stroke are not reported.

*Calibration, arm.* F1 (Verified) is 840 N per hand on 2.4 cm foam, at a wrist velocity of 2.45 to 2.66 m/s. If the foam's thickness is taken as the stroke, that implies 12 to 20 J absorbed in the first peak at η between 0.6 and 1.0, and an effective mass of about 3.5 to 6.5 kg [derived, not read from the paper]. That is the hand and forearm, a small fraction of the arm's 320 J. F4 (Verified, model), at a 0.75 m descent, puts 58 J through the wrist over 4.1 cm and 277 J through the shoulder over 27.2 cm, about 1 kN on average. A human arm arrests the trunk over a long travel at a low force. A locked arm on a rigid placeholder hand has none of that travel, and the extension stop is a lock, not a stroke.

*Where the arm's stroke can go.* Two constraints narrow it:
- A high cap is not cheap on the arm, because the load path reaches the shoulder through a lever. At 10° off the force line over 0.515 m [design, illustrative], a 10 kN cap rated at 1.5 puts about 1.3 kN·m on a shoulder that does not slip, against 6.45 N·m in the sweep row.
- A low cap needs more linear stroke than a forearm or a hand is likely to spare: 67 mm at 10 kN, and more below it, though no envelope file exists yet to confirm.

rm.v1-elbow-load-basis therefore names the arm's stroke home and sets its cap under D2(c). The candidates are the v2 hand's envelope (linear; the hand is rebuilt for v2, so its envelope is the cheapest place to reserve) and a passive slip element at the elbow or shoulder (angular; credited under D5). A slip at the shoulder takes only the part of the load off the arm's axis, while elbow flexion shortens the hand-to-shoulder distance itself. Together the two constraints point toward an angular stroke, and the elbow load basis decides.

**D4 Interfaces and wall room.**

(a) Every final interface a fall case loads (wrist, neck, shoulder mounts, hip mounts, knee, ankle, harness hardpoints) is rated to 1.5 × its zone's cap in each direction the case loads it, whatever the segment's call. The load path behind it is rated with it (D2c). An interface cannot be grown later (0036). Interface records carry the rated overload force and moment per direction.

Until a zone has a cap, its interfaces are unrated and the segment cannot be finalized. The neck interface cannot be rated yet, because the neck load needs the effective mass of Seidi et al. 2014, which is not extracted. Open.

(b) *Wall room* [source: `data/envelope/shank_R.yaml`, `thigh_R.yaml`; shell t = 5 mm per 0007 D4]:
- Shank: skin radius 24.75 mm at station 360 mm, which is 19.75 mm inside the shell, so a round tube there is at most 39.5 mm. A stroke layer there comes out of that radius, and a stroke of about 20 mm would remove the tube.
- Thigh outside the hip zone: 41.73 mm inside the shell, so at most 83.5 mm across. The hip zone has an 81.25 mm radius.

A wall thickens inward only. At 39.5 mm the bending section modulus is 2.10 cm³ at a 2 mm wall, 2.92 cm³ at 3 mm and 6.05 cm³ solid, so thickening buys at most 2 to 3 times in the lower shank. No stroke fits the shin at its bottleneck, so a knee-strike load that runs down the shank is taken by bypass (D5).

**D5 Load path and protection hierarchy.** A fall load is routed in this order, and a lower level takes only what the one above cannot.

1. *Bypass.* A secondary path that engages under overload deflection (hard stop, overload shoulder, shell-to-structure contact) carries the load around bearings, gears and cable. These are the parts a shock damages and the parts that cannot be resized later. The bypass is structure, checked under D2. Its engagement gap g is a number in the joint or interface record, chosen so that the force the primary path carries at deflection g stays within C0 and the drivetrain's rated peak. [design]
2. *Torque limit into the drivetrain.* Credited only for a passive element with a stated slip or yield torque. A firmware current limit, a controller torque limit, braking, or a joint that yields because the controller lets it earns nothing (0036, 0019 D1). A backdrivable transmission is allowed and probably lowers the load. Its reflected rotor inertia (ratio squared) leaves the transmitted torque with no stated bound, however, so v1 credits no reduction.
3. *Compliance.* Energy absorbed over a stroke from D2, linear or angular, by a passive element with a stated force-deflection or torque-angle characteristic. A passive slip element is levels 2 and 3 at once: its slip torque bounds the drivetrain torque and its reserved angle absorbs the energy. None exists in v1, so none is credited toward a claim. A linear stroke is a volume reservation, prose until rm.v1-thread-budgets. An angular stroke is a range reservation, stated in the joint's record.
4. *Sacrificial parts.* They take what remains. A part may be designated sacrificial only if its cost and time to replace are stated [design] and it fails before levels 1 and 2 are loaded. A connector is not credited with protecting the actuator it joins.

Application to the arm, from the Oct 26 to 27 cases:
- *Outstretched hands.* The elbow extension stop is the lock against hyperextension, with overload shoulders at the shoulder as the bypass (level 1). The stop is not the energy path: the stroke and cap come from rm.v1-elbow-load-basis (D3).
- *Arm trapped under the torso.* Accepted as repairable damage (level 4).
- *Lateral fall onto the shoulder.* The shell bottoms on torso structure before the pitch bearing takes thrust (level 1).

**D6 Parts that protect another segment.** A protective part is housed in the segment whose structure it belongs to, and counts in that segment's budget. It acts on the protected segment only through an interface record (`if.*`) that carries its role: direction, rated force, stroke and engagement gap. Each side checks against those numbers by address, and neither copies the other's. Tests:
- (i) The protected segment's check reads the interface numbers alone.
- (ii) Swapping the housing part for another that meets the same numbers cannot change the protected segment's check.

The protected segment takes credit only if the interface fixes force and stroke and the part exists in hardware. In v1 no compliant part exists, so every protected segment reserves as if it were absent. The clavicle case is compliance housed in the thorax, reaching the shoulder through the thorax-shoulder interface. The interface's stroke is the D2 stroke.

**D7 Reservations.** A reservation is a part record `part.<segment>.fall-reserve`. It is `housed_in` the segment, with `mass: {kg: <one unit>, source: adr-0037 D7, reserved: true}` and `sides` as the segment, status proposed, created by Code after acceptance. There is one record per zone and segment in D3. No new record kind.

Mass is the interface element at the zone's cap, modelled as a solid round aluminium cantilever: d = (32 n F_cap ℓ / (π σ_y))^(1/3) and m = ρ (π/4) d² ℓ. Here n = 1.5, σ_y = 240 MPa [source needed, catalog], ρ = 2700 kg/m³ [source: 6061 fixture], and ℓ is a standoff [design]: 60 mm pelvis, 40 mm shoulder, 30 mm arm stop. A zone with no stated standoff takes 60 mm, the longest. Per unit:

| F_cap | pelvis (ℓ = 60 mm) | shoulder (ℓ = 40 mm) | arm stop (ℓ = 30 mm) |
|---|---|---|---|
| 10 kN | 0.144 kg | 0.073 kg | 0.045 kg |
| 20 kN | 0.229 kg | 0.117 kg | 0.072 kg |
| 40 kN | 0.364 kg | 0.185 kg | 0.115 kg |

The claim is the element at the zone's cap, rounded up to the next 0.05 kg. It is a lower bound; backing structure is found at characterization. Until a zone has a cap, it claims the 40 kN element, because a claim can be released later and cannot grow. On that basis the v1 claim is:

| Zone | Housed in | Standoff | kg per unit | Units | kg |
|---|---|---|---|---|---|
| hip | pelvis | 60 mm | 0.40 | 2 | 0.80 |
| shoulder | thorax | 40 mm | 0.20 | 2 | 0.40 |
| buttock | pelvis | 60 mm (default) | 0.40 | 1 | 0.40 |
| back | thorax | 60 mm (default) | 0.40 | 1 | 0.40 |
| knee | thigh | 60 mm (default) | 0.40 | 2 | 0.80 |
| hand and arm | upper_arm | 30 mm | 0.15 | 2 | 0.30 |

Total claimed: 3.10 kg (4.8% of 65 kg), of which the pelvis holds 1.20 kg. Mass stays small per unit whichever cap is chosen, which is the point: the cost of a fall case is the stroke and the load path, not the element. Volume stays prose until rm.v1-thread-budgets and must not be treated as final (0036).

## Consequences

- The record's finding is a stroke per zone at a chosen cap, not a force: volume where the stroke is linear and joint range where it is angular. Where no cap in the series fits (D2c), the zone needs a superseding record.
- This record makes no carry claim; every zone reserves (D3). 0036's Verification line governs carry claims only, so it is not engaged here. The first carry claim, from a later version with an absorber in hardware or a drop test, brings it back.
- Amendments under D1(d) leave closed roadmap nodes closed. A node reopens only when a change fails one of D1(d)'s three tests, and then only if it reads the quantity that changed. Closing v1 against this record needs the frozen set (caps, housing segments, mass claims, reserved strokes), not the whole zone table.
- The knee and hand-and-arm strokes are the likeliest to fail D1(d)'s third test, since their energies rest on drop heights chosen here (260 J and 320 J against E_max of 540 J). A knee drop of 0.55 m instead of 0.40 m would raise the knee energy to about 360 J and grow its stroke. That change goes to a superseding record, which is cheap because rm.v1-elbow-load-basis and the knee design pin those inputs before anything is built. The drop heights stay [design] until then.
- Stroke is the parameter later versions tune. Protective behaviour credited by a superseding record draws on the same E_design (D2e), so reserved stroke can shrink or caps drop as behaviour is verified. Each zone the behaviour routes energy into is re-checked.
- The inputs are less certain than they look. E_max depends on the centre-of-mass height and h_end, both [design]. The knee and hand energies depend on drop heights chosen here. η is a requirement whose achievability is unchecked. Freyja's own m_eff per zone (D1c) is the cheapest replacement for E_max, and a drop test on a mock segment is the first thing that would replace the drop heights.
- The reserved mass is 3.10 kg at the 40 kN element. It is provisional and is released zone by zone as caps are set.
- The stumble magnitude stays open. 0019 D1(c) remains [source needed]; this record does not supply it.
- Fall cases take n = 1.5 at the cap in 0019 D1(c) and D2.
- rm.v1-fall-load-cases joins the blockers of rm.v1-upper-arm-characterized. rm.v1-elbow-load-basis (0008) takes the arm's stroke home and cap (D3).
- D4a puts rated overload on 0020 (connectors: add compliance stroke and overload stop, per the brief) and on rm.v1-trial-rig-concept (harness hardpoints).
- v1 neither relies on nor credits backdriving. A later version that dissipates fall energy through its actuators returns that energy to the 48 V bus. A zone's E_design over an arrest of about 0.1 s is several kilowatts: 540 J in 110 ms, F4's time to its second hand peak, is about 4.9 kW [design: duration illustrative]. That version needs a clamp or brake resistor sized to it, and the v1 bus design should not preclude one.
- The literature has one job here, calibration. Verifying more rows does not flip a call; a Verified row can only lower a reservation (D1c).
- Where D3 says not extracted, room is open until the bridge extracts it, and those zones have no cap.
- v1 still makes no tested fall-survival claim (0036).

## Rejected options, and why each one died

**D1.**
- *Literature contact forces as the demand.* They describe other bodies and other skins. Every rigid-floor hip force in the bracket is set by 30 to 140 mm of tissue or gel, and Freyja has neither.
- *Simulation soft-contact energy or force.* 0036: soft-contact peaks depend on solver parameters and the timestep. Configuration-space mass properties are not this (D1c).
- *A mean or median energy, including the midpoint of the E_max range.* The bound is the point; a central value hides the spread.
- *Crediting leg buckling or bracing to lower E.* Behaviour credit (0036). A later version can earn it (D2e).
- *Sharing a two-handed arrest between the hands.* There is no source, and one arm can land first or alone (S4).
- *Lowering the hip energy on S1's human effective mass.* Effective mass rises with stiffness, and a welded robot is stiffer than an active human.

**D2.**
- *Predicting force from an assumed skin.* The skin does not exist in v1, and force is very sensitive to its stiffness (D2b spans 4 to 164 kN).
- *η as a material property to be sourced.* It describes a part that does not exist; it is a requirement on that part.
- *A cap chosen for interface cost alone.* The load path behind the interface sees the cap too.
- *Factor 2 on the cap.* It stacks margin on an upper edge the absorber enforces.
- *Fatigue on fall cases.* Rare event.
- *Dynamic rating for impacts.* C0 is the static-overload limit.

**D3 and D4.**
- *Carry any case rigidly in v1.* No zone has a stroke (D2b).
- *Carry the arm through the elbow extension stop.* A lock is not a stroke.
- *Thickening walls to carry.* The shank has at most 2 to 3 times.
- *Rating interfaces later.* That is 0036 option C.

**D5.**
- *A connector fuse.* It does not protect the parts it joins.
- *Crediting firmware torque limits or backdriving.* Behaviour credit (0036).

**D6.**
- *Housing the protective part in the protected segment.* A neighbour swap would change the protected segment.
- *A cross-segment part with no interface record.* The numbers would have no home.

**D7.**
- *A flat unsized claim.* Not needed once every zone has an energy and a stroke.
- *Reserving mass only.* Mass is the cheap part; the reservation that matters is the stroke.
- *Claiming at the cap a zone will get later.* A claim may be released later but must not grow.
- *Leaving zones without a stated standoff unclaimed.* 0036 requires a quantity, not an intention.

**D1(d), amendments.**
- *A superseding record for every change to the zone list.* It would reopen closed roadmap nodes for changes that move no v1 interface, cap, claim or reserved stroke.
- *Freezing the whole zone table.* Later versions will refine scenarios and energy bases, and nothing in v1 hardware depends on most of them.

## Revisions

Dated amendments under D1(d). Each entry states the change, the three tests (interface directions already rated, caps unchanged, stroke inside the existing reservation) and the result. None yet.
