---
schema: roadmap-node/2
id: rm.v1-fall-sources
title: "Fall impact magnitudes bracketed from the literature per body region and fall direction, with each source's subject, surface and what it measured"
short: Fall sources
parent: rm.v1-ariadne-fall-loads
blocked_by: [rm.v1-fall-intent]
estimate_days: 2.0
tags: ["region:whole-body", "phase:spec"]
done_when:
  type: artifact
  path: data/falls/sources.md
---
Magnitudes, not rankings. For forward, backward and sideways falls the file gives impact force or deceleration with units, the subject (human, humanoid, dummy), the surface and body mass, and says plainly where no source exists. Starting points to verify against the papers before any number enters the file, not facts: Robinovitch et al. 1991 (hip impact force in sideways falls), Fujiwara et al. (the UKEMI work on HRP-2 falls), Ha and Liu 2015 (humanoid fall-damage minimization).
