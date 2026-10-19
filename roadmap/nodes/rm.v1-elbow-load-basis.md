---
schema: roadmap-node/2
id: rm.v1-elbow-load-basis
title: "Elbow and upper-arm load basis chosen and recorded: which cases (static gravity sweep, arm swing, fall) and from what source"
short: Elbow loads
parent: rm.v1-upper-arm-trace
blocked_by: [rm.v1-bsip-reverified, rm.v1-fall-intent]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0008-elbow-load-basis.md
---
Stage 2 excluded arm swing, so the envelope has no dynamic elbow rows. Whether a fall case enters the basis follows rm.v1-fall-intent, which this waits on; if the accepted record includes one, add rm.v1-fall-load-cases to the blockers of rm.v1-upper-arm-characterized.
