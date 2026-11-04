# Fall inputs brief (for Claude Code): room at the zone contacts, first caps, and welded effective mass

Status 2026-11-04: T1 done (memo 59). Its draft Revisions entries were not applied; adr-0044 moves cap-setting to the owning records. T2 is held and not needed to close v1.

Read `CLAUDE.md`, `CONVENTIONS.md` and `docs/STATE.md` first, in the order `CLAUDE.md` gives, then the newest memo in `docs/memos/`, then `decisions/0037-fall-design-basis.md` (all of it, including Revisions and Amendments), `decisions/0008-elbow-load-basis.md` D5 and D6, `decisions/0007-envelope-extraction.md`, and rows S1 and S11 of `data/falls/sources.md`. This brief belongs to the Ariadne track. It feeds `rm.v1-fall-load-cases`, which waits on its result. It closes when Joe signs off the memo.

Tag: Delegate.

## Purpose

0037 left five zones without a cap: hip, shoulder, buttock, back and knee. D4a says a zone with no cap has unrated interfaces and its segment cannot be finalized, so these zones hold up every roadmap node that reads a fall rating. D1(d) lets a zone take its first cap by a Revisions entry if the value is in the 10, 20, 40 kN series, is the lowest whose s_res fits room cited from `data/envelope/`, and only releases claimed mass. No entry cites that room yet. The hand and arm zone is in the same position: 0008 D6(a) sets 20 kN as a design judgment, and D6(j) lists the 45 mm room check as outstanding.

Two tasks:

- **T1 (required).** Cite the room at each zone's contact, and find the lowest fitting cap per zone.
- **T2 (optional; do not start until Joe says so after reading the T1 memo).** Freyja's own effective mass and contact velocity per zone, the second route of 0037 D1(c). It can only lower a reservation, and v1 does not need it to close.

## What this run does not do

It decides nothing. Spare depth, caps and mass-claim releases are proposed in the memo and applied by nobody. It edits no decision record, creates no `part.<segment>.fall-reserve` record and no `lc.fall-*` load case (those belong to `rm.v1-fall-load-cases`), and changes no roadmap node, `CLAUDE.md` or `docs/OVERVIEW.md`. Once Joe has read exact proposed text and approved it, a later session may apply it.

## Gate criteria

Stated before the work. Each is reported in the memo as pass or fail with its numbers, and Joe signs off the memo's gate table. Do not change a criterion to make a result pass; a criterion that looks wrong is a finding.

**G1. Provenance.** Every room number names its envelope file, that file's `mesh_file` and `inputs_sha256_12`, and the shell thickness column it used. A file built from a mesh other than the current baseline (`data/makehuman/freyja-body-v3.obj`, per 0042) is reported and not used.

**G2. Nothing decided.** `git diff` after the run shows only new files (the script, its output, the memo). Every proposed Revisions or Amendments entry is text in the memo.

**G3. Reproducible.** The script is committed, takes no argument it does not record in its output, and two runs give byte-identical output.

**G4. Every zone has an outcome.** For each of the six zones: a cap with its s_res and the depth it fits in, or "none fits", or "cannot be answered from `data/envelope/`" with the reason. No zone is skipped and none is given a number the files do not support.

## T1. Room and first caps

**Zones and strokes.** The five capless zones take s_res from 0037 D3 (113 / 57 / 29 mm at 10 / 20 / 40 kN for hip, shoulder, buttock and back; 55 / 28 / 14 mm for knee). The hand and arm takes 90 / 45 / 23 mm from 0008 D5 and D6(b) (430 J). Recompute none of these; if one looks wrong, report it as a finding.

**Contact station.** For each zone, name the contact station: a point on the baseline mesh, its segment, its section station, and the body frame it is stated in. Pick the point the zone's scenario in 0037 D3 implies (hip first on a lateral fall, and so on). Joe confirms the stations in the memo before the depths are used.

**Depth.** At each station, from the section files and the envelope YAMLs (`pelvis`, `thorax`, `abdomen`, `thigh_R` and their `*_sections.csv`), report the skin radius or depth along the contact normal, and the depth inside the shell at the 5 mm shell of 0007 D4. Show the sensitivity to the other shell thicknesses the files carry.

