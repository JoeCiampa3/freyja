---
id: adr-0044
status: accepted
date: 2026-11-01
links: [adr-0037, adr-0008, adr-0036]
---
## Context

This record amends adr-0037 D1(d), D2(c), D3 and D7, and adr-0008 D6(j). Both records keep their status (CONVENTIONS section 8).

Memo 59 ran 0037's first-cap route for the five zones without a cap (fall inputs brief, T1). The envelope answered five of the six zones, but every room reading it gave is an upper bound. No registry yet holds the hip mechanism, the lumbosacral actuators, the knee four-bar, the shoulder mechanism or any structure (memo 59, finding 5). The hip result sits within one 2 mm voxel of the 40 kN stroke. The shoulder, buttock and back results turn on hardware nobody has placed. The arm's arc cannot be answered from the repo at all.

The fault is in the rule, not the run. 0037 D2(c) picks the cap from the radial depth the envelope shows. That assumes two things that do not hold before a segment is designed: that the stroke is a linear layer under the skin, and that the envelope knows what will sit behind that layer. A zone's stroke may be a layer, an arc about a pivot (the clavicle, 0008 D6(c)), a hinged or split structure, or a crushable shell, and each needs room of a different shape. The energy rule of 0037 D2(a) and D2(e) does not depend on the mechanism, and it stands. Only the selection of the cap moves.

0037 D1(d) has two further defects. It lists "adding a zone" as an amendment, but a new zone has no reserved stroke and adds a mass claim, so it can never pass the third test. Its first test, read literally, fails any change to a zone without a cap, since that zone's interfaces are unrated. The 2026-10-31 Revisions entry for the arm already read the first test as "no new direction".

The zone list also lacks a forward trunk zone. 0008 D5 says that once the hand skids past the friction cone, the arm earns no credit and "the other zones keep E_max". A forward fall that the arm does not arrest therefore lands on the anterior chest, and no zone covers it.

Tags are as in 0037.

## Decision

**D1 Chest zone.** One zone is added to 0037 D3:

