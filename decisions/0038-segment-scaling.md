---
id: adr-0038
status: accepted
date: 2026-10-19
links: []
---
## Context

The BSIP re-verification (2026-10) found the rows match their sources and left two notes, both about the lengths.

- **Only six lengths scale.** The sheet scales the shank, thigh, pelvis, abdomen, thorax and head and neck by one factor, `k` = (stature - ankle height) / (sum of Dumas's six reference lengths) = (1700 - 62.7) / 1561 = 1.048879. The upper arm, forearm, hand and foot stay at Dumas's reference values, which belong to a 1.61 m woman (Young et al. 1983, as adjusted by Dumas 2007). No record says why. The scaling was built as a closure of the standing-height stack, and the four lengths are outside that stack. Freyja therefore has a 1.70 m body with 1.61 m arms, hands and feet.
- **The closure assumes every length is vertical.** It sums chord lengths. Dumas defines the pelvis length as the distance from the lumbosacral joint to the sagittal projection of the hip centre, 107 mm, of which only 93 mm is vertical when the pelvic frame is upright. The sheet's own integrity check reads "top of head minus stature" = -14.684 mm for that reason (97.546 - 112.230). The other segments are collinear by construction in the model, so only the pelvis, and the standing pelvic tilt, matter. At the tilt of record 0004 (12 degrees) the shortfall is 5 mm at the current factor.
- **The ankle height is an unscaled mean.** 62.7 mm is the ANSUR II female mean lateral malleolus height (n = 1986, mean stature 1628.5 mm).
- **The foot geometry is a template constant.** The foot box is 41 mm behind and 165 mm ahead of the ankle (206 mm; `FOOT_REAR_FRACTION` 0.25 of the 165 mm length), a design choice with no sheet source. The 165 mm is Dumas's foot length, which Table 1B shows is heel to the midpoint of the first and fifth metatarsal heads, not ankle to metatarsal heads (ADR 0001 amendment). Anatomically, at Freyja's scale: heel 62 mm behind the ankle, first metatarsophalangeal joint about 128 mm ahead, toe tip about 195 mm ahead, foot length 257 mm (ANSUR II, 246.3 mm scaled by 1700/1628.5), against the box's 206 mm. The dataset's shoe markers span 80% of the anatomical foot (memo 23, D1) and do not measure it.

## Decision

Joe to confirm each point; the values are my recommendation.

1. **One factor scales every Dumas length**, including the upper arm, forearm, hand and foot. The BSIP normaliser of each segment is its reference length times that factor, so every mass fraction, centre-of-mass fraction and radius of gyration stays as published. Masses are unchanged; inertias grow with the factor squared (about +10% for the four newly scaled segments).
2. **The factor closes the stack on vertical heights at the design posture:**
   `k = (stature - ankle_height) / (L_shank + L_thigh + L_abdomen + L_thorax + L_headneck + v)` with the six Dumas reference lengths and `v = X_HJC sin(theta) + |Y_HJC| cos(theta)`, the vertical drop from the lumbosacral joint to the hip centre at the design pelvic tilt `theta` of record 0004 (Dumas's unscaled hip centre 54 mm forward, 93 mm below). The pelvis keeps `107 x k` as its normaliser.
3. **The ankle height scales with stature:** 62.7 x 1700 / 1628.5 = 65.5 mm. The malleolus is part of the foot, which scales.
4. **With those two changes and theta = 12 degrees, k = 1.0504.** (The tilt alone would give 1.0521; the ankle height alone, 1.0471; the current 1.0489.) The built model's top of head must then sit within 3 mm of the 1700 mm stature.
5. **Foot geometry comes from the sheet, in millimetres ahead of the ankle centre,** not from the template:
   - heel: Dumas's calcaneus 59 mm x k = 62.0 behind (the shoe markers give 65.5, SD 2.4);
   - foot length heel to toe tip: ANSUR II 246.3 mm x 1700/1628.5 = 257.1;
   - first MTP (the toe hinge): ANSUR II ball-of-foot length 182.1 x 1700/1628.5 = 190.1 from the heel, so 128.1 ahead of the ankle (Dumas's first metatarsal head scaled gives 121.8, the dataset model's MTP 129.6, the midpoint of the first and fifth heads 111.9);
   - toe tip: 257.1 - 62.0 = 195.1 ahead, so the toe is 67.0 mm long;
   - Dumas's 165 mm stays as the foot's BSIP normaliser (173.3 mm at the new factor), and its centre of mass stays 27.0% of that length ahead of the ankle.
   The box widths, the toe height (25 mm) and the toe's mass fraction (14.4%) and centre of mass (43.6% along it) are also sheet inputs; the 100 mm width and the 25 mm height are design choices with no source.
6. **The seven missing ROM values** and the toe's range (0 to 80 degrees extension) enter the sheet in the same build.

## Consequences

- Every length changes by +0.14% (the six stack segments, k 1.0489 to 1.0504) or +5.0% (the four newly scaled), the ankle height by +4.4%, the foot box from 206 to 257 mm. The standing lean, the polygon, the ankle-torque cap estimate and every hard-coded 41 mm and 165 mm in the repo (memo 23, D9) change with it.
- The arm's inertia grows 10%, which moves the elbow and shoulder demand before the elbow load basis is chosen. That is the cheapest time for it.
- One build, one regeneration (`rm.v1-toe-in-model`, then `rm.v1-stage2-closed`).

## Rejected options, and why each one died

**Leave the arm, hand and foot lengths unscaled.** Rejected: nothing in the record supports it, it makes the arms 4.8% short against the stature, and the foot would stay 233 mm long (Dumas heel to second toe tip) against 257 for a 1.70 m woman.

**Scale them by a different factor, or only the foot.** Rejected: there is no second anthropometric anchor in the sheet, and one factor keeps the sheet's definition of Freyja as a uniformly scaled reference woman.

**Close the stack on chord lengths (the status quo).** Rejected: it leaves the top of head 5 to 15 mm below the stature, depending on the pose, and the figure that the sheet already flags.

**Take the foot geometry from the dataset's shoe markers.** Rejected: they sit on a shoe, span 80% of the anatomical foot, and the one measured malleolus check (AB15) puts mid-malleoli 20 to 39 mm from the model's ankle centre.

**Take the foot geometry from Dumas alone.** Not chosen: it gives a 244.7 mm foot (Young's women have a foot 14.5% of stature, ANSUR II 15.1%, possibly the heel-to-second-toe convention), and ANSUR II is a larger measured barefoot standing sample. Dumas's heel offset is still used, since ANSUR II does not give the ankle's position.