**Occupants.** Name what already takes that depth. Read `data/envelope/reserved/pelvis.yaml`, `reserved/thorax.yaml`, `reservations.yaml` (the spine module) and `components/thigh_R.yaml` (the hip mechanism sits in the hip zone). If an occupant the zone must clear is not in a file, say so. Do not assume one.

**Two readings of room.** 0037 D2(c) says "radial depth the zone's structure can spare", and no record defines spare. Report both and let Joe pick:
- (a) depth inside the shell less the nearest named occupant;
- (b) depth inside the shell with nothing subtracted, an upper bound.

For each reading and each zone, give the lowest series cap whose s_res fits, or "none fits".

**Hand and arm.** Its stroke home is the shoulder girdle arc at the thorax-shoulder interface (0008 D6(c)). The room there is a swept clearance, not a radial depth. State whether `data/envelope/` can answer it today. If answering needs a new sweep tool or a method choice 0007 does not make, stop and report; do not build one. Where it can be answered, report fits at 45 mm and at 90 mm. Joe decides which cap enters, because 0008 D6(a) has 20 kN and the first-cap exception in D1(d) says the lowest value that fits, which would be 10 kN if 90 mm exists.

**Knee.** 0037 D4(b) puts 41.73 mm of depth inside the shell on the thigh outside the hip zone and none along the shin at its bottleneck. Report the knee region's depth at the contact station and say which segment's room the stroke would come from.

**Stale text.** 0037 D3 says the pelvis, thorax and arm envelopes are "not extracted", but their files now exist. Propose Amendments text that says so, and propose no change to any number.

**Output.** A memo with one table (zone, station, depth, occupant, remaining depth, lowest fitting cap under each reading, the claim released if that cap were taken) and draft Revisions entries in the form 0037's existing entries use: the change, the three D1(d) tests, the result. One entry per zone that could take a first cap, and none for a zone whose answer is "none fits" or "cannot be answered".

## T2. Welded effective mass and contact velocity (hold until released)

**The route.** 0037 D1(c): m_eff at the contact from the mass matrix with every joint welded, and v_n from the rigid-body fall, giving E_design = min(E_max, ½ m_eff v_n² + m g s_res).

**Topple models.** Reuse 0008 D5's rather than choosing new ones: a rigid body pivoting about a ground point, with its stated inputs. Forward about the toe; lateral about the outer foot edge; backward about the heel (0.062 m behind the ankle [source: snapshot foot_heel_behind_ankle]). Use the standing centre of mass of 0.942 m (0037 Revisions, 2026-10-31).

**The pose problem.** A welded straight body does not land hip, buttock, back or knee first. In a straight topple the first point to reach the floor is higher up. So for each zone the run states the pose at contact in which that zone is the contact, and bounds the pose family the way 0008 D5 bounds the arm's with its friction cone. If a welded body cannot reach the zone first within any bounded family, report that and leave E_design at E_max. For the knee, no welded topple reaches the floor on the knee; its energy stays the geometric drop of D3 and only m_eff at the knee is reported. Expect several zones to come out at E_max, which is a result.

**Method.**
- m_eff = (J M⁻¹ Jᵀ)⁻¹ along the contact normal, from the mass matrix and analytic Jacobians at the contact pose.
- v_n from passive rigid-body integration with no contact model. Read no contact force or contact flag from MuJoCo; 0036 bars soft-contact magnitudes.
- s_res depends on E, so start from D3's s_res as a conservative input, then report the fixed point.

**Self-check.** The same script, with 0008 D5's inputs, must reproduce its forward arm band (302 to 355 J straight down, 378 to 422 J at β = 45°, over the stated reach and stack bracket) within a few joules. D5's numbers were corrected twice (its Amendments of 2026-10-31) and 0008 D6(c) notes its backward check is not in a committed script, so this script closes that gap. A mismatch is a finding either way.

**Cross-check, report only.** Compare the hip m_eff with S1's 31 to 37.6 kg and the energy with its 212 to 257 J. This tests 0037's claim that a welded robot is stiffer than an active human. It is not a gate.

**Output.** An addition to the memo: m_eff, v_n, pose family and E_design per zone, plus draft Revisions entries only for zones where E_design falls below E_max.

## Gate criteria for T2

**G5.** The self-check above passes or the mismatch is explained.
**G6.** No contact solver, contact force or contact flag is used or read, shown by a test that fails if one is.
