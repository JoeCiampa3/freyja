---
id: adr-0001
status: proposed
date: 2026-10-11
links: []
---
## Context

Freyja's foot is a rigid, flat, toeless box. Stage 2 asked whether that can represent walking and, if not, what a toe would have to do. Evidence in the repo, with where each number comes from:

- **The measured centre of pressure leaves the box in late stance** (`docs/memos/memo5-stage2-t3c.md`, T3c.4, measured CoP placed on Freyja's foot at the same normalised place, polygon band 25 mm, 1.4 m/s, `counter_rotate` kinematics). In the last decile of stance the CoP is outside that foot's polygon in 66% of single-support frames and 99.7% of double-support frames (median outside 9 mm and 86 mm); at 1.6 m/s 85% and 100% (17 mm and 105 mm). In mid-stance the failures are small (12.5% at 40 to 50%, median 13 mm). The early-stance failures (85% in double support at 0 to 10%, median 38 mm) happen with the heel down and are not a toe effect.
- **A toeless box caps the late-stance ankle torque.** `docs/briefs/stage2-brief.md` T3b estimates the cap as peak ground force times the foot's reach ahead of the ankle (165 mm), about 140 N m; that figure was not recomputed here. The method that agrees with the dataset's moments, `A_filtered`, has ankle plantarflexion 95th-percentile peak torque of 149.3 and 163.8 N m (right, left) at 1.4 m/s and 157.6 and 169.4 N m at 1.6 m/s (`sim/runs/ENVELOPE.md`, gait record `gait.20261011-2317-walk_treadmill`): 7% to 21% above the estimated cap at the 95th percentile, and its maxima (162.9 to 202.5 N m) are higher. These loads rest on the human CoP, which the box cannot reproduce.
- **B (Freyja's own dynamics) is not rescued by a toe.** B's single-support CoP sits 65 to 66 mm behind the measured one on average with a fore-aft rms of 102 to 126 mm; segment masses explain about 12 mm of the rms and 18 mm of the mean (memo5), and moving the trunk group's centre of mass to the dataset's torso offset makes it worse (`memo6-stage2-close.md`, T9.2). A toe addresses the late-stance foot geometry, not that offset.

**What the dataset cannot supply: the toe's own loads.** The brief asked for the metatarsophalangeal angle, moment and power in late stance from the dataset. The dataset's OpenSim model has the joint locked: over every subject-stride and foot (17 subjects, 988 strides, 1976 stride-feet, both speeds) the largest `mtp_angle` is exactly 0 degrees and each subject's largest `mtp` inverse-dynamics moment is 0.13 to 0.30 N m (median 0.18), against tens to hundreds of N m for the other joints (`python sim/scripts/gait_diag.py toe`). There is no toe angle, moment or power in this dataset to scale to Freyja, and nothing in this record is a toe load.

## Decision

Not decided. Proposed for Joe: the evidence above shows a rigid, toeless foot cannot represent push-off, so the choice is between the three options below. Sizing an actuated or sprung toe needs a source this repo does not have. Two ways to get one, for Joe to choose: a published model or dataset that does not lock the metatarsophalangeal joint (the source and its licence to be identified and cited before any number enters the sheet), or a proxy from data already here (force-plate CoP and the heel and toe-tip markers give the force's lever about an assumed joint position, which is an assumption about where the joint is and would be flagged as a proxy).

## Consequences

- **No toe (today).** The foot rests on its toe edge in late stance. Stage 2's loads stay built on `A_filtered`, flagged provisional, and B and any controller are confined to a CoP inside the box: the late-stance ankle torque is capped near 140 N m by the T3b estimate, below the human-derived 95th-percentile peak of 149 to 169 N m. Nothing needs designing. A controller project inherits a foot that cannot push off.
- **Passive toe (a hinge with a spring or damper).** Lets the forefoot extend and moves the loaded edge forward, which removes the geometric cap without a drive. It needs the toe's extension range and a stiffness or a damping, and the dataset gives neither: its angle is 0 and its moment is noise. The loaded edge's position would also set the lever length and so the ankle torque, which `A` and `B` would then have to be re-run on.
- **Actuated toe.** Adds a drive, power electronics, mass and volume in the slim-leg envelope (the aesthetic envelope is a hard constraint, `docs/OVERVIEW.md`), and needs a moment and power demand that this dataset cannot supply. It cannot be sized from Stage 2.

## Rejected options, and why each one died

(Left for Joe.)
