"""
Stage 2e T5 (report only): the knee extension moment's tails. For A_filtered and for the dataset-direct row, both speeds and each exclusion set
(`all`, `without_offset`, `without_pitch_flagged`, the subject lists in the gait spec): the 95th percentile and the maximum of the stride-limb
extension peaks and their ratio; and the ten largest strides of A with the split of A minus the dataset-direct value at A's peak frame into force,
lever and inertia terms, the stance percent of the peak, the force at the peak, the effect of the 6 Hz filter on that stride (A_native over A_filtered
peak) and the subject's median A over dataset-direct ratio.

    python sim/scripts/gait_diag.py knee-tails [--speeds 1.4 1.6] [--workers 5]

Nothing here changes the model, the sheet, the mapping, the retargeting, a default or the band, and nothing is written to the repo. The per-stride
physics is `knee_gain.limb_series` (A_filtered exactly as `gait.run_stride` does it, split into its terms, beside the dataset's own).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gait  # noqa: E402

REPO = gait.REPO
TOP_N = 10  # the brief's "ten largest strides of A"
LOW_FORCE_BW = 0.10  # raw force under this many body weights: a frame where the plate's CoP is not reliable (the flag's first and last frames carry 20 to 30 N); a reading aid I chose, not a check's threshold
LOW_LOAD_BW = 0.5 # force at the peak frame below this many body weights counts as "low load" in the report (a reading aid, not a threshold of any check)


# ------------------------------------------------------------------------------ pure helpers

def exclusion_masks(subjects, offset, pitch) -> dict:
    """{name: boolean mask over `subjects`} for the three exclusion sets the gait record uses."""
    subs = np.asarray(list(subjects))
    return {"all": np.ones(len(subs), bool), "without_offset": ~np.isin(subs, list(offset)), "without_pitch_flagged": ~np.isin(subs, list(pitch))}


def extension_peak(tau) -> float:
    """Magnitude of the most negative (extension) moment of one stride-limb, zero if the moment is never negative."""
    return float(max(0.0, -np.min(np.asarray(tau, float))))


def peak_frame(tau) -> int:
    """Frame of the most negative moment."""
    return int(np.argmin(np.asarray(tau, float)))


def low_load_excluded_peak(tau, fz_raw, weight, frac) -> float:
    """Extension peak over the frames whose raw (dataset, scaled) vertical force is at least `frac` of body weight: a diagnostic of what the peak would be
    without the first and last frames of the force flag, where the plate's CoP is not yet or no longer defined. Zero if no frame qualifies."""
    tau, fz = np.asarray(tau, float), np.asarray(fz_raw, float)
    ok = fz >= frac * weight
    return float(max(0.0, -tau[ok].min())) if ok.any() else 0.0


def peak_is_low_load(tau, fz_raw, weight, frac) -> bool:
    """Whether the extension peak's own frame has raw vertical force below `frac` of body weight."""
    return bool(np.asarray(fz_raw, float)[peak_frame(tau)] < frac * weight)


def tail_row(peaks) -> dict:
    """n, 95th percentile, maximum and maximum over 95th percentile of a set of stride-limb peaks."""
    p = np.asarray(peaks, float)
    if len(p) == 0:
        return {"n": 0, "p95": None, "max": None, "ratio": None}
    p95 = float(np.percentile(p, 95))
    return {"n": int(len(p)), "p95": p95, "max": float(p.max()), "ratio": float(p.max() / p95)}


def stance_percent(flag, k) -> float:
    """Percent of the foot's stance, counted from its own heel strike, at frame k of the 100 unique frames; nan outside the stance."""
    import foot_pitch
    run = foot_pitch.stance_run(flag)
    if run is None:
        return float("nan")
    start, length = run
    j = (int(k) - start) % len(flag)
    return 100.0 * j / length if j < length else float("nan")


def frame_split(s, k) -> dict:
    """A minus the dataset-direct torque at frame k, N m, split as knee_gain's selection-free accounting does: each ground term is sign x force x lever
    with the sign +1 (vertical: Fz x (CoP minus knee, forward); horizontal: Fx x (knee height)), the force part is the force difference at the
    dataset's lever and the lever part the lever difference at A's force; inertia is A's distal weight and inertia minus the dataset's remainder; other
    is whatever the planar picture does not capture. `s` is a knee_gain.limb_series dict."""
    from knee_gain import force_lever_split
    vf, vl = force_lever_split(s["FzA"][k], s["FzD"][k], s["dxA"][k], s["dxD"][k], 1.0)
    hf, hl = force_lever_split(s["FxA"][k], s["FxD"][k], s["hA"][k], s["hD"][k], 1.0)
    total = float(s["tauA"][k] - s["tauD"][k])
    inertia = float(s["inA"][k] - s["inD"][k])
    other = total - float(vf + vl + hf + hl) - inertia
    return {"total": total, "vert_force": float(vf), "vert_lever": float(vl), "horiz_force": float(hf), "horiz_lever": float(hl), "inertia": inertia,
            "other": other, "force": float(vf + hf), "lever": float(vl + hl)}


def carrier(split) -> str:
    """Which of force, lever and inertia has the largest magnitude in the split."""
    return max(("force", "lever", "inertia"), key=lambda k: abs(split[k]))


def subject_median_ratio(rows) -> dict:
    """{subject: median of peakA / peakD over its stride-limbs}."""
    by = {}
    for r in rows:
        by.setdefault(r["subject"], []).append(r["peakA"] / r["peakD"])
    return {k: float(np.median(v)) for k, v in by.items()}