| Zone | Scenario | Energy basis [design] | E_design | s_res at 10 / 20 / 40 kN | Housed in (units) | Owning node (D3) | Call |
|---|---|---|---|---|---|---|---|
| chest (anterior thorax) | forward, chest first, with the arm not arresting (beyond 0008 D5's cone) or not reaching | E_max | 540 J | 113 / 57 / 29 mm | thorax (1) | rm.v1-torso-structure | reserve |

The contact station is set by the owning record.

**D2 Who sets a cap.** This replaces the first paragraph of 0037 D2(c) and the first-cap paragraph of 0037 D1(d).

A zone's cap (F_cap or T_cap), stroke home and reserved stroke or range are set by the decision record that designs the zone's stroke home. That record is the one named by the zone's owning node in D3, and it states three things:
- *The mechanism.* It may be any passive element with a stated force-deflection or torque-angle characteristic and η ≥ 0.6 over the reserved stroke (0037 D2a), placed anywhere on the load path: a linear layer, an arc about a pivot, a hinged or split structure, a crushable shell, or something else.
- *The cap.* It is the lowest value in the 0037 D2(c) series at which the record shows the stroke home holds s_res, or Δθ_res = 1.25 Δθ, together with the geometry that shows it.
- *The mass claim at that cap,* under 0037 D7. It may only fall from the 40 kN element.

For a linear stroke, `analysis/fall_room.py` and `data/falls/room.json` are admissible geometry evidence. No other mechanism needs them.

A 0037 Revisions entry then records the cap by pointing to the owning record. The zone's load case cites both, in the same way the arm's energy cites 0037 D3 and 0008 D5.

Until then the zone has no cap. Its interfaces are unrated, its segment cannot be finalized (0037 D4a), and it claims the 40 kN element. If the owning record cannot show a stroke home at any cap in the series, the zone cannot meet 0036's principle, and that record says so.

The rest of 0037 D2(c) stands: the load path is rated with the cap, and raising the cap is cheap at a flange but not along the load path.

**D3 Owning nodes.**

| Zone | Owning node | Why there |
|---|---|---|
| hip, buttock | rm.v1-pelvis-structure | the pelvis holds the stroke, behind the hip architecture (adr-0010) and the spine placement (adr-0041) |
| back, chest | rm.v1-torso-structure | the thorax holds the stroke, beside the spine reservation |
| shoulder (lateral) | rm.v1-shoulder-concept (adr-0025) | the stroke is the shoulder girdle's arc, which 0008 D6(c) already hands to this node for the arm |
| knee | rm.v1-knee-concept-adr (adr-0014) | the four-bar fills the knee, so any stroke there is part of that mechanism |
| hand and arm | rm.v1-shoulder-concept (adr-0025) | 0008 D6(c) puts the stroke home at the thorax-shoulder interface |

When a stub owner is expanded, ownership passes to the child decision that designs the stroke home. That needs no new record.

**D4 Amending the zone table.** This replaces the first paragraph of 0037 D1(d).

Each zone's cap, housing segment, mass claim and reserved stroke or range are frozen once set, and change only by a new record. A Revisions entry may change an existing zone's scenario, energy basis or drop height, or add a scenario to an existing zone, if all three tests hold:
1. It adds no load direction to the zone.
2. It changes no cap that has been set.
3. Where the zone has a cap, its stroke fits inside what is reserved. Where the zone has no cap, the changed energy passes to the owning record, which sizes the stroke when it sets the cap.

A change that fails any of the three needs a new record. A new zone always needs a new record, as D1 here does, because it has no reserved stroke and adds a mass claim.

**D5 The arm's cap.** This amends adr-0008 D6(j). The arm has no cap in 0037 until rm.v1-shoulder-concept shows its arc. 0008 D6(a)'s 20 kN is the design judgment that record starts from, not a set cap. If that record finds room for a longer arc, the first cap drops to 10 kN under D2, with no superseding record. D6(j)'s rule that dropping the cap needs a superseding record applies only once a cap has been entered. An interface already rated above 1.5 × the cap that enters keeps its rating; 0008's 30 kN axial rating is one such case.

**D6 Mass claim.** The chest claims the 40 kN element at the default 60 mm standoff, 0.40 kg (0037 D7). The thorax then holds 1.20 kg of fall reservations, and the total is 3.50 kg (5.4% of 65 kg), against 3.10 kg in 0037 D7.

## Consequences

- Memo 59's draft Revisions entries are not applied. Its room numbers (`data/falls/room.json`) remain evidence an owning record may cite for a linear stroke, with memo 59's caveat that every reading (a) is an upper bound.
- No cap can be set before its owning node is decided. This blocks nothing new. rm.v1-pelvis-structure and rm.v1-torso-structure already wait on the hip architecture, the spine reservation and the trunk offset, and the knee and shoulder concepts are leaves in their own right. Closing v1 against 0037 means each owning record entering its zone's cap, which that record would have had to settle anyway.
- rm.v1-fall-load-cases gains one case, `lc.fall-chest`. Its evidence is adr-0037 D1(b) for the energy and this record's D1 for the zone.
- Each owning node now carries a fall requirement: its record must state the zone's mechanism, cap and stroke under D2. The node bodies should say so; that edit is a roadmap batch for Joe, not part of this record.
- T2 of the fall inputs brief (welded effective mass) stays held. It lowers energy, which matters only once an owning record finds its stroke home tight.
- D4's tests match how the 2026-10-31 Revisions entry for the arm was already read, so that entry stands as written.

## Rejected options, and why each one died

- *Set caps now from memo 59's reading (a).* They are upper bounds on hardware nobody has placed, and a set cap is frozen.
- *Keep the envelope-first rule and wait for the registries to fill.* The registries fill as the owning records place hardware, so the cap would wait for those records anyway, and the rule would still assume a linear layer.
- *Leave caps to a later version.* Interfaces are final in v1 (0036), and a zone without a cap cannot rate them.
- *Fold the chest into the back zone.* It is a different direction and a different contact; the back's stroke is posterior.
- *Build a sweep tool for the shoulder arc now.* The pivot is not chosen yet. The tool belongs with the shoulder concept.
- *Keep 0037 D1(d)'s wording.* It promises an amendment route for new zones that its own third test closes.
