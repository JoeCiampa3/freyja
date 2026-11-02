---
schema: roadmap-node/2
id: rm.v1-knee-concept-adr
title: "Knee actuation concept recorded as an accepted ADR"
short: Knee concept
parent: rm.v1-knee-actuation
estimate_days: 1.0
tags: ["region:leg", "phase:spec"]
done_when:
  type: decision
  record: decisions/0014-knee-actuation-concept.md
---
Open decision: earlier knee work is an input, not a commitment.

Fall zone (adr-0044 D3): this record owns the knee zone (forward collapse onto one knee, 260 J). The four-bar fills the knee, so any stroke is part of that mechanism. Memo 59's 51.1 mm predates the four-bar and is an upper bound. If no stroke fits at any cap, the record says so (adr-0044 D2). Estimate raised to 1.0 day for the fall mechanism and cap.
