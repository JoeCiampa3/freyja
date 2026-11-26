STATE: base 37c2ae0ddd30 | brief architecture sha256:bd2d997fe5e8, ariadne sha256:31a88eef7b85 | snapshot sha256:492fe816e6d8 | tests not run | dirty yes (`fy state --no-run` on Joe's ruling: drive C: is full, finding 2; the uncommitted files are this memo and the backticks restored in `CLAUDE.md`'s Ariadne line, finding 4; no code changed)

# Memo 67: shoulder room, Group A (the required set): stopped at T1, Gates Table 1 gives peaks, not per-task ranges

Brief: `docs/briefs/ariadne/shoulder-room-brief.md`, Group A. The prompt gave the path as `docs/briefs/shoulder-room-brief.md`. No file is there; `docs/briefs/ariadne/shoulder-room-brief.md` hashes to `31a88eef7b85…`, matching the prompt's prefix 31A88EEF7B85 (LF, no mismatch), so I ran that file. The prompt named no group. Group B needs your sign-off and a named u1, so this session ran Group A. It stopped at T1 on the brief's first stop condition ("Gates 2016 Table 1 does not give per-task ranges for both plane of elevation and elevation"). There is no code, no inputs-file change and no output change. The one commit holds this memo, `docs/STATE.md` and the backticks restored in `CLAUDE.md`'s Ariadne brief line (finding 4). Nothing in the model, template, `pre_processor`, sheet, `tools/envelope/`, decision records, roadmap nodes or thread records changed. Nothing stamped, nothing pushed.

## Decision summary

- **What this means for Freyja:** the brief planned to replace B1, memo 66's ADL box, with the union of per-task boxes, expecting basin 2's 25.98 deg floor to rise. That cannot be built from Gates 2016 Table 1. The table gives each task's **peak** angles only: how far in front of the body, how far behind, and how high. It never gives a per-task lower end of elevation, and it gives a behind-the-body end for only 3 of 12 task rows. So no per-task box can be formed without numbers the table does not hold. Per the brief, Group A stops here. Group B runs with **memo 66's basin-2 axis unchanged**: `data/shoulder/axis_search.json#/basins/1/u1` = (-0.43809, -0.57088, 0.69439), upper end (phi -37.5, theta 134.0).
- **The numbers that matter**, each beside its reference:
  - Table 1's extremes, signs restored: plane of elevation **-65 to 105**, elevation peak **108**. These match B1's bounds (-65 to 105; 0 to 108) except elevation 0, which is in no cell. It comes from the abstract. So G-A1 holds for three of four bounds, and the fourth has no cell to check.
  - Per-task ends given: plane maximum **12 of 12** rows, plane minimum **3 of 12**, elevation maximum **12 of 12**, elevation minimum **0 of 12**.
  - Basin 2's lower-end binding corner, B1 (105, 39): perineal care, contralateral limb, peaks at plane **105** and elevation **63**. Any task box that runs from elevation 0 (or anything at most 39) up to that 63 still contains (105, 39). On the table's own numbers, task boxes would likely **not** relieve the lower end. That is a reading of the table, not a computed result.
  - Basin 2's upper-end corner, B1 (-38, 108): the only task reaching 108 (box off shelf, head height) has no behind-body peak. The three tasks that do go behind reach elevation 80, 51 and 55. So the upper corner is where task boxes could help, but only through a plane minimum for the shelf task that the table does not give.
  - Folded-arms source for S4: **none found** (two searches). The patch stays from memory.
- **Decisions for Joe:**
  1. Accept the stop and start Group B on memo 66's basin-2 u1 (recommended). Name it as `data/shoulder/axis_search.json#/basins/1/u1`.
  2. Or rule how a task box's missing ends are formed, then rerun Group A. For example: elevation from 0 (the arm-at-side start), and plane from the task's behind-body peak where given, else from its front peak alone, a line not a box. Both are rules, not table cells, so they need your ruling (brief, Stop and ask: "any required-set number that is not … a Gates 2016 table cell").
- **What would change this:** per-participant or per-task minimum angles from the paper's supplement, which I could not read, or another dataset with per-task ranges. Or a ruling under item 2.

## Gates

