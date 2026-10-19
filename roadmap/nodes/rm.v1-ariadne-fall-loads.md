---
schema: roadmap-node/2
id: rm.v1-ariadne-fall-loads
title: "Fall loads defined for v1: what a fall may break, the load cases that follow it, and the independent sources their magnitudes rest on"
short: Fall loads
parent: rm.v1-ariadne
tags: ["region:whole-body"]
---
Simulation can rank falls but cannot give their magnitudes: soft-contact peaks depend on solver parameters and the timestep. So these cases rest on independent sources. Whether v1 is designed to touch the ground at all is decided first (rm.v1-fall-intent). If it is not, this subtree is superseded and what remains is the arrest load on the harness points, which the rig and torso records carry.
