"""Generate the temporal-alignment diagrams for the user guide.

Run from the repository root::

    python docs/_static/images/generate_time_alignment_figures.py

Produces five figures:

- ``time_alignment_gross_vs_fine.png``   - the concept figure: a constant offset (gross) beside a growing drift (fine).
- ``time_alignment_concatenate.png``     - gross alignment: separate trial files tiled onto one session clock.
- ``time_alignment_interpolation.png``   - fine alignment: frames interpolated onto the reference clock via shared pulses.
- ``time_alignment_coarse.png``          - one time-bearing object moved by ``shift_times`` and by
  ``move_start_to``.
- ``time_alignment_moves_together.png`` - an interface's time-bearing objects moved together by ``shift_times``
  and by ``move_start_to``, with the gaps between them preserved.
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


def clean(ax, *, xlim, ylim, title, title_loc="left"):
    """Apply the shared panel styling: a title (left-aligned by default), fixed limits, and no axes."""
    ax.set_title(title, fontsize=12, loc=title_loc, pad=6)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


def build_gross_vs_fine():
    """The concept figure: a constant offset (gross) beside a growing drift (fine).

    Each panel shows the recording's clock instants as a faint full-height gray grid, the recording samples as
    black ticks on that grid, and a second stream as blue ticks. Red bars run from each recording instant to the
    matching sample of the second stream: equal-length on the left (a constant offset a single shift fixes),
    growing on the right (a drift no shift can fix).
    """
    grid = np.arange(0, 8, 1.0)  # the recording's / session clock instants
    y_ref, y_other = 1.0, 0.0
    gap_y = y_other - 0.28  # where the red gap bars sit, just under the second stream

    def panel(ax, *, second_ticks, second_label, note, title):
        # faint full-height guides at the recording clock instants
        ax.vlines(grid, gap_y - 0.15, y_ref + TICK_H + 0.15, color="0.7", lw=0.9, alpha=0.5)
        timeline(ax, y=y_ref, ticks=grid, label="recording", color=BLACK, show_time=False)
        timeline(ax, y=y_other, ticks=second_ticks, label=second_label, color=REF, label_x=grid[0] - 0.3, show_time=False)
        # red bars from each recording instant to the matching (misplaced) sample of the second stream
        for gx, sx in zip(grid, second_ticks):
            ax.plot([gx, sx], [gap_y, gap_y], color=RED, lw=1.7)
        ax.text((grid[0] + grid[-1]) / 2, gap_y - 0.55, note, ha="center", va="center", fontsize=9.5, color="0.35")
        clean(ax, xlim=(-2.4, grid[-1] + 2.5), ylim=(gap_y - 1.0, y_ref + TICK_H + 0.4), title=title, title_loc="center")

    fig, (axl, axr) = plt.subplots(1, 2, figsize=(11, 3.6))

    offset = 0.45  # behavior started later: same rate, so the gap to every recording instant is the same
    panel(
        axl,
        second_ticks=grid + offset,
        second_label="behavior",
        note="same rate, so the gap is constant:\none rigid shift lines it up",
        title="Same clock (gross)",
    )

    drift = grid + (grid - grid[0]) * 0.14  # camera clock runs faster: the gap grows across the session
    panel(
        axr,
        second_ticks=drift,
        second_label="camera",
        note="different rates, so the gap grows:\nno shift works, the times are re-timed",
        title="Different clocks (fine)",
    )

    fig.tight_layout(w_pad=3.0)
    fig.savefig(OUTDIR / "time_alignment_gross_vs_fine.png", dpi=200, bbox_inches="tight")


def build_concatenate():
    """How gross alignment looks for a trialized session: separate trial files laid end to end on one clock.

    Each trial is recorded to its own file, so each clock starts near zero and the trials pile up on top of one
    another as loaded. ``shift_times`` slides each trial to the time it began, tiling them along a single session
    clock, and nothing inside any trial is touched.
    """
    trials = [np.arange(0, 4, 1.0), np.arange(0, 3, 1.0), np.arange(0, 5, 1.0)]  # three trial files, each from ~0
    labels = ["trial 1", "trial 2", "trial 3"]
    rows = (2, 1, 0)

    gap = 1.0  # inter-trial interval between one trial's end and the next trial's start
    starts, cursor = [], 0.0
    for trial in trials:
        starts.append(cursor)
        cursor += (trial[-1] - trial[0]) + gap
    session_end = starts[-1] + (trials[-1][-1] - trials[-1][0])

    shared_xlim = (-3.6, session_end + 1.4)  # both panels share a scale, so the preserved tick spacing looks identical
    shared_ylim = (-1.35, 2.75)

    fig, (axl, axr) = plt.subplots(1, 2, figsize=(11, 3.0))

    # left column: as loaded, every trial's clock starting near zero
    for y, trial, label in zip(rows, trials, labels):
        timeline(axl, y=y, ticks=trial, label=label, color=BLACK, label_x=-0.9, show_time=False)
    axl.vlines(0, -0.35, 2.25, color="0.75", lw=1.2)
    clean(axl, xlim=shared_xlim, ylim=shared_ylim, title="As loaded: each trial's clock starts near zero")

    # right column: each trial slid to its start, tiled along one session clock
    for y, trial, label, start in zip(rows, trials, labels, starts):
        timeline(axr, y=y, ticks=trial + start, label=label, color=BLACK, label_x=-0.9, show_time=False)
        if start > 0:  # the rigid shift that moves this trial to where it began
            axr.annotate(
                "", xy=(start, y - 0.28), xytext=(0, y - 0.28),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.3),
            )
    axr.hlines(-0.72, 0, session_end + 0.4, color=REF, lw=2.4)  # the single session clock the trials tile
    axr.text(-0.6, -0.72, "session", ha="right", va="center", fontsize=9, color=REF)
    axr.text(session_end + 0.55, -0.72, "time", ha="left", va="center", fontsize=8.5, style="italic")
    clean(axr, xlim=shared_xlim, ylim=shared_ylim, title="Aligned: each trial slid to its start, tiled on one session clock")

    fig.tight_layout(w_pad=2.5)
    fig.savefig(OUTDIR / "time_alignment_concatenate.png", dpi=200, bbox_inches="tight")


def build_interpolation():
    """Fine alignment: re-time a stream by interpolating its samples onto the reference clock through shared pulses.

    The same synchronization pulses are recorded on both clocks (red), so each pulse pins a camera-clock time to a
    reference-clock time. Those pairs are the anchors. The camera's frames (blue) are denser than the pulses, so a
    frame that falls between two pulses is placed on the reference clock by interpolating between the surrounding
    anchors.
    """
    y_ref, y_cam = 1.0, 0.0
    pulse_h = 0.34  # pulses drawn taller than frames so the shared markers stand out
    frame_h = TICK_H

    cam_pulses = np.array([1.0, 4.0, 7.0, 10.0])  # sync pulses on the camera's own clock: evenly spaced
    ref_pulses = 1.0 + (cam_pulses - 1.0) * 0.88  # the same pulses on the reference clock: drifted, so they compress
    frames = np.arange(1.0, 10.01, 0.5)  # the camera's frames, denser than the pulses

    fig, ax = plt.subplots(figsize=(9, 3.9))

    # reference clock (top): the trusted axis, only the shared pulses live here as anchors
    ax.hlines(y_ref, ref_pulses[0], ref_pulses[-1] + 0.4, color=BLACK, lw=3)
    ax.vlines(ref_pulses, y_ref, y_ref + pulse_h, color=RED, lw=2.4)
    ax.text(0.7, y_ref + pulse_h / 2, "reference clock", ha="right", va="center", fontsize=12, color=BLACK)
    ax.text(
        ref_pulses[-1] + 0.7,
        y_ref + pulse_h / 2,
        "reference_sync_times",
        ha="left",
        va="center",
        fontsize=9,
        color=RED,
    )

    # camera clock (bottom): dense frames plus the same shared pulses
    ax.hlines(y_cam, frames[0], frames[-1] + 0.4, color=REF, lw=3)
    ax.vlines(frames, y_cam, y_cam + frame_h, color=REF, lw=1.2)
    ax.vlines(cam_pulses, y_cam, y_cam + pulse_h, color=RED, lw=2.4)
    ax.text(0.7, y_cam + frame_h / 2, "camera clock", ha="right", va="center", fontsize=12, color=REF)
    ax.text(
        cam_pulses[-1] + 0.7, y_cam + pulse_h / 2, "local_sync_times", ha="left", va="center", fontsize=9, color=RED
    )

    # each shared pulse anchors a camera-clock time to a reference-clock time
    for cx, rx in zip(cam_pulses, ref_pulses):
        ax.plot([cx, rx], [y_cam + pulse_h, y_ref], color=RED, lw=1.0, alpha=0.55, linestyle=(0, (4, 3)))
    ax.annotate(
        "same pulse,\ntwo clocks",
        xy=((cam_pulses[2] + ref_pulses[2]) / 2, (y_cam + pulse_h + y_ref) / 2),
        xytext=(cam_pulses[2] + 1.4, y_cam + 0.62),
        fontsize=9,
        color=RED,
        ha="center",
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.0),
    )

    # one frame that falls between two pulses, placed on the reference clock by interpolation
    frame = 5.5
    landing = np.interp(frame, cam_pulses, ref_pulses)
    ax.vlines(frame, y_cam, y_cam + pulse_h, color=REF, lw=2.4)  # highlight the frame
    ax.plot([frame, landing], [y_cam + pulse_h, y_ref], color=REF, lw=1.6)
    ax.plot(landing, y_ref, marker="o", color=REF, markersize=6, zorder=5)  # where it lands on the reference clock
    ax.annotate(
        "a frame between pulses\nlands here by interpolation",
        xy=(landing, y_ref),
        xytext=(landing - 2.9, y_ref + 0.5),
        fontsize=9,
        color=REF,
        ha="center",
        arrowprops=dict(arrowstyle="->", color=REF, lw=1.0),
    )

    clean(
        ax,
        xlim=(-2.6, 12.6),
        ylim=(-0.5, 1.85),
        title="alignment[key].remap_times(...): the shared pulses anchor the two clocks, frames between them are "
        "interpolated",
    )
    fig.tight_layout()
    fig.savefig(OUTDIR / "time_alignment_interpolation.png", dpi=200, bbox_inches="tight")


def build_coarse():
    """One time-bearing object moved by ``shift_times`` and by ``move_start_to``.

    The one-object counterpart of ``build_moves_together``. Both calls keep the spacing between samples; they differ in
    what the number is measured from, ``shift_times`` from where the object was and ``move_start_to`` from session
    start. The moved panels show the as-loaded object faintly below the moved one.
    """
    loaded_ticks = np.arange(0.5, 6.5, 1.0)

    def draw_object(ax, ticks, color, y=0.0, width=3):
        ax.hlines(y, ticks[0], ticks[-1] + 0.4, color=color, lw=width)
        ax.vlines(ticks, y, y + TICK_H, color=color, lw=1.5)

    def panel(ax, *, shift, title, arrow_from=None, arrow_to=None, arrow_label=None):
        if shift:
            # Drawn below the moved object, so the two never merge into one line.
            draw_object(ax, loaded_ticks, color="0.82", y=-0.3, width=2)
        ticks = loaded_ticks + shift
        draw_object(ax, ticks, color=BLACK)
        ax.text(ticks[0], 0.3, "one time-bearing object", ha="left", va="bottom", fontsize=9.5, color="0.4")
        ax.vlines(0, -0.45, 0.45, color="0.75", lw=1.2)
        ax.text(0, -0.85, "session start", ha="center", va="top", fontsize=9, color="0.55")
        if arrow_label:
            ax.vlines([arrow_from, arrow_to], -0.6, 0.2, color=RED, lw=1.0, linestyles="dotted")
            ax.annotate(
                "", xy=(arrow_to, -0.6), xytext=(arrow_from, -0.6), arrowprops=dict(arrowstyle="->", color=RED, lw=1.6)
            )
            ax.text((arrow_from + arrow_to) / 2, -0.72, arrow_label, ha="center", va="top", fontsize=10, color=RED)
        clean(ax, xlim=(-2.0, 13), ylim=(-1.3, 0.75), title=title)

    fig, axes = plt.subplots(3, 1, figsize=(9, 5.6))
    panel(axes[0], shift=0.0, title="As loaded: the object sits where its source times put it")
    panel(
        axes[1],
        shift=3.0,
        title="alignment[key].shift_times(3.0): measured from where the object was",
        arrow_from=loaded_ticks[0],
        arrow_to=loaded_ticks[0] + 3.0,
        arrow_label="delta = 3.0",
    )
    panel(
        axes[2],
        shift=5.0 - loaded_ticks[0],
        title="alignment[key].move_start_to(5.0): measured from session start",
        arrow_from=0.0,
        arrow_to=5.0,
        arrow_label="t = 5.0",
    )
    fig.tight_layout(h_pad=1.8)
    fig.savefig(OUTDIR / "time_alignment_coarse.png", dpi=200, bbox_inches="tight")


def build_moves_together():
    """An interface's time-bearing objects moved together by ``shift_times`` and by ``move_start_to``.

    Both calls move every object by one amount and keep the gaps between them. They differ in what the number is
    measured from: ``shift_times`` from where the objects were, ``move_start_to`` from session start to the earliest
    object start. The moved panels show the as-loaded objects faintly behind the moved ones.
    """
    loaded_starts = np.array([0.5, 1.5, 3.0])  # three objects at fixed internal gaps

    def draw_objects(ax, starts, color, lower=0.0, width=3):
        for y, start in zip((2 - lower, 1 - lower, 0 - lower), starts):
            ticks = np.arange(start, start + 4)
            ax.hlines(y, ticks[0], ticks[-1] + 0.4, color=color, lw=width)
            ax.vlines(ticks, y, y + TICK_H, color=color, lw=1.5)

    def panel(ax, *, shift, title, arrow_from=None, arrow_to=None, arrow_label=None):
        if shift:
            # Drawn below the moved rows, so the two never merge into one line.
            draw_objects(ax, loaded_starts, color="0.82", lower=0.3, width=2)
        starts = loaded_starts + shift
        draw_objects(ax, starts, color=BLACK)
        x_lo = starts[0] - 0.7
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
        if arrow_label:
            ax.vlines([arrow_from, arrow_to], -0.6, 2.0, color=RED, lw=1.0, linestyles="dotted")
            ax.annotate(
                "", xy=(arrow_to, -0.6), xytext=(arrow_from, -0.6), arrowprops=dict(arrowstyle="->", color=RED, lw=1.6)
            )
            ax.text((arrow_from + arrow_to) / 2, -0.72, arrow_label, ha="center", va="top", fontsize=10, color=RED)
        clean(ax, xlim=(-2.0, 13), ylim=(-1.5, 3.2), title=title)

    fig, axes = plt.subplots(3, 1, figsize=(9, 8.1))
    panel(axes[0], shift=0.0, title="As loaded: the objects sit where the source times put them")
    panel(
        axes[1],
        shift=3.0,
        title="alignment.shift_times(3.0): measured from where the objects were",
        arrow_from=loaded_starts[0],
        arrow_to=loaded_starts[0] + 3.0,
        arrow_label="delta = 3.0",
    )
    panel(
        axes[2],
        shift=5.0 - loaded_starts[0],
        title="alignment.move_start_to(5.0): measured from session start to the earliest start",
        arrow_from=0.0,
        arrow_to=5.0,
        arrow_label="t = 5.0",
    )
    fig.tight_layout(h_pad=2.2)
    fig.savefig(OUTDIR / "time_alignment_moves_together.png", dpi=200, bbox_inches="tight")


def main():
    """Generate all temporal-alignment figures into this directory."""
    build_gross_vs_fine()
    build_concatenate()
    build_interpolation()
    build_coarse()
    build_moves_together()
    print(
        "wrote time_alignment_gross_vs_fine.png, time_alignment_interpolation.png, "
        "time_alignment_coarse.png and time_alignment_moves_together.png"
    )


if __name__ == "__main__":
    main()
