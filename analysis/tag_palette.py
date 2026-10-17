"""
Display colours for the roadmap tag vocabulary (roadmap/tags.yaml): the colour arithmetic the colours are checked with, and the search that
produced them.

    python analysis/tag_palette.py            # prints the chosen colours as YAML, region then phase

What the colours must satisfy (the constants below are the design goals, fixed before the search ran and never tuned toward its result):

- Each colour keeps at least CONTRAST_MIN : 1 against all four backgrounds the viewer draws on (light --bg and --panel, dark --bg and
  --panel; tools/roadmap/viewer/index.html). 3 : 1 is WCAG 2.1 success criterion 1.4.11 for graphical objects. So one hex works in both
  themes, and the search only needs mid-luminance colours.
- Within a namespace, and against the neutral grey the viewer uses for "no tag", every pair stays at least DELTA_E_MIN apart (CIE76 Delta E
  in CIELAB, D65), under normal vision and under simulated protanopia, deuteranopia and tritanopia (Machado, Oliveira and Fernandes 2009,
  severity 1.0, applied to linear sRGB). Delta E 76 of about 10 or more is a plainly visible difference at a glance.

Colour never carries meaning alone: the viewer shows the value in a legend, in the drawer and in hover text, and status stays in the marker
shape. The search is deterministic (seeded) and has no dependency beyond the standard library.
"""
from __future__ import annotations

import itertools
import math
import random

BACKGROUNDS = ("#fafaf8", "#ffffff", "#161614", "#1f1f1c")  # light --bg, light --panel, dark --bg, dark --panel
NEUTRAL = "#8c8c88"  # what a node without the chosen namespace's tag is drawn in (the viewer's --c-untagged)
CONTRAST_MIN = 3.0  # WCAG 2.1 1.4.11, graphical objects
DELTA_E_MIN = {"phase": 20.0, "region": 12.0}  # per namespace: 6 values can be far apart, 14 cannot; both under all four visions
SEED = 20261017

# Machado, Oliveira and Fernandes (2009), severity 1.0, rows act on linear RGB
CVD = {
    "normal": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def parse_hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb) -> str:
    return "#" + "".join(f"{round(min(1, max(0, c)) * 255):02x}" for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear(rgb) -> tuple:
    return tuple(_lin(c) for c in rgb)


def luminance(h: str) -> float:
    r, g, b = linear(parse_hex(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lab(h: str, mode: str = "normal") -> tuple:
    """CIELAB (D65) of the colour as seen under `mode`."""
    m = CVD[mode]
    r, g, b = linear(parse_hex(h))
    r, g, b = (max(0.0, min(1.0, sum(m[k][j] * (r, g, b)[j] for j in range(3)))) for k in range(3))
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: str, b: str, mode: str = "normal") -> float:
    return math.dist(lab(a, mode), lab(b, mode))


def separation(a: str, b: str) -> float:
    """The smallest Delta E of the pair over normal vision and the three simulated deficiencies."""
    return min(delta_e(a, b, m) for m in CVD)


def min_contrast(h: str) -> float:
    return min(contrast(h, bg) for bg in BACKGROUNDS)


def min_separation(colours) -> float:
    return min((separation(a, b) for a, b in itertools.combinations(colours, 2)), default=math.inf)


def search(n: int, fixed=(NEUTRAL,), seed: int = SEED, pool: int = 6000, rounds: int = 4) -> list:
    """n colours that keep CONTRAST_MIN on every background and maximise the smallest pairwise separation, also from `fixed`. Greedy max-min
    over a seeded pool of candidates, then `rounds` passes in which each colour is swapped for the pool member that raises the minimum."""
    rng = random.Random(seed)
    cands = []
    while len(cands) < pool:
        h = to_hex((rng.random(), rng.random(), rng.random()))
        if min_contrast(h) >= CONTRAST_MIN and h not in cands:
            cands.append(h)
    sep = {}

    def d(a, b):
        k = (a, b) if a < b else (b, a)
        if k not in sep:
            sep[k] = separation(a, b)
        return sep[k]

    chosen = []
    while len(chosen) < n:
        best = max(cands, key=lambda c: (min([d(c, o) for o in (*fixed, *chosen)] or [math.inf]), c))
        chosen.append(best)
    for _ in range(rounds):
        for i in range(n):
            rest = [*fixed, *chosen[:i], *chosen[i + 1:]]
            chosen[i] = max(cands, key=lambda c: (min(d(c, o) for o in rest), c))
    return chosen


def main():
    for name, values in (("phase", ["spec", "sim", "design", "fab", "bench", "integrate"]),
                         ("region", ["head", "neck", "torso", "spine", "pelvis", "arm-l", "arm-r", "hand-l", "hand-r", "leg-l", "leg-r", "foot-l", "foot-r", "whole-body"])):
        colours = search(len(values))
        print(f"# {name}: smallest separation {min_separation([*colours, NEUTRAL]):.1f} (goal {DELTA_E_MIN[name]}), smallest contrast {min(map(min_contrast, colours)):.2f}")
        for v, c in zip(values, colours):
            print(f"{v}: \"{c}\"")


if __name__ == "__main__":
    main()
