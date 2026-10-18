---
schema: roadmap-node/2
id: rm.v1-ariadne-system-model
title: "System model in place: every v1 segment, joint, part, interface, load case and harness run held once as a record, every dossier generated from them, and stale work reported with the values that moved"
short: System model
parent: rm.v1-ariadne
---
Ariadne's data layer (Stage 3a). Relations are stored once, on the record that owns them, and every per-item document is generated, so moving a part between segments is a one-line edit whose consequences are computed. Ariadne-track work, not architecture: it is the product's data, not repo tooling. The CAD bridge (Stage 3b) writes into it.
