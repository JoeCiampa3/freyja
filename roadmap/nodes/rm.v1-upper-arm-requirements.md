---
schema: roadmap-node/2
id: rm.v1-upper-arm-requirements
title: "Upper-arm requirement records authored from the characterization file, setting the values its CAD is validated against"
short: UA requirements
parent: rm.v1-upper-arm-trace
blocked_by: [rm.v1-upper-arm-characterized, rm.v1-structural-method]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: manual
---
Authored, not generated: the characterization file carries the inputs (loads, ROM, volume, interfaces), and these records (requirements/, CONVENTIONS section 8) carry Joe's acceptance values. They block the design leaf as well as validation, because thresholds are authored before the work. Manual: an artifact criterion reads one file and no requirement schema exists.
