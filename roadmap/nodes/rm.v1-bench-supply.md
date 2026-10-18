---
schema: roadmap-node/2
id: rm.v1-bench-supply
title: "Bench power supply at the working bus voltage in place behind the bench e-stop: current limited, and with a recorded way to absorb regenerated energy"
short: Bench supply
parent: rm.v1-metabolic
blocked_by: [rm.v1-power-architecture, rm.v1-bench-estop]
stub: true
tags: ["phase:bench"]
---
A cheap 24 V switching supply is on hand; whether it serves any bench is decided here. A bench supply generally cannot sink regenerated energy, so the absorption path (clamp, braking resistor or battery) is settled before any actuator is back-driven.
