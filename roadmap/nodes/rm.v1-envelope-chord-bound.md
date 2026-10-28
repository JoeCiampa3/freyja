---
schema: roadmap-node/2
id: rm.v1-envelope-chord-bound
title: "Envelope margins account for CAD tessellation error: each bridge component's margin reduced by its chord bound, and a component without a chord guarantee flagged rather than trusted"
short: Chord bound
parent: rm.v1-ariadne-body-envelope
blocked_by: [rm.v1-bridge-tooling]
stub: true
tags: ["region:whole-body"]
---
A tessellated convex surface lies inside the true one, so margins measured to a CAD mesh are optimistic by up to the sidecar's `chord_bound_mm`. Memo 41 proposes: carry the bound and the `chord_guarantee` flag into the generated registry; subtract the bound in component margins; report `unguaranteed` instead of a number when a face fell back to the 15 degree default. The placeholder's 0.05 mm is below the 2 mm voxel and does not need it. Expand before the first part with free-form faces (a skin-following shell) enters the envelope, which is likely the real upper arm.
