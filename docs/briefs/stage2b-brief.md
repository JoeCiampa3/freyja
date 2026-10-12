# Stage 2b brief (for Claude Code): close-out checks, a tracked gait extract and the trunk wording

Read `CLAUDE.md`, `CONVENTIONS.md`, `docs/OVERVIEW.md`, `docs/memos/memo5-stage2-t3c.md` and `docs/memos/memo6-stage2-close.md`, then the Decisions block of `docs/briefs/stage2-brief.md`. Stage 2 is closed; this brief does not reopen it. It does three things: checks two numbers from `memo6` that I do not believe yet, makes the gait results reproducible from a clean clone, and brings the wording about the trunk and about B into line with what was measured.

## Ground rules

CONVENTIONS section 9 and `CLAUDE.md` apply. Tests first, one commit per task, files staged by explicit path, every multi-line edit made with the editor tool and confirmed from the file before committing. While iterating run only the affected test file; run the full suite once before each commit. Stop and ask before changing the model, the sheet, the template, any default, the retargeting or a band. Report numbers that contradict this brief and stop.

The work is two sessions. **Session 1: T1, T2, T4, then `docs/memos/memo7-stage2b-checks.md`, `fy state`, stop.** Joe reads the memo and starts **session 2: T3, T5, then `docs/memos/memo8-stage2b-close.md`, `fy state`, stop.** If T1 finds a mapping or offset error, stop after T1 and report it, because T2 and T3 would then rest on it.

## Decisions (Joe confirms by committing this brief; each line is a one-line revert if he disagrees)

- **Spine plan (not final).** v1 builds a multi-DOF spine for articulation and locks it during gait. The lumbosacral joint may instead stay unlocked and actuated for basic balance during gait, with a fully rigid torso as the fallback if control complexity balloons. The three trunk modes are named for what they model: `rigid` is a locked spine; `counter_rotate` is an actuated lumbosacral roll and yaw cancelling the pelvis's roll and yaw by feed-forward; `first_harmonic` is a human-like reference point from the trunk IMU (a diagnostic, never a record mode). No mode is the v1 headline until Joe decides. This supersedes the Stage 2 Trunk bullet's statement that `counter_rotate` is the headline for B and H's lateral and yaw rows; the record keeps both modes, and every row that depends on the trunk names its mode. Balance feedback through the trunk is the controller project's, not modelled here.
- **B's failure stands as a finding, with its attribution softened.** B fails the band, the polygon test and the dataset's moments. The unexplained part of its 66 mm backward CoP offset is unattributed: segment masses explain about 18 mm, the trunk-group placement none (T9.2), and a trunk lean cannot account for it at about 3 mm of whole-body CoM per degree. Do not describe it as a property of Freyja's mass distribution, her foot or the controller project. The control experiment (B's CoP computed on the dataset's own model) is parked.
- **Toe.** The dataset's own foot is toeless (`mtp_angle` exactly 0). No proxy load is built from the force plate. `decisions/0001-toe-joint.md` stays `proposed`; cited literature values will be supplied by Joe and the planning session, not by Code.
- **Band, flags, schema.** The envelope band is not widened. The pitch-flag rule (5 degrees, either speed) stays. `gait-summary/1` may be amended in place only while no instance of it is tracked; the extract in T3 is the first tracked instance and has its own schema from the start.
- **`pose.com_x_rel_ankle_m`.** No dataset carries a quiet-standing CoP. The default 0.0 stays and is described as a design choice (ankle torque near zero, heel margin 41 mm), not as an uncited measurement. A comment changes; the value does not.

## T1. Hip extension sanity (report only)

`memo6` reports peak hip extension beyond the model's 18.1 degree stop in 85% and 98% of strides, with a 95th percentile of 36.8 and 36.2 degrees. From memory, level walking at these speeds is about 15 to 25 degrees, so this is about double what I expect, and it must not go into the Joint ROM sheet until it is explained. Report, per speed:

(a) from the raw dataset's inverse kinematics, before any retargeting, the per-stride peak hip extension (state the sign convention) as median, 95th percentile and maximum;
(b) the same quantity from the retargeted joint angles in the cycles the gait record uses;
(c) the difference per subject, and whether it is a constant offset;
(d) the hip angle in the dataset's static trial against Freyja's `stand_static` hip angle;
(e) the same extremes for knee flexion and ankle plantarflexion, to see whether the offset is hip-specific.

