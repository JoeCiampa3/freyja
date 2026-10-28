---
schema: roadmap-node/2
id: rm.v1-elbow-load-basis
title: "Elbow and upper-arm load basis chosen and recorded: which cases (static gravity sweep, arm swing, fall) and from what source"
short: Elbow loads
parent: rm.v1-upper-arm-trace
blocked_by: [rm.v1-bsip-reverified, rm.v1-fall-design-basis]
estimate_days: 1.0
tags: ["region:arm", "phase:spec", "stage3"]
done_when:
  type: decision
  record: decisions/0008-elbow-load-basis.md
---
Stage 2 excluded arm swing, so the envelope has no dynamic elbow rows. Whether a fall case enters the basis follows rm.v1-fall-design-basis, which this waits on; if the accepted record includes one for the elbow, add rm.v1-fall-load-cases to the blockers of rm.v1-upper-arm-characterized.

Inputs from the Oct 2026 arm discussion (docs/briefs/ariadne/stage3b-brief.md, Follow-ups): payload 1.0 kg at full extension (design) and 0.5 kg (nominal), from a household-object task list; speed demand from minimum-jerk trajectories with amplitudes and durations from the literature, recording each paper's onset and end definitions, and robot inertias from the snapshot; Soucie's 4.7 to 150 degrees as the ROM ceiling, Morrey's arc for loads. Magermans (2005) shows daily activities reaching about 157 degrees of elbow flexion, so the mechanism must reach the full ceiling. Joe holds PDFs of: Flash and Hogan 1985, Magermans 2005, Meyns 2013, Peeters, Simon-Martinez 2018, Schwarz 2022.
