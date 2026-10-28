---
schema: roadmap-node/2
id: rm.v1-fall-design-basis
title: "Fall design basis recorded: per segment, which fall cases govern, the factor and independent source each rests on, and the mass and volume reserved where the hardware does not carry the case"
short: Fall basis
parent: rm.v1-ariadne-fall-loads
blocked_by: [rm.v1-fall-sources, rm.v1-fall-intent]
estimate_days: 1.5
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: decision
  record: decisions/0037-fall-design-basis.md
---
Joe's decision, made on a table: per segment, the fall bracket from rm.v1-fall-sources against the walking envelope, and what the ratio says. Where a fall case governs, design to it or reserve; where it does not, say so. This quantifies the reservations 0036 requires: a reserved mass claim per segment (a row in the thread's mass budget) and a reserved volume (rm.v1-thread-budgets gives that a home).

It also checks two things the redesign risk turns on. First, whether the slim-leg aesthetic envelope leaves room to thicken a wall, since an interface that cannot grow is the one real redesign cost. Second, where the load path puts a fall's loads: hard stops into structure rather than through the transmissions, which are the parts a shock load damages and the parts that cannot be resized later. No credit for fall behaviour, and no magnitude taken from simulation alone.

Inputs from the Oct 2026 arm discussion (docs/briefs/ariadne/stage3b-brief.md, Follow-ups): a protection hierarchy in place of a connector fuse, in order: (1) keep impact loads out of bearings and gears through secondary load paths that engage under overload deflection (hard stops, overload shoulders, shell-to-structure contact); (2) limit torque into drivetrains (backdrivable or controlled-yield joints); (3) absorb energy over a defined stroke with damped compliance; (4) let cheap parts take what remains. Rare impacts are checked against a bearing's static rating C0. Open question for this record: a convention for parts that protect another segment (compliance in the clavicle softening a lateral fall onto the shoulder) without breaking modularity; one candidate is that such a part is housed in its own segment and reaches the protected one only through an interface record.
