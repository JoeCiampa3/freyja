---
schema: roadmap-node/2
id: rm.v1-gait-0p5
title: "Level walking at v1's 0.5 m/s acceptance speed run through the gait pipeline: method A's agreement band re-checked at that speed, the envelope and tracked extract regenerated, and its load case in the thread"
short: Gait 0.5 m/s
parent: rm.v1-ariadne-walk-loads
blocked_by: [rm.v1-thread-store]
estimate_days: 1.5
tags: ["region:whole-body", "phase:sim", "stage2"]
done_when:
  type: artifact
  path: thread/records/lc.walk-0p5.yaml
---
Sizing stays on the 1.4 and 1.6 m/s cases (the hardware rule). The 0.5 m/s case is the condition the controller, the power budget and the trial itself run under, and it checks that no row peaks at low speed: slow gait lengthens stance and double support, so peaks are not assumed to fall with speed.

First step: confirm from the dataset manifest that treadmill trials at 0.5 m/s exist in usable number. If they do not, stop and say so; a scaled 0.5 m/s case is not method A and cannot be band-checked. Then add the speed to the walk_treadmill spec, run the gait pipeline, rerun method A's agreement check at 0.5 m/s (the band was established at 1.4 and 1.6, not here), regenerate the envelope and the tracked gait extract, and last add lc.walk-0p5 to the thread as a proposed record, which is what makes this leaf pass. The final regeneration in rm.v1-stage2-closed covers all three speeds.
