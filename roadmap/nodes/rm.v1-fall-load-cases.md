---
schema: roadmap-node/2
id: rm.v1-fall-load-cases
title: "Fall load cases in the thread, one per adr-0037 zone and scenario, each carrying its design energy with checked evidence; simulation ranks only which zone meets the floor first"
short: Fall cases
parent: rm.v1-ariadne-fall-loads
blocked_by: [rm.v1-fall-design-basis, rm.v1-thread-sources]
tags: ["region:whole-body", "phase:sim"]
---
Written in the energy-defined form of thread-record/2 (rm.v1-thread-sources): zone, direction, design energy and energy basis as adr-0037 D3 gives them after its Revisions; `zone_in` the housing segment; `independent_source_required: true`; and evidence naming the clause each energy rests on (D1(b) for E_max; for the hand and arm, D3 as revised and adr-0008 D5), plus any Verified row that lowered one. The records are proposed. The decision decides each energy and the record carries it, so a change to 0037 that moves a carried value edits the record in the same commit.

Simulation enters only where 0036 and 0037 D1(c) let it. The ranking is forward dynamics with contact, unlike anything else behind a thread load case: it orders which zone meets the floor first in each fall direction, reported across a solref and solimp sweep as a spread, so an order that flips with contact parameters is visible. It sets no force, energy or other soft-contact quantity. No fall scenario exists yet; it is created here. Freyja's own effective mass at a contact (mass matrix with the joints welded) is a configuration-space quantity 0037 permits; if computed, it lowers a reservation only through a 0037 Revisions entry, and the record follows.

Head and neck have no energy in D3 and get no case until they do. The foot is not a fall case (stumble, adr-0019 D1(c)).

Retitled 2026-10-31: the first title had the sources give the magnitudes and the simulation rank how severe each direction is, both from before adr-0037.

Expanded 2026-11-04 into two children: rm.v1-fall-cases-recorded (the records, which is what rm.v1-upper-arm-characterized waits on) and rm.v1-fall-ranking-audit (the ranking, still a stub, with a proposed reframing). adr-0044 (2026-11-01) adds a chest zone, so the cases cover it too. A case carries energy and direction and never a cap, so the cases wait on no cap; each cites its owning record once that record enters the zone's cap (adr-0044 D2).

Under adr-0044 (accepted 2026-11-01) the case list adds the chest zone (D1), and each zone's cap and stroke are set by its owning record (D3), not here. A case's evidence cites adr-0037 D1(b) for the energy and adr-0044 for the zone, and gains its cap by citation when an owning record enters one. The adr-0037 D7 reservation records, `part.<segment>.fall-reserve`, are created by rm.v1-fall-reserves-recorded (a stub, deferred by Joe 2026-11-04): seven, one per zone and segment (hip and buttock in the pelvis; back, chest and shoulder in the thorax; knee in the thigh; hand and arm in the upper arm), 3.50 kg in all (adr-0044 D6), each at the 40 kN element until an owning record enters a cap and releases mass. Memo 59's room numbers are evidence for a linear stroke only.