If (c) shows a constant offset or a mapping error, stop and report the number; change nothing.

## T2. The ankle number

`A_filtered` gives a 95th-percentile peak ankle torque of 149 to 164 N m at 1.4 m/s and 158 to 169 N m at 1.6 (maxima up to 202 N m). Joe's frozen ankle spec is about 103 N m, a Winter mean of 1.58 N m/kg times 65 kg, lever-corrected; it lives in the sizing documents and not in this repo, so do not look for it. The two are different statistics at different speeds. For `A_filtered`'s sagittal hip, knee and ankle rows, per speed and limb, report the peak torque as mean, median, 95th percentile and maximum, in N m and in N m per kg of Freyja's mass. Beside it report the dataset's own peak moment in N m per kg of subject mass (mean, median, 95th percentile, maximum, all 17 subjects). State the ratio of the two per kg figures and the scaling rule used (force by the mass ratio, lever arms by the leg-length ratio), so Joe can see whether any excess over the dataset is scaling.

## T4. Gain or shape for the off-band stems

Hip ab/adduction and hip rotation sit just outside the band for `A_filtered` (0.97 / 18% and 0.86 to 0.88 / 16 to 17%). Report, per speed, the ordinary-least-squares slope and intercept of A's moment against the dataset's (pooled over limbs and subject-strides), the RMS after removing the best-fit gain, and the peak difference in N m per kg. A slope away from 1 with a high correlation is a gain error; a slope near 1 is a shape error. Do not change the band and do not admit the rows.

After T4: write `docs/memos/memo7-stage2b-checks.md` (T1, T2, T4, with every tolerance and every question for Joe), run `fy state`, and stop.

## T3. A tracked gait extract (session 2)

`ENVELOPE.md`'s gait section reads an untracked `gait.json` and cannot be regenerated from a clean clone. Write `sim/benchmarks/gait_extract.json`, generated by `fy gait` and tracked, holding exactly what `ENVELOPE.md` and the baseline need: per speed, trunk mode, method and joint the statistics now printed (torque, power, regeneration and speed, 95th percentile and maximum, `A_native`'s maximum, correlation, RMS, flags, band verdicts, stride and subject counts, the three exclusion sets), plus the lumbosacral lateral and axial rows for all three trunk modes (`rigid`, `counter_rotate` and the `first_harmonic` reference point at the T3c.2 median gain and lag, with the quartile corners as the spread), computed by the same code `gait_diag.py harmonic` uses, moved into a pure function. Stamp it as `walk_reference.json` is stamped, and give it its own schema `gait-extract/1` in `docs/schemas/`. `fy runs envelope` reads the extract, not `gait.json`. Amend CONVENTIONS section 2 (the extract's row) and section 6 (`gait-extract/1`) in the same commit and say so.

Tests first: a synthetic extract produces the expected envelope text; the extract is byte-identical on a second run; changing one value in the extract changes the envelope (mutation); the harmonic rows equal the diagnostic's numbers to 1e-9 (lateral torque 95th percentile 32.1 and 40.7 N m at 1.4 and 1.6 m/s in `memo6`); the extract validates against its schema. Then verify from a clean clone that `fy runs envelope` reproduces the tracked `ENVELOPE.md` byte for byte, and say so in the memo. The envelope's lumbosacral rows show all three modes.

## T5. Wording and housekeeping (session 2)

(a) Find every generated or authored text that attributes B's failure to Freyja's mass distribution, her foot or the controller project (search the generators in `gait.py` and `runs_report.py`, `GAIT.md`, `ENVELOPE.md`, the READMEs and `decisions/0001-toe-joint.md`) and reword it to the Decisions' statement. Change the generators, not the generated files. (b) Describe the three trunk modes as in the Decisions where `rigid` and `counter_rotate` are first explained in generated text. (c) Change the comment on `pose.com_x_rel_ankle_m` as the Decisions say; not the value. (d) Add a `.gitattributes` with `* text=auto eol=lf`. Do not run a renormalisation; report how many tracked files it would change (`git add --renormalize --dry-run .`) and let Joe decide. (e) Update `CLAUDE.md`'s "Current brief" line to this brief.

After T5: write `docs/memos/memo8-stage2b-close.md`, run `fy state`, and stop.

## Done when

Session 1 ends with `memo7`, session 2 with `memo8`; each opens with the STATE line, names every tolerance chosen and why, owns every mistake, and lists the questions for Joe. All suites green offline, `git status` clean, no raw data tracked.
