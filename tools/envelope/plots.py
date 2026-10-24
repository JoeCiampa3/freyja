"""Silhouette plots of a segment: sagittal and coronal projections with a scale grid and the inner envelopes overlaid."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import field  # noqa: E402

COLORS = {0.0: "#222222", 3.0: "#1f77b4", 5.0: "#2ca02c", 8.0: "#ff7f0e", 10.0: "#d62728"}   # shell thickness -> outline colour


def _projection(seg: field.Segment, axis: int):
    """The segment's signed distance collapsed along `axis` by the maximum over the region (1 for the sagittal view, 0 for the coronal): its
    level set at t is the silhouette of the inner envelope {sd >= t}."""
    return np.where(seg.region, seg.sd, -1e3).max(axis=axis)


def silhouette_png(seg: field.Segment, path, view: str, shells, title: str, side: str = "right"):
    """view 'sagittal' (look along y: x horizontal, anterior to the right) or 'coronal' (look along x: y horizontal, medial to the right
    for the right thigh)."""
    if view == "sagittal":
        axis, hax, hlabel = 1, 0, "x, anterior (mm)"
    else:
        axis, hax = 0, 1
        hlabel = "y, medial (mm)" if side == "right" else "y, lateral (mm)"
    H = seg.centres(hax)
    Z = seg.centres(2)
    fig, ax = plt.subplots(figsize=(5.2, 9.2), dpi=110)
    proj = _projection(seg, axis)                         # shape (n_h, nz)
    for t in shells:
        ax.contour(H, Z, proj.T, levels=[t], colors=[COLORS.get(t, "k")], linewidths=1.6 if t == 0 else 1.0)
    ax.plot([0, 0], [0, -seg.length], color="k", lw=0.8, ls="--")
    ax.axhline(0, color="0.5", lw=0.8)
    ax.axhline(-seg.length, color="0.5", lw=0.8)
    for s in np.arange(0, seg.length + 1, 50):
        ax.text(H.min(), -s, f"{s:.0f}", fontsize=7, va="center", ha="left", color="0.35")
    ax.set_xlabel(hlabel)
    ax.set_ylabel("z (mm); stations measured down from the hip centre")
    ax.set_aspect("equal")
    ax.set_xlim(H.min(), H.max())
    ax.set_ylim(-seg.length - 25, 25)
    ax.set_xticks(np.arange(np.ceil(H.min() / 50) * 50, H.max() + 1, 50))
    ax.set_xticks(np.arange(np.ceil(H.min() / 10) * 10, H.max() + 1, 10), minor=True)
    ax.set_yticks(np.arange(-np.floor(seg.length / 50) * 50, 1, 50))
    ax.set_yticks(np.arange(-np.floor(seg.length / 10) * 10, 1, 10), minor=True)
    ax.grid(which="major", color="0.75", lw=0.7)
    ax.grid(which="minor", color="0.9", lw=0.4)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], color=COLORS.get(t, "k"), lw=1.6 if t == 0 else 1.0, label="skin" if t == 0 else f"inner t={t:g} mm") for t in shells],
              loc="lower right", fontsize=7)
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, metadata={"Software": None})
    plt.close(fig)