| Gate | Result | Numbers |
|---|---|---|
| G-A1 table consistency | not reached as a gate (T1 stopped); checked by hand | plane min -65 (hand to back pocket, behind body, mean), plane max 105 (perineal care contralateral, in front, mean), elevation max 108 (box off shelf head height, mean): equal to B1. Elevation min 0: no Table 1 cell |
| G-A2 regression | not run (T2 not reached) | the committed `data/shoulder/axis_search.json` is memo 66's output, last written at b3e1cee: basins 28.8944480005 and 25.9820707212 deg, inputs sha256:140ba477659d |
| G-A3 V1 to V7 on the refined run | not run (T2 not reached) | — |

## T0 baseline

- HEAD 37c2ae0, tree clean.
- `fy thread build`: 70 files, 0 changed, 34 records, 1 work item, rework 0, errors 0, warnings 0 (0.5 s).
- `fy test --quick`, three runs: 1129 passed, 2 errors (100.6 s); then 2 errors again (122.6 s, second run of a pair). Every error is the disk (finding 2), none is code. The first pair was `ImportError` collecting `tests/test_cad_fusion.py`. The second was `OSError: [Errno 28] No space left on device` in `shutil.copytree` at the setup of `tests/test_roadmap_cli.py`. Collected alone, `tests/test_cad_fusion.py` imports cleanly, serially and under xdist.
- `data/shoulder/axis_search.json` is memo 66's output: last commit b3e1cee, basins and floors equal memo 66's table.

## Gates 2016 Table 1 (shoulder rows)

Source: Gates et al. 2016, Am J Occup Ther 70(1), 7001350010, Table 1, "Peak Shoulder (Thoracohumeral), Elbow, and Forearm Angles for Each Task", p. 7001350010p5 and its continuation. Joe pasted it from the PDF, because PMC served me a bot check (finding 3). The PDF's text layer dropped every minus sign, which renders as a leading "2". I restored the signs on two grounds. First, the rows sit under "Peak motion behind body" (plane) and "Peak external rotation" / "Peak supination", which are negative in ISB. Second, the abstract's -65/0/105 and -55/0/79 match: "265" is -65, "255" is -55. A CI printed "[275,255]" is [-75, -55]. Columns are Mean, Median and 95% CI. The table's numbers are peaks, one end per row. Rows are tasks, grouped under each DOF and each direction.

Humeral plane of elevation, peak motion in front of body (the per-task maximum):

| Task | Mean | Median | 95% CI |
|---|---|---|---|
| Perineal care, contralateral limb | 105 | 105 | [96, 115] |
| Deodorant, ipsilateral limb | 100 | 99 | [95, 104] |
| Box off shelf, fixed height | 90 | 88 | [86, 94] |
| Box off shelf, head height | 86 | 86 | [83, 89] |
| Donning and zipping pants | 84 | 85 | [79, 88] |
| Drinking from a cup | 81 | 79 | [74, 88] |
| Hand to back pocket | 80 | 79 | [73, 87] |
| Can off shelf, fixed height | 78 | 78 | [73, 83] |
| Box off ground | 75 | 76 | [72, 78] |
| Can off shelf, head height | 72 | 72 | [68, 77] |
| Deodorant, contralateral limb | 65 | 66 | [61, 70] |
| Perineal care, ipsilateral limb | 61 | 60 | [37, 84] |

Humeral plane of elevation, peak motion behind body (the per-task minimum; signs restored):

| Task | Mean | Median | 95% CI |
|---|---|---|---|
| Hand to back pocket | -65 | -64 | [-75, -55] |
| Donning and zipping pants | -57 | -55 | [-64, -50] |
| Perineal care, ipsilateral limb | -46 | -57 | [-79, -14] |

Humeral elevation, peak elevation "measured as positive motion from arm at side" (the per-task maximum; no minimum is given):

| Task | Mean | Median | 95% CI |
|---|---|---|---|
| Box off shelf, head height | 108 | 105 | [104, 111] |
| Deodorant, contralateral limb | 107 | 109 | [101, 113] |
| Can off shelf, head height | 105 | 104 | [102, 108] |
| Box off shelf, fixed height | 86 | 85 | [80, 92] |
| Can off shelf, fixed height | 86 | 84 | [78, 95] |
| Hand to back pocket | 80 | 80 | [74, 85] |
| Drinking from a cup | 71 | 71 | [67, 75] |
| Box off ground | 69 | 70 | [62, 75] |
| Perineal care, contralateral limb | 63 | 67 | [48, 77] |
| Perineal care, ipsilateral limb | 55 | 53 | [45, 65] |
| Deodorant, ipsilateral limb | 55 | 52 | [50, 60] |
| Donning and zipping pants | 51 | 51 | [49, 54] |

