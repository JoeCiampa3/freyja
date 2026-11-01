---
schema: roadmap-node/2
id: rm.v1-fall-load-cases
title: "Fall load cases in the thread, one per adr-0037 zone and scenario, each carrying its design energy with checked evidence; simulation ranks only which zone meets the floor first"
short: Fall cases
parent: rm.v1-ariadne-fall-loads
blocked_by: [rm.v1-fall-design-basis, rm.v1-thread-sources]
stub: true
tags: ["region:whole-body", "phase:sim"]
---
Written in the energy-defined form of thread-record/2 (rm.v1-thread-sources): zone, direction, design energy and energy basis as adr-0037 D3 gives them after its Revisions; `zone_in` the housing segment; `independent_source_required: true`; and evidence naming the clause each energy rests on (D1(b) for E_max; for the hand and arm, D3 as revised and adr-0008 D5), plus any Verified row that lowered one. The records are proposed. The decision decides each energy and the record carries it, so a change to 0037 that moves a carried value edits the record in the same commit.

Simulation enters only where 0036 and 0037 D1(c) let it. The ranking is forward dynamics with contact, unlike anything else behind a thread load case: it orders which zone meets the floor first in each fall direction, reported across a solref and solimp sweep as a spread, so an order that flips with contact parameters is visible. It sets no force, energy or other soft-contact quantity. No fall scenario exists yet; it is created here. Freyja's own effective mass at a contact (mass matrix with the joints welded) is a configuration-space quantity 0037 permits; if computed, it lowers a reservation only through a 0037 Revisions entry, and the record follows.

Head and neck have no energy in D3 and get no case until they do. The foot is not a fall case (stumble, adr-0019 D1(c)).

Retitled 2026-10-31: the first title had the sources give the magnitudes and the simulation rank how severe each direction is, both from before adr-0037.
