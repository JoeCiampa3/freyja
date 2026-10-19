---
schema: roadmap-node/2
id: rm.v1-fall-load-cases
title: "Fall load cases in the thread, each with an independent source attached: simulation ranks which segments meet the floor first and how severe each direction is, the sources give the magnitudes"
short: Fall cases
parent: rm.v1-ariadne-fall-loads
blocked_by: [rm.v1-fall-design-basis, rm.v1-thread-sources]
stub: true
tags: ["region:whole-body", "phase:sim"]
---
Forward dynamics with contact, unlike every other load case in the thread (those are statics or inverse dynamics with the ground reaction supplied). No fall scenario exists yet; it is created here. Rank across directions and across a solref and solimp sweep, and report the spread rather than a number. The records are proposed, with independent_source_required true.