# ------------------------------------------------------------------------------ the report

def _rows(speed, workers, native=False):
    import json
    import knee_gain
    c = gait._ctx(gait.simrun.MODEL_FILE)
    manifest = json.loads((REPO / "data" / "camargo2021" / "manifest.json").read_text(encoding="utf-8"))
    S_list = knee_gain.run_knee(speed, workers, native_force=native)
    series = [knee_gain.limb_series(S, side, c, manifest) for S in S_list for side in ("right", "left")]
    return c, series


def report(args):
    spec = gait.load_spec("walk_treadmill")
    offset, pitch = spec["offset_subjects"], spec["pitch_flag_subjects"]
    for speed in args.speeds:
        c, series = _rows(speed, args.workers)
        _, native = _rows(speed, args.workers, native=True)
        subj = [s["subject"] for s in series]
        pA = np.array([extension_peak(s["tauA"]) for s in series])
        pD = np.array([extension_peak(s["tauD"]) for s in series])
        pN = np.array([extension_peak(s["tauA"]) for s in native])
        masks = exclusion_masks(subj, offset, pitch)
        print(f"\n=== {speed} m/s: {len(series)} stride-limbs; knee extension moment of the stride (N m), A_filtered and the dataset-direct row scaled to Freyja ===")
        print("exclusion set           n     A p95    A max   A max/p95 | dataset p95  max  max/p95 | A_native p95   max   | A p95 over dataset p95")
        for name, m in masks.items():
            a, d, n_ = tail_row(pA[m]), tail_row(pD[m]), tail_row(pN[m])
            print(f"  {name:22s} {a['n']:4d} {a['p95']:8.1f} {a['max']:8.1f} {a['ratio']:9.2f} | {d['p95']:11.1f} {d['max']:6.1f} {d['ratio']:8.2f} | {n_['p95']:10.1f} {n_['max']:7.1f}   | {a['p95'] / d['p95']:.2f}")
        # the same peaks without the frames whose raw force is under LOW_FORCE_BW of body weight (a diagnostic, not a fix)
        pAx = np.array([low_load_excluded_peak(s["tauA"], s["FzD"], c.weight, LOW_FORCE_BW) for s in series])
        low = np.array([peak_is_low_load(s["tauA"], s["FzD"], c.weight, LOW_FORCE_BW) for s in series])
        print(f"  A's peak frame has raw force under {LOW_FORCE_BW:.2f} BW in {low.sum()} of {len(series)} stride-limbs ({100 * low.mean():.1f}%; subjects {sorted({s['subject'] for s, l in zip(series, low) if l})}); "
              "A without those frames (every exclusion set): " + "; ".join(f"{name} p95 {tail_row(pAx[m])['p95']:.1f} max {tail_row(pAx[m])['max']:.1f}" for name, m in masks.items()))
        med = subject_median_ratio([dict(subject=s, peakA=a, peakD=d) for s, a, d in zip(subj, pA, pD)])
        order = np.argsort(-pA)[:TOP_N]
        print(f"the {TOP_N} largest extension peaks of A: subject, stride, limb, stance % of the peak, A peak, dataset-direct peak (same stride), dataset-direct at A's peak frame, "
              "split of (A - dataset) at that frame [force | lever | inertia | other], carrier, Fz at the peak (body weights; A / dataset), A_native / A_filtered peak, subject median A/dataset")
        for r, i in enumerate(order, 1):
            s = series[i]
            k = peak_frame(s["tauA"])
            sp = frame_split(s, k)
            pct = stance_percent(s["stance_d"], k)
            bw = c.weight
            print(f"  {r:2d} {s['subject']} stride {s['index']:3d} {s['side']:5s} {pct:5.1f}% {pA[i]:7.1f} {pD[i]:7.1f} {-s['tauD'][k]:7.1f} | {sp['force']:+6.1f} {sp['lever']:+6.1f} {sp['inertia']:+6.1f} {sp['other']:+6.1f} {carrier(sp):7s} | "
                  f"{s['FzA'][k] / bw:4.2f} / {s['FzD'][k] / bw:4.2f} | {pN[i] / pA[i]:5.3f} | {med[s['subject']]:.2f}")
        top = [series[i] for i in order]
        cnt = {}
        for s in top:
            cnt[s["subject"]] = cnt.get(s["subject"], 0) + 1
        splits = [frame_split(s, peak_frame(s["tauA"])) for s in top]
        carriers = [carrier(x) for x in splits]
        print(f"  top {TOP_N}: subjects {dict(sorted(cnt.items(), key=lambda kv: -kv[1]))}; carriers {carriers.count('lever')} lever, {carriers.count('force')} force, "
              f"{carriers.count('inertia')} inertia; Fz at the peak below {LOW_LOAD_BW} BW: {sum(1 for s in top if s['FzA'][peak_frame(s['tauA'])] / c.weight < LOW_LOAD_BW)}; "
              f"median A_native/A_filtered over the top {TOP_N} {np.median(pN[order] / pA[order]):.3f}, over every stride-limb {np.median(pN / pA):.3f}")
        allsub = sorted(med.items(), key=lambda kv: -kv[1])
        print("  subjects' median A/dataset peak ratio, all: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(med.items())) + f"; median over subjects {np.median([v for _, v in allsub]):.2f}")
