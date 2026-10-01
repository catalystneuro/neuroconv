"""Generate the temporal-alignment diagrams for the user guide.

Run from the repository root::

    python docs/_static/images/generate_time_alignment_figures.py

Produces six figures:

- ``time_alignment_gross_vs_fine.png``   - the concept figure: a constant offset (gross) beside a growing drift (fine).
- ``time_alignment_concatenate.png``     - gross alignment: separate trial files tiled onto one session clock.
- ``time_alignment_interpolation.png``   - fine alignment: sample timestamps remapped onto the reference clock via shared pulses.
- ``time_alignment_coarse.png``          - one time-bearing object moved by ``shift_times`` and by
  ``move_start_to``.
- ``time_alignment_moves_together.png`` - an interface's time-bearing objects moved together by ``shift_times``
  and by ``move_start_to``, with the gaps between them preserved.
- ``time_alignment_remap_together.png`` - one pulse mapping applied to every video file in an interface.
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
    """Show paired pulse times and their mapping of sample timestamps onto the reference clock."""
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 12, "text.color": "#243444"}):
        RED = "#b63c35"
        BLUE = "#246ca6"
        PALE = "#a8c4da"
        INK = "#243444"
        GRAY = "#c4cdd5"

        local = np.array([2.0, 4.0, 6.0])
        reference = np.array([3.0, 6.0, 7.0])
        samples = np.arange(2.2, 5.71, 0.5)
        mapped = np.interp(samples, local, reference)
        fig = plt.figure(figsize=(9.6, 7.5))
        fig.text(0.065, 0.965, "Use shared pulses to remap sample times", fontsize=21, weight="bold", va="top")
        upper = fig.add_axes([0.075, 0.54, 0.85, 0.34])
        lower = fig.add_axes([0.075, 0.105, 0.85, 0.34])

        for ax in [upper, lower]:
            ax.set(xlim=(1.6, 7.45), ylim=(-0.8, 1.9))
            ax.axis("off")

        def baseline(ax, y):
            ax.hlines(y, 1.82, 7.25, color=GRAY, lw=1.1, zorder=1)

        def anchors(ax, pulses, y, numbers=True):
            ax.vlines(pulses, y, y + 0.24, color=RED, lw=2.4, zorder=4)
            if numbers:
                for value in pulses:
                    ax.text(value, y + 0.33, f"{value:g} s", ha="center", color=RED, fontsize=11)

        for y, pulses in [(1.2, local), (0, reference)]:
            baseline(upper, y)
            anchors(upper, pulses, y, numbers=y > 0)
        for value in reference:
            upper.text(value, -0.17, f"{value:g} s", ha="center", color=RED, fontsize=11)
        upper.scatter(samples, np.full(len(samples), 1.2), s=38, color=BLUE, zorder=5)
        for a, b in zip(local, reference):
            upper.annotate(
                "",
                xy=(b, 0.25),
                xytext=(a, 1.16),
                arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.3, "linestyle": (0, (3, 3)), "alpha": 0.7},
            )
        upper.text(0, 1.0, "Local format clock", transform=upper.transAxes, fontsize=13, weight="bold")
        upper.text(
            1,
            1.0,
            "local_sync_times",
            transform=upper.transAxes,
            ha="right",
            fontsize=12,
            color=RED,
            fontfamily="DejaVu Sans Mono",
        )
        upper.text(0, 0.16, "Reference clock", transform=upper.transAxes, fontsize=13, weight="bold")
        upper.text(
            1,
            0.16,
            "reference_sync_times",
            transform=upper.transAxes,
            ha="right",
            fontsize=12,
            color=RED,
            fontfamily="DejaVu Sans Mono",
        )

        upper.annotate(
            "",
            xy=(0.47, 0.48),
            xytext=(0.47, 0.56),
            xycoords=fig.transFigure,
            arrowprops={"arrowstyle": "->", "lw": 2, "color": INK},
            annotation_clip=False,
        )
        fig.text(0.51, 0.52, "remap_times(...)", va="center", fontsize=13, fontfamily="DejaVu Sans Mono")

        for y, times, pulses in [
            (1.2, samples, local),
            (0, mapped, reference),
        ]:
            baseline(lower, y)
            lower.scatter(times, np.full(len(times), y), s=37, color=PALE, zorder=3)
            anchors(lower, pulses, y, numbers=False)
        for a, b in zip(samples, mapped):
            selected = np.isclose(a, 3.2)
            color = BLUE if selected else PALE
            lower.annotate(
                "",
                xy=(b, 0.055),
                xytext=(a, 1.15),
                arrowprops={
                    "arrowstyle": "->",
                    "color": color,
                    "lw": 2.3 if selected else 1,
                },
                zorder=1,
            )
            if selected:
                lower.scatter([a, b], [1.2, 0], s=76, color=BLUE, zorder=5)
                lower.text(a, 1.48, f"{a:g} s", ha="center", color=BLUE, fontsize=12)
                lower.text(b, -0.24, f"{b:g} s", ha="center", color=BLUE, fontsize=12)
        for times, y, direction in [(samples, 1.38, 1), (mapped, -0.18, -1)]:
            start, end = times[-2:]
            lower.plot([start, start, end, end], [y - direction * 0.07, y, y, y - direction * 0.07], color=BLUE, lw=1.1)
            lower.text(
                (start + end) / 2,
                y + direction * 0.08,
                f"Δt = {end - start:g} s",
                ha="center",
                va="bottom" if direction > 0 else "top",
                color=BLUE,
                fontsize=11,
            )
        lower.text(1, 1.0, "Before remapping", transform=lower.transAxes, ha="right", fontsize=12, color=BLUE)
        lower.text(1, 0.0, "After remapping", transform=lower.transAxes, ha="right", fontsize=12, color=BLUE)
        fig.text(0.075, 0.064, "Same samples, new timestamp values.", fontsize=12, color=BLUE)
        fig.text(
            0.075,
            0.028,
            "Red marks: synchronization pulses. Blue dots: sample timestamps before and after.",
            fontsize=11,
            color="#586675",
        )

        fig.savefig(OUTDIR / "time_alignment_interpolation.png", dpi=190, facecolor="white")
        plt.close(fig)


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


def build_remap_together():
    """Show one pulse mapping applied to every video file in an interface."""
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 12, "text.color": "#243444"}):
        red = "#b63c35"
        blue = "#246ca6"
        pale = "#a8c4da"
        gray = "#c4cdd5"
        local = np.array([2.0, 4.0, 6.0])
        reference = np.array([3.0, 6.0, 7.0])
        objects = {
            "trial_01": np.array([2.2, 2.5, 2.8]),
            "trial_02": np.array([3.3, 3.6, 3.9]),
            "trial_03": np.array([4.8, 5.1, 5.4, 5.7]),
        }
        fig = plt.figure(figsize=(9.6, 8.0))
        fig.text(0.065, 0.965, "One pulse mapping for all video files", fontsize=21, weight="bold", va="top")
        upper = fig.add_axes([0.075, 0.59, 0.85, 0.28])
        lower = fig.add_axes([0.075, 0.11, 0.85, 0.30])
        for ax in (upper, lower):
            ax.set(xlim=(1.6, 7.45), ylim=(-0.8, 1.9))
            ax.axis("off")
            for y, pulses in [(1.2, local), (0, reference)]:
                ax.hlines(y, 1.82, 7.25, color=gray, lw=1.1, zorder=1)
                ax.vlines(pulses, y, y + 0.24, color=red, lw=2.4, zorder=4)
        for a, b in zip(local, reference):
            upper.text(a, 1.53, f"{a:g} s", ha="center", color=red, fontsize=11)
            upper.text(b, -0.17, f"{b:g} s", ha="center", color=red, fontsize=11)
            upper.annotate(
                "",
                xy=(b, 0.25),
                xytext=(a, 1.16),
                arrowprops={
                    "arrowstyle": "->",
                    "color": red,
                    "lw": 1.3,
                    "linestyle": (0, (3, 3)),
                    "alpha": 0.7,
                },
            )
        upper.text(0, 1, "Camera clock", transform=upper.transAxes, fontsize=13, weight="bold")
        upper.text(
            1,
            1,
            "local_sync_times",
            transform=upper.transAxes,
            ha="right",
            fontsize=12,
            color=red,
            fontfamily="DejaVu Sans Mono",
        )
        upper.text(0, 0.16, "Electrophysiology clock", transform=upper.transAxes, fontsize=13, weight="bold")
        upper.text(
            1,
            0.16,
            "reference_sync_times",
            transform=upper.transAxes,
            ha="right",
            fontsize=12,
            color=red,
            fontfamily="DejaVu Sans Mono",
        )
        fig.text(
            0.5,
            0.53,
            "video_interface.alignment.remap_times(...)",
            ha="center",
            fontsize=13,
            fontfamily="DejaVu Sans Mono",
        )
        upper.annotate(
            "",
            xy=(0.5, 0.445),
            xytext=(0.5, 0.505),
            xycoords=fig.transFigure,
            arrowprops={"arrowstyle": "->", "lw": 2, "color": "#243444"},
            annotation_clip=False,
        )
        lower.text(
            0, 1.05, "Before remapping: continuous camera clock", transform=lower.transAxes, fontsize=13, color=blue
        )
        for key, times in objects.items():
            mapped = np.interp(times, local, reference)
            for y, values, label_y in [(1.2, times, 1.48), (0, mapped, -0.35)]:
                lower.add_patch(
                    mpatches.Rectangle(
                        (values[0] - 0.06, y - 0.13),
                        values[-1] - values[0] + 0.12,
                        0.26,
                        facecolor="#edf4f9",
                        edgecolor=pale,
                        lw=1,
                        zorder=2,
                    )
                )
                lower.scatter(values, np.full(len(values), y), s=38, color=blue, zorder=5)
                lower.text(
                    (values[0] + values[-1]) / 2,
                    label_y,
                    key,
                    ha="center",
                    color=blue,
                    fontsize=11,
                    fontfamily="DejaVu Sans Mono",
                )
            for a, b in zip(times, mapped):
                lower.annotate(
                    "", xy=(b, 0.15), xytext=(a, 1.05), arrowprops={"arrowstyle": "->", "color": pale, "lw": 1}
                )
        lower.text(
            0, -0.05, "After remapping: electrophysiology clock", transform=lower.transAxes, fontsize=13, color=blue
        )
        fig.text(0.075, 0.035, "Same files and samples. One mapping applied to every object.", fontsize=12, color=blue)
        fig.savefig(OUTDIR / "time_alignment_remap_together.png", dpi=190, facecolor="white")
        plt.close(fig)


def main():
    """Generate all temporal-alignment figures into this directory."""
    build_gross_vs_fine()
    build_concatenate()
    build_interpolation()
    build_coarse()
    build_moves_together()
    build_remap_together()
    print(
        "wrote time_alignment_gross_vs_fine.png, time_alignment_interpolation.png, "
        "time_alignment_coarse.png, time_alignment_moves_together.png and time_alignment_remap_together.png"
    )


if __name__ == "__main__":
    main()
