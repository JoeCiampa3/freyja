---
id: adr-0036
status: proposed
date: 2026-10-19
links: []
---
## Context

We aim to build Freyja v1 such that future version's hardware demands do not force a full rebuild. However, the acceptance gate for v1 does not aim for full autonomy. At the time of v1 completion we must have a convention for how to handle falls during testing.

## Decision

v1's aim is to get to a working prototype as soon as possible, one that can later be iterated. To that end, we are deferring whole body fall testing to a later version. The v1 testing will be done in a harness, that allows full rom but will not allow the prototype to fall over. 

## Consequences



## Rejected options, and why each one died


