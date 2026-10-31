STATE: base 091e091b694e | brief architecture sha256:18d9fa74b1b4, ariadne sha256:f58800563b5d | snapshot sha256:492fe816e6d8 | tests not run (Part A wrote nothing; last full suite 2055 passed at 06cab1c) | dirty no (before this memo)

# Memo 54: brief 11 stopped at S1; a grid phase fails gate 3b

Brief: `docs/briefs/architecture/volume-extractor-brief11.md` (sha256 18d9fa74b1b4, committed alone as 091e091). Part A only. Part B did not run. This memo is left uncommitted, because S1 says to commit nothing further.

## Decision summary

- **S1 fired, on its second clause.** Phase 1.5 mm fails gate 3b: arm field 3.9871 l against raster 4.0791 l, -2.25% against 1%. Every other gate passes on all four phases, and C1 to C4 pass on all four.
- **C2 is not measuring raster phase.** Its spread is **0.0154 points against S1's 0.035**, and it stays between -0.415% and -0.430%. Closure's 0.070-point margin to the 0.5% limit is therefore real, and the committed phase is the worst of the four, so it is not flattered.
- **The failure is a labelling fragility, not arm geometry.** At phase 1.5, 7 groin and axilla vertices flip from torso to arms. The groin ones sit at the crotch apex layer (z 807.6 mm, apex 808.4 mm). They pull 0.055 l of right-thigh cells into the arm class. No body's field volume moves much: the legs' sum changes by 0.0012 l.
- **Part B's snap would land on origin (-100, -554, -6)**, phase (0.28, 1.05, 0) from today's. That phase shows no groin flip. But I only checked its vertex labels, not its gates, and the snap would freeze a phase that passes without removing the cause.
- **Correction to memo 53:** it called phase noise "about 0.1 mm" and "well under a voxel". That holds for the centroids, but the label flip is a larger effect, 0.055 l in one raster class.
- **Decision for you:** how to proceed. Recommended: fix the groin labelling first, with a phase test, then run Part B as written.
- **What would change this:** the four phases lie on one diagonal, and only `BodyRaster` was shifted. Other phases could fail too, or the voxel fields could add spread.

## Part A

`BodyRaster.__init__` (`tools/envelope/features.py:92-98`): the x and y origins are the vertex minimum minus 6 mm, and z is -6 mm. So x and y depend on the sculpt's extent, and on v3 that extent is set by the arms.

Each run was `gates.run` on v3 with `BodyRaster`'s origin shifted along all three axes, patched in a scratch script with output to the scratchpad. Nothing under `data/`, `tools/` or `checks/` was written. The voxel fields' own grids were not shifted. Phase 0 reproduces the committed closure to all digits.

| Phase, mm | C2, points | C4 worst | C1 upper arm | C1 forearm | Legs, l | Arms, l | Gates failing |
|---|---|---|---|---|---|---|---|
| 0 | -0.4300 | thorax -0.026% | 1.000007 | 0.999973 | 18.9136 | 3.9754 | none (35 pass) |
| 0.5 | -0.4254 | thorax -0.016% | 1.000016 | 0.999990 | 18.9136 | 3.9756 | none |
| 1.0 | -0.4247 | thorax -0.024% | 1.000007 | 0.999972 | 18.9150 | 3.9764 | none |
| 1.5 | -0.4147 | thorax -0.058% | 1.000018 | 0.999994 | 18.9148 | 3.9872 | **3b arms: -2.254%, limit 1%** |

C4 is against v2 at its own phase 0, so it mixes the sculpt's change with raster phase. C3 was not computed per phase because that needs v2 at each phase; the SJC's phase scatter is below.

**Spread of C2: 0.0154 points, S1 limit 0.035: passes.**

**S1 verdict: fired,** because one phase fails a gate.

## What happened at 1.5 mm

Raster classes, unconformed, l:

| Class | 0 | 0.5 | 1.0 | 1.5 |
|---|---|---|---|---|
| arms | 3.4685 | 3.4746 | 3.4817 | **3.5493** |
| thigh_R | 6.4855 | 6.4741 | 6.4774 | **6.4225** |
| thigh_L | 6.4692 | 6.4816 | 6.4778 | 6.4731 |

From phase 1.0 to 1.5, `thigh_R` drops 0.055 l and arms gain 0.068 l. Only the right side moves, and the field's `upper_arm` gains only 0.005 l. So gate 3b is comparing a raster class that has gained thigh cells.

Vertex labels against phase 0 (`decompose.vertex_regions`; re-run in the scratchpad, about a minute):

| Origin | Torso to arms | Other changes |
|---|---|---|
| Phase 1.5 | **7, z 807.6 to 1294.3 mm**, y to ±216 | 79 at the head and neck |
| Phase 1.0 | 2, at the axilla, z 1293 | 6 torso to legs, **z 807.6 to 808.2, y ±164.7**, the same groin area; 81 at the head and neck |
| Part B's snap | 2, at the axilla, z 1293 | 4 arms to torso at the axilla; 64 at the head |

So the groin vertices at the crotch apex layer change class with phase: torso at 0, legs at 1.0, arms at 1.5. The likely mechanism is `vertex_regions` classifying a small piece of that layer as an arm because it isn't one of the big pieces, and the nearest-vertex rule then carrying the label into the thigh. I infer that from the labels and classes; I have not stepped through it. The asymmetry (right thigh only) is also unexplained.

**Other quantities that move with phase:**

| Quantity | Range over the phases |
|---|---|
| SJC x, mesh frame | 15.55 to 15.81 mm (through the CJC's x, 1.74 to 2.00 mm) |
| Neck plane | 1472.0 to 1476.5 mm |
| Axilla level | 1294.0 to 1295.5 mm, following the z shift |

The SJC's 0.26 mm scatter is well inside C3's 2 mm, but memo 52's 0.007 mm is far below it, so that number's precision is not real. C3 is better read as "under about 0.3 mm". It still passes by a wide margin.

## Options

| Option | For | Against |
|---|---|---|
| **A. Fix the groin labelling, with a test across phases, then Part B as written (recommended)** | Removes the cause; gate 3b stops depending on phase | One more label rule, and another rebuild |
| B. Part B as written now | Smallest change; the snap's labels look clean | Freezes a phase that happens to pass; the cause stays and a later sculpt could hit it. Gates at the snap are unverified |
| C. Leave the code as it is | No rebuild; today's output passes | Arm edits still perturb leg numbers, and could land on a failing phase |

A change to the label rule, or to S1, is yours to make; I have changed neither.

## My mistakes

- **Memo 53's "well under a voxel"** understated this: I had looked at centroids only, and had not varied the phase.

## Questions for Joe

1. Which option? If A, should the rule be that a piece at or below the crotch apex can never be an arm (my first candidate), or do you want it worked out from the layer topology?
2. Should Part B's rerun of S1 also sample off-diagonal phases, given that the snap's phase (0.28, 1.05, 0) is off the diagonal?
