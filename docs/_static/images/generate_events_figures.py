"""Generate the diagrams for the "extract events from a sampled signal" how-to.

Run from the repository root::

    uv run --with matplotlib --with numpy python docs/_static/images/generate_events_figures.py

Produces seven figures:

- ``events_pipeline_model.png``          - the spine figure: the two stages, what the data is at each seam,
  and which settings each stage takes.
- ``events_two_stages.png``              - the same pipeline walked concretely on one analog trace. Kept as
  the alternative to the abstract spine figure; not currently used by the page.
- ``events_conditioning_binarize.png``   - the ``binarize`` cut: a magnitude cut at a level.
- ``events_conditioning_bits.png``       - the ``bits`` cut: one wire picked out of a packed word.
- ``events_five_readings.png``           - the detection vocabulary: three point readings and two durative ones.
- ``events_several_levels.png``          - one signal read at three cut points, giving three nested durative events.
- ``events_high_period_limit.png``       - where a duration reading breaks down: the grid, not the pulse.

One figure per conditioning cut, deliberately: a cut added later is a new builder and a new figure beside
its own paragraph, rather than a redraw of a comparison that has to grow a panel.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

BLACK = "black"
RED = "firebrick"
REF = "#2f6f9f"  # a distinct colour for the derived / secondary stream
GUIDE = "0.86"  # faint vertical guides marking the sampling instants
NOTE = "0.35"  # captions and asides
TICK_H = 0.16
OUTDIR = Path(__file__).parent


def clean(ax, *, xlim, ylim, title, title_loc="left"):
    """Apply the shared panel styling: a title (left-aligned by default), fixed limits, and no axes."""
    ax.set_title(title, fontsize=12, loc=title_loc, pad=6)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")


def timeline(ax, *, y, ticks, label, color=BLACK, label_x=None, tick_h=TICK_H, pad=0.4, fontsize=11):
    """Draw one stream: a baseline with vertical sample ticks and a right-aligned left label."""
    ticks = np.asarray(ticks, dtype=float)
    ax.hlines(y, ticks[0], ticks[-1] + pad, color=color, lw=2.6)
    ax.vlines(ticks, y, y + tick_h, color=color, lw=1.4)
    label_position = label_x if label_x is not None else ticks[0] - 0.3
    ax.text(label_position, y + tick_h / 2, label, ha="right", va="center", fontsize=fontsize, color=color)


def two_valued_line(ax, times, values, *, y_low, y_high, color=BLACK, lw=2.6):
    """Draw a two-valued signal as a square wave held between consecutive knots."""
    times = np.asarray(times, dtype=float)
    levels = np.where(np.asarray(values) > 0, y_high, y_low)
    ax.step(times, levels, where="post", color=color, lw=lw, solid_joinstyle="miter")


def point_events(ax, y, times, *, color=BLACK, size=10):
    """Draw a row of point events as upward triangles sitting on a baseline."""
    times = np.asarray(times, dtype=float)
    ax.plot(times, np.full(times.shape, y), linestyle="none", marker="^", markersize=size, color=color, clip_on=False)


def durative_event(ax, y, start, stop, *, color=RED, lw=2.6, cap=0.13):
    """Draw one durative event as a horizontal span with vertical end caps."""
    ax.hlines(y, start, stop, color=color, lw=lw)
    ax.vlines([start, stop], y - cap, y + cap, color=color, lw=lw)


def build_two_stages():
    """The spine figure: every event type is read in two stages, and the data type changes between them.

    One analog trace, cut at a level, becomes a two-valued line of the same length on the same timeline
    (conditioning, signal to signal), and that line's low-to-high transitions become event times
    (detection, signal to events). The three panels share one time axis so a sample in the top panel sits
    directly above the same sample below it.
    """
    samples = np.arange(6.0)
    values = np.array([480, 510, 700, 690, 505, 660], dtype=float)
    cut = 550.0
    line = (values > cut).astype(int)  # 0 0 1 1 0 1
    rising = samples[1:][(line[1:] == 1) & (line[:-1] == 0)]  # samples 2 and 5

    x_lim = (-2.7, 9.6)
    x_end = samples[-1] + 0.7
    right_column = 5.95

    fig, axes = plt.subplots(3, 1, figsize=(10, 7.2), gridspec_kw={"height_ratios": [1.55, 1.05, 0.62]})

    # -- top: the file's signal, any values, any dtype ---------------------------------------------
    ax = axes[0]
    ax.vlines(samples, 170, 790, color=GUIDE, lw=0.9, zorder=0)
    timeline(ax, y=340, ticks=samples, label="XA3\n(analog input)", label_x=-0.45, tick_h=24, pad=0.7)
    ax.plot(samples, values, marker="o", markersize=6, color=BLACK, lw=1.7)
    for x, value in zip(samples, values):  # labels sit clear of the cut line, so they never sit on it
        above = value > cut
        ax.text(
            x, value + (34 if above else -34), f"{value:.0f}",
            ha="center", va="bottom" if above else "top", fontsize=10, color=BLACK,
        )
    ax.hlines(cut, -0.35, x_end, color=RED, lw=1.6, linestyles=(0, (6, 4)))
    ax.text(right_column, cut, '  {"binarize": 550.0}', ha="left", va="center", fontsize=11, color=RED)
    ax.annotate("", xy=(2.5, 155), xytext=(2.5, 295), arrowprops=dict(arrowstyle="-|>", color=NOTE, lw=1.6))
    ax.text(2.72, 225, "conditioning: signal to signal", ha="left", va="center", fontsize=11, color=NOTE)
    clean(ax, xlim=x_lim, ylim=(110, 830), title="the file's signal: any values, any dtype")

    # -- middle: the line, two values, same length, same timeline ----------------------------------
    ax = axes[1]
    ax.vlines(samples, -0.95, 1.45, color=GUIDE, lw=0.9, zorder=0)
    two_valued_line(ax, np.append(samples, x_end), np.append(line, line[-1]), y_low=0.0, y_high=1.0)
    ax.plot(samples, line, linestyle="none", marker="o", markersize=6, color=BLACK)
    for x, level in zip(samples, line):
        ax.text(x, -0.26, str(level), ha="center", va="top", fontsize=11, color=BLACK)
    ax.text(-0.45, 0.5, "line", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, 0.5, "  two values, same length,\n  same timeline", ha="left", va="center", fontsize=10.5, color=NOTE)
    ax.annotate("", xy=(2.5, -1.02), xytext=(2.5, -0.62), arrowprops=dict(arrowstyle="-|>", color=NOTE, lw=1.6))
    ax.text(2.72, -0.82, "detection: signal to events", ha="left", va="center", fontsize=11, color=NOTE)
    clean(ax, xlim=x_lim, ylim=(-1.35, 1.5), title='a line: the same trace after {"binarize": 550.0}')

    # -- bottom: the events ------------------------------------------------------------------------
    ax = axes[2]
    ax.vlines(rising, -0.05, 0.55, color=GUIDE, lw=0.9, zorder=0)
    ax.hlines(0.0, -0.35, x_end, color=BLACK, lw=2.6)
    point_events(ax, 0.11, rising)
    ax.text(-0.45, 0.11, '"detection": "rising"', ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, 0.11, "  two rising edges: one time each", ha="left", va="center", fontsize=10.5, color=NOTE)
    clean(ax, xlim=x_lim, ylim=(-0.4, 0.66), title="events: a time at each low-to-high transition")

    fig.tight_layout(h_pad=1.4)
    fig.savefig(OUTDIR / "events_two_stages.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_pipeline_model():
    """The model as a schematic: what the data looks like at each stage, drawn rather than named.

    Each box holds a sketch of its own data, an arbitrary trace, a two-valued line, then events, so the
    shape of the pipeline reads before any vocabulary does. It names no settings on purpose: ``bits``,
    ``binarize`` and the five readings are introduced by the sections below, and listing them here would
    put the whole grammar in front of a reader who has not met any of it.
    """
    # One arbitrary trace carried through both stages. The three panels share an x-axis, so the sketches
    # have to agree: the line is this trace cut, and the events are that line's rising edges. Stacking is
    # what makes the shared timeline visible instead of asserted, and it is also what makes an inconsistent
    # set of drawings a visible error rather than a hidden one.
    # Four crossings of uneven width rather than two: a sparse trace across a wide box reads as an empty
    # drawing, and uneven widths keep it looking like a recording instead of a test pattern.
    trace = np.array(
        [2.1, 2.5, 3.8, 4.3, 3.6, 2.4, 2.0, 2.6, 4.1, 4.6, 4.0, 2.9, 2.2,
         2.4, 3.5, 4.2, 3.9, 3.3, 2.5, 2.0, 2.8, 3.9, 4.4, 3.1, 2.3]
    )
    samples = np.arange(float(len(trace)))
    cut = 3.2
    line = (trace >= cut).astype(int)
    rising = samples[1:][np.diff(line) > 0]

    box_w, box_h, gap = 11.0, 1.25, 1.05
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    def box(index, label, caption):
        """Draw one stage's box and its labels, returning the y centre of its drawing area."""
        y_top = -index * (box_h + gap)
        y_centre = y_top - box_h / 2
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (0, y_top - box_h), box_w, box_h,
                boxstyle="round,pad=0.06,rounding_size=0.12",
                facecolor="white", edgecolor=BLACK, lw=1.8,
            )
        )
        ax.text(-0.35, y_centre + 0.18, label, ha="right", va="center", fontsize=12, color=BLACK)
        ax.text(-0.35, y_centre - 0.22, caption, ha="right", va="center", fontsize=9.5, color=NOTE)
        return y_centre

    def to_x(values):
        """Place sample indices across the boxes' shared inner span."""
        return 0.6 + values / samples[-1] * (box_w - 1.2)

    # 1. whatever the file carries: a magnitude of some kind, sampled over time.
    y = box(0, "the file's signal", "any values, one per sample")
    ax.plot(
        to_x(samples), y + (trace - trace.mean()) * 0.28,
        color=BLACK, lw=2.0, marker="o", markersize=3.4,
    )

    # 2. the two-valued line conditioning always returns, on the same timeline.
    y = box(1, "a digital line", "two values, same timeline")
    two_valued_line(
        ax, to_x(np.append(samples, samples[-1] + 0.6)), np.append(line, line[-1]),
        y_low=y - 0.32, y_high=y + 0.32, lw=2.4,
    )

    # 3. what detection returns: a time wherever the line did the thing you asked for, plus a duration when
    #    the reading is a durative one. The duration is only worth drawing here because the panels share an
    #    x-axis: each red span lines up under the pulse it measures, so what a duration *is* needs no
    #    caption. Side by side it was an unexplained detail and was left out.
    # Onsets only. Durations were drawn here and taken out again: every placement either floated above the
    # axis or collided with the markers, and the durative readings are explained in the section below, so
    # the box carries the one thing every reading produces.
    y = box(2, "the detected events", "a time per event")
    ax.hlines(y - 0.16, 0.6, box_w - 0.6, color=BLACK, lw=1.4)
    point_events(ax, y - 0.1, to_x(rising), size=9)

    for index, (stage, type_change) in enumerate(
        [("conditioning", "signal to signal"), ("detection", "signal to events")]
    ):
        y_gap = -(index + 1) * (box_h + gap) + gap / 2
        ax.annotate(
            "", xy=(box_w / 2, y_gap - gap / 2 + 0.08), xytext=(box_w / 2, y_gap + gap / 2 - 0.08),
            arrowprops=dict(arrowstyle="-|>", color=BLACK, lw=1.8, shrinkA=0, shrinkB=0),
        )
        ax.text(box_w / 2 + 0.3, y_gap + 0.14, stage, ha="left", va="center", fontsize=12, color=BLACK)
        ax.text(box_w / 2 + 0.3, y_gap - 0.2, type_change, ha="left", va="center", fontsize=9.5, color=NOTE)

    bottom = -2 * (box_h + gap) - box_h
    clean(ax, xlim=(-4.3, box_w + 0.4), ylim=(bottom - 0.3, 0.35), title="", title_loc="left")

    fig.tight_layout()
    fig.savefig(OUTDIR / "events_pipeline_model.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# Shared by the conditioning figures, one per cut. They are drawn to a common coordinate system and a
# common output row so the two read as the same operation applied to different signals, even though each
# is now its own figure sitting beside its own paragraph. A third cut gets its own builder and reuses
# these, which is why they are module level rather than closed over.
_CUT_SAMPLES = np.arange(6.0)
_CUT_X_LIM = (-2.2, 6.6)
_CUT_Y_LIM = (-1.45, 4.75)
_CUT_X_END = _CUT_SAMPLES[-1] + 0.7
_CUT_Y_LOW, _CUT_Y_HIGH = 0.0, 0.62


def _draw_cut_output(ax, levels):
    """Draw the two-valued line a cut lands on, placed identically in every conditioning figure."""
    levels = np.asarray(levels)
    two_valued_line(
        ax,
        np.append(_CUT_SAMPLES, _CUT_X_END),
        np.append(levels, levels[-1]),
        y_low=_CUT_Y_LOW,
        y_high=_CUT_Y_HIGH,
    )
    ax.plot(
        _CUT_SAMPLES, _CUT_Y_LOW + levels * (_CUT_Y_HIGH - _CUT_Y_LOW),
        linestyle="none", marker="o", markersize=5.5, color=BLACK,
    )
    for x, level in zip(_CUT_SAMPLES, levels):
        ax.text(x, -0.28, str(level), ha="center", va="top", fontsize=11, color=BLACK)
    ax.text(-0.45, (_CUT_Y_LOW + _CUT_Y_HIGH) / 2, "line", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(2.5, -1.12, "two values, one per sample", ha="center", va="center", fontsize=10.5, color=NOTE)


def build_conditioning_binarize():
    """``binarize`` cuts a magnitude at a level, giving the line below it.

    Its own figure rather than half of a comparison, so it sits beside the paragraph that defines it and
    so a cut added later is a new figure rather than a redrawn one.
    """
    analog = np.array([480, 510, 700, 690, 505, 660], dtype=float)
    cut = 550.0

    def value_to_y(value):
        """Place an analog value in the shared coordinate system."""
        return 1.95 + (value - 450.0) / (720.0 - 450.0) * 2.05

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.vlines(_CUT_SAMPLES, -0.55, 4.35, color=GUIDE, lw=0.9, zorder=0)
    ax.text(-2.1, 4.5, "a magnitude: an analog trace", ha="left", va="center", fontsize=11, color=NOTE)
    ax.plot(_CUT_SAMPLES, value_to_y(analog), marker="o", markersize=6, color=BLACK, lw=1.7)
    for x, value in zip(_CUT_SAMPLES, analog):  # labels sit clear of the cut, so they never sit on it
        above = value > cut
        ax.text(
            x, value_to_y(value) + (0.13 if above else -0.13), f"{value:.0f}",
            ha="center", va="bottom" if above else "top", fontsize=10.5, color=BLACK,
        )
    ax.hlines(value_to_y(cut), -0.4, _CUT_X_END, color=RED, lw=1.6, linestyles=(0, (6, 4)))
    ax.text(-0.45, value_to_y(cut), "cut  ", ha="right", va="center", fontsize=11, color=RED)
    ax.annotate("", xy=(2.5, 1.02), xytext=(2.5, 1.62), arrowprops=dict(arrowstyle="-|>", color=NOTE, lw=1.6))
    ax.text(2.72, 1.32, "cut at the level you give", ha="left", va="center", fontsize=11, color=NOTE)
    _draw_cut_output(ax, (analog > cut).astype(int))
    clean(ax, xlim=_CUT_X_LIM, ylim=_CUT_Y_LIM, title='{"binarize": 550.0}')

    fig.tight_layout()
    fig.savefig(OUTDIR / "events_conditioning_binarize.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_conditioning_bits():
    """``bits`` picks one wire out of a packed integer word, giving the line below it.

    The bit grid is the point: the word's value per sample is not a magnitude, it is several independent
    lines carried at once, and one of them is what a spec asks for.
    """
    word = np.array([13, 15, 15, 11, 9, 1])
    selected_bit = 1

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.vlines(_CUT_SAMPLES, -0.55, 4.35, color=GUIDE, lw=0.9, zorder=0)
    ax.text(-2.1, 4.5, "a packed word: bits are separate wires", ha="left", va="center", fontsize=11, color=NOTE)
    bit_y = {0: 2.02, 1: 2.44, 2: 2.86, 3: 3.28}
    cell = 0.3
    for bit, y in bit_y.items():
        selected = bit == selected_bit
        ax.text(-0.45, y, f"bit {bit}", ha="right", va="center", fontsize=10.5, color=RED if selected else BLACK)
        for x, value in zip(_CUT_SAMPLES, word):
            filled = bool((value >> bit) & 1)
            ax.add_patch(
                mpatches.Rectangle(
                    (x - cell / 2, y - cell / 2), cell, cell,
                    facecolor=BLACK if filled else "white", edgecolor="0.55", lw=0.9, zorder=2,
                )
            )
    ax.text(-0.45, 3.75, "word value", ha="right", va="center", fontsize=10.5, color=BLACK)
    for x, value in zip(_CUT_SAMPLES, word):
        ax.text(x, 3.62, str(value), ha="center", va="bottom", fontsize=10.5, color=BLACK)
    ax.add_patch(
        mpatches.Rectangle(
            (_CUT_SAMPLES[0] - 0.32, bit_y[selected_bit] - 0.25), _CUT_SAMPLES[-1] - _CUT_SAMPLES[0] + 0.64, 0.5,
            facecolor="none", edgecolor=RED, lw=1.6, zorder=3,
        )
    )
    ax.annotate("", xy=(2.5, 1.02), xytext=(2.5, 1.62), arrowprops=dict(arrowstyle="-|>", color=NOTE, lw=1.6))
    ax.text(2.72, 1.32, "read one wire out", ha="left", va="center", fontsize=11, color=NOTE)
    _draw_cut_output(ax, ((word >> selected_bit) & 1).astype(int))
    # The line follows the wire, never the size of the number, and the sample at 9 is where that shows:
    # 9 is larger than 1 but bit 1 is 0 in both, so the line is low across the pair. Spelled out because a
    # reader tracking the word values instead of the boxed row reads the drop as a magnitude threshold.
    ax.text(
        2.5, -1.95,
        "the line follows the wire, not the size of the word:\n"
        "9 is bigger than 1, but bit 1 is 0 in both",
        ha="center", va="center", fontsize=10.5, color=NOTE,
    )
    clean(ax, xlim=_CUT_X_LIM, ylim=(-2.6, 4.75), title='{"bits": [1]}')

    fig.tight_layout()
    fig.savefig(OUTDIR / "events_conditioning_bits.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_five_readings():
    """The detection vocabulary: five readings of one line, in two families.

    Because conditioning always returns a two-valued signal, none of these readings needs a threshold of
    its own; each is a statement about transitions. The three point readings write a timestamp per edge,
    the two durative ones write a timestamp and a duration per pulse, and the rows share the line's time
    axis so each marker sits under the edge it came from.
    """
    edges_up = np.array([1.5, 6.5, 11.5])
    edges_down = np.array([4.0, 9.5, 13.5])
    knots_t = np.array([0.0, 1.5, 4.0, 6.5, 9.5, 11.5, 13.5, 15.0])
    knots_v = np.array([0, 1, 0, 1, 0, 1, 0, 0])
    all_edges = np.sort(np.concatenate([edges_up, edges_down]))

    y_low, y_high = 3.9, 4.6
    rows = {"rising": 2.6, "falling": 2.0, "value_change": 1.4, "high_period": 0.2, "low_period": -0.4}
    x_lim = (-6.9, 26.8)
    right_column = 15.9

    fig, ax = plt.subplots(figsize=(10.5, 5.4))

    ax.vlines(all_edges, -0.72, y_high, color=GUIDE, lw=0.9, zorder=0)
    two_valued_line(ax, knots_t, knots_v, y_low=y_low, y_high=y_high)
    ax.text(-0.5, (y_low + y_high) / 2, "line", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, (y_low + y_high) / 2, "  the two-valued output of conditioning", ha="left", va="center", fontsize=10.5, color=NOTE)

    def group_header(y_rule, text):
        ax.hlines(y_rule, x_lim[0] + 0.2, x_lim[1] - 0.2, color="0.82", lw=0.9)
        ax.text(x_lim[0] + 0.3, y_rule - 0.12, text, ha="left", va="top", fontsize=10.5, color=NOTE)

    group_header(3.35, "point readings: a timestamp per edge, no payload")
    group_header(0.95, "durative readings: a timestamp and a duration per pulse")

    def row_label(name, note):
        y = rows[name]
        ax.text(-0.5, y, name, ha="right", va="center", fontsize=11, color=BLACK)
        ax.text(right_column, y, "  " + note, ha="left", va="center", fontsize=10.5, color=NOTE)

    ax.hlines([rows["rising"], rows["falling"], rows["value_change"]], -0.15, 15.4, color="0.75", lw=1.2)
    point_events(ax, rows["rising"] + 0.1, edges_up)
    point_events(ax, rows["falling"] + 0.1, edges_down)
    point_events(ax, rows["value_change"] + 0.1, all_edges)
    row_label("rising", "each low-to-high transition")
    row_label("falling", "each high-to-low transition")
    row_label("value_change", "every transition, both directions, in one table")

    for start, stop in zip(edges_up, edges_down):
        durative_event(ax, rows["high_period"], start, stop)
    for start, stop in zip(edges_down[:-1], edges_up[1:]):
        durative_event(ax, rows["low_period"], start, stop)
    row_label("high_period", "each rising edge to the next falling one")
    row_label("low_period", "each falling edge to the next rising one")

    clean(ax, xlim=x_lim, ylim=(-0.95, 5.05), title="Five readings of the same line")
    fig.tight_layout()
    fig.savefig(OUTDIR / "events_five_readings.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_several_levels():
    """One signal read at three cut points: three specs on the same signal, giving three nested events.

    A spec holds exactly one cut, so a trace you want read at three levels becomes three specs, each with
    its own cut and its own ``event_name``. The resulting ``high_period`` spans nest, and the band the
    signal sits in at any instant is how many cut points are currently exceeded, so nothing is lost.
    """
    knots_t = np.array([0.0, 1.0, 1.9, 3.1, 4.0, 5.2, 6.0, 7.2, 8.1, 9.3, 10.2, 12.0])
    knots_v = np.array([0.30, 0.30, 1.45, 1.45, 2.50, 2.50, 3.45, 3.45, 2.50, 1.45, 0.30, 0.30])
    t = np.linspace(0.0, 12.0, 1201)
    trace = np.interp(t, knots_t, knots_v)
    half_window = 30  # a short box filter, so the plateaus survive but the ramps read as analog
    padded = np.pad(trace, half_window, mode="edge")
    trace = np.convolve(padded, np.ones(2 * half_window + 1) / (2 * half_window + 1), mode="same")[half_window:-half_window]

    cuts = [(3.0, "above_high", -0.8), (2.0, "above_mid", -1.6), (1.0, "above_low", -2.4)]
    x_lim = (-2.9, 18.6)
    right_column = 12.7

    fig, ax = plt.subplots(figsize=(10.5, 7.6))

    ax.plot(t, trace, color=BLACK, lw=2.0)
    ax.text(-0.35, 0.30, "XA1 (analog)", ha="right", va="center", fontsize=11, color=BLACK)

    for level, name, row_y in cuts:
        above = trace >= level
        start, stop = t[above][0], t[above][-1]
        ax.hlines(level, -0.2, 12.4, color=RED, lw=1.5, linestyles=(0, (6, 4)))
        ax.text(right_column, level, f'  {{"binarize": {level}}}  {name}', ha="left", va="center", fontsize=11, color=RED)
        for crossing in (start, stop):
            ax.vlines(crossing, row_y, level, color="0.78", lw=0.9, linestyles=(0, (2, 3)), zorder=0)
        durative_event(ax, row_y, start, stop, cap=0.16)
        ax.text(-0.35, row_y, name, ha="right", va="center", fontsize=11, color=BLACK)
        ax.text(right_column, row_y, f"  high_period, {stop - start:.1f} s", ha="left", va="center", fontsize=10.5, color=NOTE)

    ax.text(
        -2.75, -0.25, "three specs on the same signal, one cut each, so the spans nest",
        ha="left", va="center", fontsize=10.5, color=NOTE,
        bbox=dict(facecolor="white", edgecolor="none", pad=2.0),  # sits over the drop lines, so it needs a backing
    )

    # -- the reconstructed band, at the bottom -----------------------------------------------------
    ax.hlines(-3.05, x_lim[0] + 0.2, x_lim[1] - 0.2, color="0.82", lw=0.9)
    band = sum((trace >= level).astype(int) for level, _, _ in cuts)
    band_base, band_step = -4.0, 0.22
    ax.plot(t, band_base + band * band_step, color=REF, lw=2.0)
    ax.text(-0.35, band_base + 1.5 * band_step, "band", ha="right", va="center", fontsize=11, color=REF)
    boundaries = np.flatnonzero(np.diff(band)) + 1
    for run in np.split(np.arange(t.size), boundaries):
        if t[run[-1]] - t[run[0]] < 0.55:
            continue
        centre = (t[run[0]] + t[run[-1]]) / 2
        ax.text(centre, band_base + band[run[0]] * band_step + 0.1, str(band[run[0]]), ha="center", va="bottom", fontsize=11, color=REF)
    ax.text(
        right_column, band_base + 1.5 * band_step,
        "  the band is how many cut points\n  are currently exceeded, so the\n  original band sequence reconstructs",
        ha="left", va="center", fontsize=10.5, color=NOTE,
    )

    clean(ax, xlim=x_lim, ylim=(-4.6, 4.3), title="One signal, three cut points: three nested durative event types")
    fig.tight_layout()
    fig.savefig(OUTDIR / "events_several_levels.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_high_period_limit():
    """Where a durative reading stops being about the pulse: a duration is measured in sampling periods.

    Every pulse in this train is the same width, but the sampling grid is coarser than the pulse, so one
    pulse covers a single sample and the next covers two. The duration written out is 7.69 ms or 15.38 ms
    depending only on where the pulse landed on the grid. ``rising`` writes one time per pulse instead and
    is the honest reading for such a line.
    """
    period = 1000.0 / 130.0  # a 130 Hz line samples every 7.69 ms
    grid = np.arange(0.0, 100.0, period)
    pulse_starts = np.array([12.0, 45.0, 78.0])
    pulse_width = 9.0

    y_pulse_low, y_pulse_high = 3.0, 3.8
    y_samp_low, y_samp_high = 1.75, 2.45
    y_period, y_rising = 0.85, 0.05
    x_lim = (-33.0, 152.0)
    right_column = 101.0

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ax.vlines(grid, -0.35, y_pulse_high + 0.05, color=GUIDE, lw=0.9, zorder=0)

    # -- the real pulse train ----------------------------------------------------------------------
    knots_t, knots_v = [0.0], [0]
    for start in pulse_starts:
        knots_t += [start, start + pulse_width]
        knots_v += [1, 0]
    knots_t.append(100.0)
    knots_v.append(0)
    two_valued_line(ax, knots_t, knots_v, y_low=y_pulse_low, y_high=y_pulse_high)
    ax.text(-1.5, (y_pulse_low + y_pulse_high) / 2, "the real pulse", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, (y_pulse_low + y_pulse_high) / 2, "  every pulse is 9 ms wide", ha="left", va="center", fontsize=10.5, color=NOTE)
    for start in pulse_starts:
        ax.annotate(
            "", xy=(start, y_pulse_high + 0.3), xytext=(start + pulse_width, y_pulse_high + 0.3),
            arrowprops=dict(arrowstyle="<->", color=NOTE, lw=1.1),
        )
        ax.text(start + pulse_width / 2, y_pulse_high + 0.38, "9 ms", ha="center", va="bottom", fontsize=10, color=NOTE)

    # -- what the sampled line looks like ----------------------------------------------------------
    inside = np.zeros(grid.size, dtype=int)
    for start in pulse_starts:
        inside |= ((grid >= start) & (grid < start + pulse_width)).astype(int)
    two_valued_line(ax, np.append(grid, 100.0), np.append(inside, inside[-1]), y_low=y_samp_low, y_high=y_samp_high)
    levels = np.where(inside > 0, y_samp_high, y_samp_low)
    ax.plot(grid[inside == 0], levels[inside == 0], linestyle="none", marker="o", markersize=5, markerfacecolor="white", markeredgecolor="0.5")
    ax.plot(grid[inside == 1], levels[inside == 1], linestyle="none", marker="o", markersize=6, color=BLACK)
    ax.text(-1.5, (y_samp_low + y_samp_high) / 2, "as sampled", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, (y_samp_low + y_samp_high) / 2, "  samples 7.69 ms apart (130 Hz)", ha="left", va="center", fontsize=10.5, color=NOTE)

    # -- the durations that get written out --------------------------------------------------------
    high_indices = np.flatnonzero(inside)
    runs = np.split(high_indices, np.flatnonzero(np.diff(high_indices) > 1) + 1)
    for run in runs:
        start, stop = grid[run[0]], grid[run[-1] + 1]
        durative_event(ax, y_period, start, stop, cap=0.14)
        ax.text(
            (start + stop) / 2, y_period + 0.2,
            f"{stop - start:.2f} ms\n({run.size} sample{'s' if run.size > 1 else ''})",
            ha="center", va="bottom", fontsize=10, color=RED,
        )
    ax.text(-1.5, y_period, "high_period", ha="right", va="center", fontsize=11, color=RED)
    ax.text(right_column, y_period, "  what is written is the grid,\n  not the pulse", ha="left", va="center", fontsize=10.5, color=NOTE)

    # -- the honest reading ------------------------------------------------------------------------
    ax.hlines(y_rising, -1.0, 100.0, color=BLACK, lw=2.4)
    point_events(ax, y_rising + 0.13, [grid[run[0]] for run in runs])
    ax.text(-1.5, y_rising + 0.13, "rising", ha="right", va="center", fontsize=11, color=BLACK)
    ax.text(right_column, y_rising + 0.1, "  one time per pulse: use this", ha="left", va="center", fontsize=10.5, color=NOTE)

    ax.text(
        -33.0 + 1.0, -1.05,
        "Every pulse is identical, but a 9 ms pulse on a 7.69 ms grid covers one sample or two depending on where it started.\n"
        "A durative reading earns its place once the high period covers roughly ten samples or more.",
        ha="left", va="center", fontsize=10.5, color=NOTE,
    )

    clean(ax, xlim=x_lim, ylim=(-1.6, 4.6), title="A duration is measured in sampling periods, so a fast pulse reads the grid")
    fig.tight_layout()
    fig.savefig(OUTDIR / "events_high_period_limit.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    """Generate every event-extraction figure into this directory."""
    build_pipeline_model()
    build_two_stages()
    build_conditioning_binarize()
    build_conditioning_bits()
    build_five_readings()
    build_several_levels()
    build_high_period_limit()
    print(
        "wrote events_two_stages.png, events_conditioning_binarize.png, events_conditioning_bits.png, "
        "events_five_readings.png, events_several_levels.png and events_high_period_limit.png"
    )


if __name__ == "__main__":
    main()
