"""Generate the temporal-alignment diagrams for the user guide.

Run from the repository root::

    python docs/_static/images/generate_time_alignment_figures.py

This regenerates three figures in this directory, all in one consistent style:

- ``time_alignment_coarse.png``    - coarse alignment: a whole stream slid onto a reference clock.
- ``time_alignment_fine.png``      - fine alignment: every sample placed at its true reference time.
- ``time_alignment_timebases.png`` - a multi-timebase interface, showing that ``shift_times`` moves the
  whole interface relative to another interface (its clocks stay locked), while ``set_timebase_origin``
  moves one of its clocks (the internal offset changes).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

BLACK = "black"
RED = "firebrick"
REF = "#2f6f9f"  # a distinct colour for the reference / "other" interface
TICK_H = 0.16
OUTDIR = Path(__file__).parent


def timeline(ax, *, y, ticks, label, color=BLACK, label_x=None, show_time=True):
    """Draw one clock: a baseline with vertical sample ticks, a left label, and a 'time' cap.

    ``label_x`` overrides where the (right-aligned) label sits, so several rows can share a label
    column; ``show_time`` toggles the italic 'time' cap at the right end.
    """
    ticks = np.asarray(ticks, dtype=float)
    x0, x1 = ticks[0], ticks[-1]
    ax.hlines(y, x0, x1 + 0.4, color=color, lw=3)
    ax.vlines(ticks, y, y + TICK_H, color=color, lw=1.5)
    ax.text(label_x if label_x is not None else x0 - 0.3, y + TICK_H / 2, label, ha="right", va="center", fontsize=12, color=color)
    if show_time:
        ax.text(x1 + 0.6, y, "time", ha="left", va="center", fontsize=9, style="italic")


def clean(ax, *, xlim, ylim, title):
    """Apply the shared panel styling: a left-aligned title, fixed limits, and no axes."""
    ax.set_title(title, fontsize=12, loc="left", pad=6)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


def build_coarse():
    """Coarse alignment: the camera's internal spacing is right; only its placement is unknown."""
    reference = np.arange(0, 11, 1.0)
    camera = np.arange(0, 6, 1.0)
    offset = 3.0  # the recording places the camera's start at t = 3.0

    fig, axes = plt.subplots(2, 1, figsize=(9, 4.6))

    ax = axes[0]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=camera, label="camera")
    ax.annotate("", xy=(offset, 1.0), xytext=(0.0, TICK_H), arrowprops=dict(arrowstyle="->", color=RED, lw=1.8))
    clean(ax, xlim=(-2.4, 12), ylim=(-0.5, 1.6), title="As loaded: the camera's start is not yet placed on the recording clock")

    ax = axes[1]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=camera + offset, label="camera")
    ax.vlines(offset, -0.15, 1.2, color=RED, lw=1.0, linestyles="dotted")
    clean(ax, xlim=(-2.4, 12), ylim=(-0.5, 1.6), title="shift_times(3.0): the whole stream slides onto the recording clock, spacing intact")

    fig.tight_layout(h_pad=1.8)
    fig.savefig(OUTDIR / "time_alignment_coarse.png", dpi=200, bbox_inches="tight")


def build_fine():
    """Fine alignment: the camera clock drifts, so each sample must be placed individually."""
    reference = np.arange(0, 11, 1.0)
    n = 8
    true_times = np.arange(n) * 1.0
    drifted = np.arange(n) * 1.18  # a faster camera clock: spacing grows, later samples drift

    fig, axes = plt.subplots(2, 1, figsize=(9, 4.6))

    ax = axes[0]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=drifted, label="camera")
    for x_from, x_to in zip(drifted, true_times):
        ax.annotate("", xy=(x_to, 1.0), xytext=(x_from, TICK_H), arrowprops=dict(arrowstyle="->", color=RED, lw=1.1))
    clean(ax, xlim=(-2.4, 12), ylim=(-0.5, 1.6), title="As loaded: the camera clock drifts against the recording")

    ax = axes[1]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=true_times, label="camera")
    clean(ax, xlim=(-2.4, 12), ylim=(-0.5, 1.6), title="set_times(...): every sample is placed at its true recording time")

    fig.tight_layout(h_pad=1.8)
    fig.savefig(OUTDIR / "time_alignment_fine.png", dpi=200, bbox_inches="tight")


