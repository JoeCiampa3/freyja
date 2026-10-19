---
schema: roadmap-node/2
id: rm.v1-ariadne-fall-loads
title: "Fall loads defined for v1: what a fall may break, the load cases that follow it, and the independent sources their magnitudes rest on"
short: Fall loads
parent: rm.v1-ariadne
tags: ["region:whole-body"]
---
Simulation can rank falls but cannot give their magnitudes: soft-contact peaks depend on solver parameters and the timestep. So these cases rest on independent sources. rm.v1-fall-intent sets the protocol (nothing but the feet touch the floor in v1 trials) and the rule that each segment carries its fall case or reserves for it; rm.v1-fall-design-basis, decided after the literature bracket, sets the cases, the factors and the reservations.
