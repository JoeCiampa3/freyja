---
schema: roadmap-node/2
id: rm.v1-upper-arm-designed
title: "Upper-arm structure designed in CAD to its requirement records and connector record, ready for validation"
short: UA designed
parent: rm.v1-upper-arm-structure
blocked_by: [rm.v1-elbow-actuator-selected, rm.v1-upper-arm-characterized, rm.v1-upper-arm-requirements, rm.v1-upper-arm-connectors, rm.v1-provisional-design-rules]
estimate_days: 3.0
tags: ["region:arm", "phase:design", "stage3"]
done_when:
  type: manual
---
Manual until the real design's work item (`work.upper-arm-cad`, revised from the bridge placeholder `p1`) consumes the upper arm's requirement records; then the criterion becomes `{type: work, work: work.upper-arm-cad, status: current}`. Adopting it earlier would pass on the placeholder, which is stamped and current (memo 41). At the estimate cap: if it runs past three days, split it into layout and detail. Designed to the provisional design rules; rm.v1-design-rules confirms them before fabrication.