def build_timebase_concept():
    """A timebase is one clock and the streams riding it; its origin is the single handle that moves them all."""

    def panel(ax, *, origin, title):
        starts = [origin + 0.5, origin + 1.5, origin + 3.0]  # three streams at fixed internal offsets
        for y, start in zip((2, 1, 0), starts):
            timeline(ax, y=y, ticks=np.arange(start, start + 4), label="", show_time=False)
        x_lo = origin - 0.2
        x_hi = starts[-1] + 3 + 0.6
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x_lo, -0.35),
                x_hi - x_lo,
                2.9,
                boxstyle="round,pad=0.12,rounding_size=0.2",
                linewidth=1.2,
                edgecolor="0.5",
                facecolor="none",
                linestyle="--",
            )
        )
        ax.text(x_lo, 2.72, "one timebase", ha="left", va="bottom", fontsize=9.5, color="0.4")
        ax.vlines(0, -0.4, 2.6, color="0.75", lw=1.2)
        ax.text(0, -0.8, "session start", ha="center", va="top", fontsize=9, color="0.55")
        ax.vlines(origin, -0.4, 2.6, color=RED, lw=1.5, linestyles="dashed")
        ax.text(origin, -0.8, "origin", ha="center", va="top", fontsize=10, color=RED)
        clean(ax, xlim=(-2.0, 13), ylim=(-1.25, 3.2), title=title)

    fig, axes = plt.subplots(2, 1, figsize=(9, 5.2))
    panel(axes[0], origin=1.5, title="A timebase: several streams on one clock, at fixed internal offsets")
    panel(axes[1], origin=4.5, title="Move the origin and they all slide together; the offsets between them never change")
    fig.tight_layout(h_pad=2.2)
    fig.savefig(OUTDIR / "time_alignment_timebase_concept.png", dpi=200, bbox_inches="tight")


def build_timebases():
    """A multi-timebase interface aligned against another interface, contrasting the two modes."""
    reference = np.arange(0, 12, 1.0)

    def cameras(ax, *, left0, right0, box_label):
        left = np.arange(left0, left0 + 6)
        right = np.arange(right0, right0 + 6)
        # a box around the two camera timelines: they are one interface (two clocks). It tracks the
        # cameras, so the whole interface visibly moves with them.
        x_lo = min(left0, right0) - 0.15
        x_hi = max(left[-1], right[-1]) + 0.6
        camera_label_x = x_lo - 0.3  # a shared label column just left of the box, moving with it
        timeline(ax, y=2, ticks=reference, label="other interface", color=REF)
        timeline(ax, y=1, ticks=left, label="left_camera", label_x=camera_label_x, show_time=False)
        timeline(ax, y=0, ticks=right, label="right_camera", label_x=camera_label_x, show_time=False)
        box = mpatches.FancyBboxPatch(
            (x_lo, -0.35),
            x_hi - x_lo,
            1.9,
            boxstyle="round,pad=0.12,rounding_size=0.2",
            linewidth=1.2,
            edgecolor="0.5",
            facecolor="none",
            linestyle="--",
        )
        ax.add_patch(box)
        ax.text(x_lo, 1.72, box_label, ha="left", va="bottom", fontsize=9.5, color="0.4")

    fig, axes = plt.subplots(3, 1, figsize=(9.5, 7.4))

    cameras(axes[0], left0=1.0, right0=3.0, box_label="one interface (two clocks)")
    clean(axes[0], xlim=(-3.2, 14), ylim=(-0.7, 2.8), title="As loaded: a two-clock interface, and another interface as reference")

    cameras(axes[1], left0=4.0, right0=6.0, box_label="one interface (two clocks)")
    clean(axes[1], xlim=(-3.2, 14), ylim=(-0.7, 2.8), title="shift_times(3.0): the whole interface slides relative to the other interface; its clocks stay locked")

    cameras(axes[2], left0=3.0, right0=3.0, box_label="one interface (two clocks)")
    clean(axes[2], xlim=(-3.2, 14), ylim=(-0.7, 2.8), title="set_timebase_origin(3.0, timebase='left_camera'): one clock moves; the internal offset changes")

    fig.tight_layout(h_pad=2.0)
    fig.savefig(OUTDIR / "time_alignment_timebases.png", dpi=200, bbox_inches="tight")


def main():
    """Generate all temporal-alignment figures into this directory."""
    build_coarse()
    build_fine()
    build_timebase_concept()
    build_timebases()
    print("wrote coarse, fine, timebase_concept, and timebases figures")


if __name__ == "__main__":
    main()
