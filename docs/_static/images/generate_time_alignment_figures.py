"""Generate the temporal-alignment diagrams for the user guide.

Run from the repository root::

    python docs/_static/images/generate_time_alignment_figures.py

Produces two figures:

- ``time_alignment_coarse.png``         - a stream slid as a rigid block onto the recording clock.
- ``time_alignment_moves_together.png`` - an interface's time-bearing objects all shifted by the same offset,
  with the gaps between them preserved.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

BLACK = "black"
RED = "firebrick"
REF = "#2f6f9f"  # a distinct colour for the reference stream
TICK_H = 0.16
OUTDIR = Path(__file__).parent


def timeline(ax, *, y, ticks, label, color=BLACK, label_x=None, show_time=True):
    """Draw one stream: a baseline with vertical sample ticks, a left label, and a 'time' cap.

    ``label_x`` overrides where the (right-aligned) label sits, so several rows can share a label column;
    ``show_time`` toggles the italic 'time' cap at the right end.
    """
    ticks = np.asarray(ticks, dtype=float)
    x0, x1 = ticks[0], ticks[-1]
    ax.hlines(y, x0, x1 + 0.4, color=color, lw=3)
    ax.vlines(ticks, y, y + TICK_H, color=color, lw=1.5)
    label_position = label_x if label_x is not None else x0 - 0.3
    ax.text(label_position, y + TICK_H / 2, label, ha="right", va="center", fontsize=12, color=color)
    if show_time:
        ax.text(x1 + 0.6, y, "time", ha="left", va="center", fontsize=9, style="italic")


def clean(ax, *, xlim, ylim, title):
    """Apply the shared panel styling: a left-aligned title, fixed limits, and no axes."""
    ax.set_title(title, fontsize=12, loc="left", pad=6)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


def build_coarse():
    """A stream whose internal spacing is already right, but whose placement on the shared clock is not."""
    reference = np.arange(0, 11, 1.0)
    stream = np.arange(0, 6, 1.0)
    offset = 3.0

    fig, axes = plt.subplots(2, 1, figsize=(9, 4.6))

    ax = axes[0]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=stream, label="events")
    ax.annotate("", xy=(offset, 1.0), xytext=(0.0, TICK_H), arrowprops=dict(arrowstyle="->", color=RED, lw=1.8))
    clean(ax, xlim=(-2.4, 12), ylim=(-0.5, 1.6), title="As loaded: the stream is not yet placed on the recording clock")

    ax = axes[1]
    timeline(ax, y=1, ticks=reference, label="recording", color=REF)
    timeline(ax, y=0, ticks=stream + offset, label="events")
    ax.vlines(offset, -0.15, 1.2, color=RED, lw=1.0, linestyles="dotted")
    clean(
        ax,
        xlim=(-2.4, 12),
        ylim=(-0.5, 1.6),
        title="shift_times(3.0): the whole stream slides onto the recording clock, spacing intact",
    )

    fig.tight_layout(h_pad=1.8)
    fig.savefig(OUTDIR / "time_alignment_coarse.png", dpi=200, bbox_inches="tight")


def build_moves_together():
    """An interface's time-bearing objects all move by one offset; their internal gaps are preserved."""

    def panel(ax, *, offset, title):
        starts = [offset + 0.5, offset + 1.5, offset + 3.0]  # three objects at fixed internal gaps
        for y, start in zip((2, 1, 0), starts):
            timeline(ax, y=y, ticks=np.arange(start, start + 4), label="", show_time=False)
        x_lo = offset - 0.2
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
        ax.text(x_lo, 2.72, "one interface: its time-bearing objects", ha="left", va="bottom", fontsize=9.5, color="0.4")
        ax.vlines(0, -0.4, 2.6, color="0.75", lw=1.2)
        ax.text(0, -0.85, "session start", ha="center", va="top", fontsize=9, color="0.55")
        if offset:
            ax.annotate("", xy=(offset, -0.6), xytext=(0, -0.6), arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
            ax.text(offset / 2, -0.72, "offset", ha="center", va="top", fontsize=10, color=RED)
        clean(ax, xlim=(-2.0, 13), ylim=(-1.5, 3.2), title=title)

    fig, axes = plt.subplots(2, 1, figsize=(9, 5.4))
    panel(axes[0], offset=0.0, title="Offset 0: the source times are written exactly as the system recorded them")
    panel(axes[1], offset=3.0, title="shift_times(3.0): every object moves by the same amount, the gaps never change")
    fig.tight_layout(h_pad=2.2)
    fig.savefig(OUTDIR / "time_alignment_moves_together.png", dpi=200, bbox_inches="tight")


def main():
    """Generate all temporal-alignment figures into this directory."""
    build_coarse()
    build_moves_together()
    print("wrote time_alignment_coarse.png and time_alignment_moves_together.png")


if __name__ == "__main__":
    main()