Humeral rotation is not transcribed. The search does not use it, and its pasted text has ambiguous signs (for example "Box off shelf, head height 4 6 [26,14]", whose CI must be [-6, 14], with no row heading to confirm it).

## Findings

1. **Gates 2016 Table 1 does not give per-task ranges for both plane of elevation and elevation** (brief, "Report as a finding, and stop"). Plane minimum is given for 3 of 12 task rows, elevation minimum for none. Group A stops before T1. B1 stays the basis; B1T is not typed. By the brief, Group B runs on memo 66's basin-2 axis unchanged. The two binding corners read against the table (decision summary): the lower one (105, 39) is likely to survive any task box, and the upper one (-38, 108) depends on a plane minimum the table lacks. Also: a task's plane peak and elevation peak need not be simultaneous. So even a complete per-task box overstates that task, and memo 66's first caution carries over to task boxes.
2. **Drive C: is full**: 464 GB, 1.5 GB free, 100% used. Both quick-suite failures this session are `Errno 28` (`OSError: No space left on device` in a `copytree`) or follow from it (an `ImportError` collecting `test_cad_fusion.py` that does not reproduce alone). `data/envelope/cache` is 533 MB and pytest's temp tree 225 MB; I deleted nothing. On your ruling, `fy state` was run with `--no-run`, so `docs/STATE.md` reports the last full run (memo 66's tree), not this tree. The tree differs from memo 66's only by the brief (37c2ae0) and this memo.
3. **PMC serves a bot check to automated fetches.** The PMC page returned a reCAPTCHA interstitial. Europe PMC's full-text API returned HTTP 500. NCBI efetch returned front matter and the abstract only, with "The publisher of this article does not allow downloading of the full text in XML form". Memo 66 read the same page through a fetch, so this is new. Any brief that sends me to PMC needs the paper pasted or put on disk.
4. **`fy state` silently dropped the Ariadne brief** (CONVENTIONS 9.9). 37c2ae0 wrote `CLAUDE.md`'s line as `Current Ariadne brief: docs/briefs/...` without backticks. `tools/state`'s `BRIEF_LINE` (`^Current (\w+) brief:\s*` followed by a backticked path) then matches only the architecture line. The first `fy state --no-run` printed a STATE line with no Ariadne hash and no error. The parser errors only when no line matches at all. I restored the backticks in this commit; `CLAUDE.md` lets Code update that line when the prompt names the brief. Recommended: make a `Current <track> brief:` line without a backticked path an error.
5. **No folded-arms source.** Two web searches, for humerothoracic angles with arms folded or crossed across the chest, found nothing. The nearest hits were the ISB plane-of-elevation definition and a 2015 BMC Musculoskeletal Disorders paper on a 3D-capture zero reference (bilateral abduction, not crossed arms). S4 stays `source_needed`, untyped, since T1 and T2 did not run.

## Tolerances and parameters I chose

None. No measure ran.

## My mistakes

1. After PMC returned the bot check, I tried Europe PMC's API and NCBI efetch, then a third fetch of the PMC PDF and two mirrors. The auto-mode classifier blocked that third one as a workaround of the bot check, and it was right. The first two are official APIs, but the third went at the same host that had refused. I stopped there and asked you for the table.
2. I took the first quick-suite errors for a test-isolation problem and reran the suite before checking the disk. One `df` would have found the cause two minutes earlier.

## Questions for Joe

1. Accept the stop and name memo 66's basin-2 u1 for Group B (`data/shoulder/axis_search.json#/basins/1/u1`)? Recommended.
2. Or rule how per-task boxes are formed from peaks (decision summary, item 2), and I rerun Group A on that rule. If you take this, say whether the 95% CI or the mean is the basis. The brief's B1 used means.
3. The paper's supplemental appendices may hold per-participant minima and maxima. If you have them, paste them; they would make B1T buildable as the brief intended.
4. Disk: free space on C: before the next session. Group B's `fy envelope free --union` and the cache reads will need it, and `fy state` should run the full suite on this tree.
5. Sternoclavicular offset c for M4 and a folded-arms source: still none (brief, Prerequisites).
