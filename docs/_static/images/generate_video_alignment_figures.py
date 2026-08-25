"""Generate the diagram for the "time align behavior videos to other modalities" how-to.

Run from the repository root::

    uv run --with matplotlib --with numpy python docs/_static/images/generate_video_alignment_figures.py

Produces two figures:

- ``video_setup_free_running.png`` and ``video_setup_triggered.png``  - one per setup the guide is
  organised by, free-running against triggered being how cameras are documented and the fact about the
  rig's intent that decides everything else, and within each the shapes
  the session's files and its digital line can take, over the recording system that runs the whole session
  and carries the session clock. Rig only: no method names, since which call places a setup belongs in the
  prose beside it and would date the figure.
- ``video_wiring.png``            - the four ways the camera and the recording system are wired, which is
  what decides how well a rig can be aligned: the camera reports, the camera is commanded, a third box
  drives both, or there is no cable at all.

One figure rather than one per setup, deliberately: the third row of the first group and the first of the
second are the same files on disk, and only the line underneath tells them apart, which is the whole
reason the interface asks.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

BLACK = "black"
RED = "firebrick"
FILL = "#dce7f0"  # the body of a video file
EDGE = "#2f6f9f"  # its outline, and the colour of anything derived from the camera
NOTE = "0.35"  # captions and asides
OUTDIR = Path(__file__).parent

FILE_HEIGHT = 0.38
PULSE_DROP = 0.42  # how far below a file's baseline the digital line sits
SYSTEM_DROP = 0.86  # and how far below it the recording system's own band sits
SYSTEM_HEIGHT = 0.20
ROW_PITCH = 1.55
GROUP_GAP = 0.7
LABEL_X = 0.42  # right edge of the left-hand label column
GROUP_X = -2.75  # left edge of the group headings


def video_files(ax, *, y, spans, labels):
    """Draw one row of video files as labelled blocks sitting on a common baseline."""
    for (start, stop), label in zip(spans, labels):
        ax.add_patch(
            mpatches.Rectangle(
                (start, y), stop - start, FILE_HEIGHT, facecolor=FILL, edgecolor=EDGE, lw=1.6, joinstyle="miter"
            )
        )
        ax.text((start + stop) / 2, y + FILE_HEIGHT / 2, label, ha="center", va="center", fontsize=8.5, color=EDGE)


def digital_line(ax, *, y, pulses, label):
    """Draw the recording system's line as a baseline carrying an upward tick per pulse."""
    ax.hlines(y, 0.55, 9.6, color=NOTE, lw=1.2)
    pulses = np.asarray(pulses, dtype=float)
    if pulses.size:
        ax.vlines(pulses, y, y + 0.18, color=RED, lw=1.3)
    ax.text(LABEL_X, y + 0.05, label, ha="right", va="center", fontsize=8, color=NOTE)


def recording_system(ax, *, y):
    """The other modality, drawn in every case: it runs the whole session and carries the clock.

    Repeated per row rather than once for the figure, because it is present in every one of these setups
    and the video is being placed against it in all of them.
    """
    ax.add_patch(
        mpatches.Rectangle(
            (0.55, y), 9.05, SYSTEM_HEIGHT, facecolor="0.93", edgecolor="0.6", lw=1.2, joinstyle="miter"
        )
    )
    ax.text(5.075, y + SYSTEM_HEIGHT / 2, "recording system", ha="center", va="center", fontsize=7.5, color="0.35")


def row_label(ax, *, y, title):
    """The name of the setup, at the left margin and level with the files it describes."""
    ax.text(LABEL_X, y + FILE_HEIGHT / 2, title, ha="right", va="center", fontsize=9.5, color=BLACK)


def frame_pulses(spans, *, interval):
    """A pulse per frame, present only while a file is being written."""
    return np.concatenate([np.arange(start, stop, interval) for start, stop in spans])


def build_setup_figure(*, file_name, title, rows):
    """One setup, drawn on its own: its cases stacked over the recording system and the session clock.

    One figure per setup rather than all three in one, because they are read one at a time, beside the
    section that teaches them, and a single stack of seven cases is taller than a screen.
    """
    figure, ax = plt.subplots(figsize=(9.4, 1.45 * len(rows) + 1.6))
    # Centred over the same x range the axes spans, so it sits over the drawing rather than over the
    # row-label gutter to its left.
    ax.text(
        (GROUP_X - 0.1 + 10.0) / 2,
        FILE_HEIGHT + 0.42,
        title,
        ha="center",
        va="center",
        fontsize=11,
        color=BLACK,
        fontweight="semibold",
    )

    y = 0.0
    for row_title, spans, labels, pulses, line_label in rows:
        row_label(ax, y=y, title=row_title)
        video_files(ax, y=y, spans=spans, labels=labels)
        digital_line(ax, y=y - PULSE_DROP, pulses=pulses, label=line_label)
        recording_system(ax, y=y - SYSTEM_DROP)
        y -= ROW_PITCH

    # The session clock every row is expressed on, drawn once under the stack.
    baseline_y = y + ROW_PITCH - SYSTEM_DROP - 0.55
    ax.annotate(
        "", xy=(9.7, baseline_y), xytext=(0.55, baseline_y), arrowprops=dict(arrowstyle="-|>", color=BLACK, lw=1.4)
    )
    ax.text(LABEL_X, baseline_y, "session clock", ha="right", va="center", fontsize=9, color=BLACK)
    ax.vlines(0.55, baseline_y - 0.14, baseline_y + 0.14, color=BLACK, lw=1.4)
    ax.text(0.55, baseline_y - 0.28, "session_start_time", ha="center", va="top", fontsize=8, color=NOTE)
    # A guide at the session start, so the gap before each row's first file reads as its offset.
    ax.vlines(0.55, baseline_y, FILE_HEIGHT + 0.2, color="0.8", lw=1.0, linestyle=(0, (4, 4)))

    ax.set_xlim(GROUP_X - 0.1, 10.0)
    ax.set_ylim(baseline_y - 0.6, FILE_HEIGHT + 0.62)
    ax.axis("off")
    figure.tight_layout()
    figure.savefig(OUTDIR / file_name, dpi=200, bbox_inches="tight")
    plt.close(figure)


def build_recording_setups():
    """The three setups, one figure each, all on the same session clock so they compare directly."""
    session = [(1.0, 9.2)]
    split = [(1.0, 3.7), (3.7, 6.4), (6.4, 9.1)]
    trials = [(1.0, 2.6), (4.0, 5.6), (7.0, 8.6)]

    build_setup_figure(
        file_name="video_setup_free_running.png",
        title="A free-running camera",
        rows=[
            ("Known offset", session, ["session.avi"], [1.0], "start pulse"),
            (
                "A pulse per frame",
                session,
                ["session.avi"],
                frame_pulses(session, interval=0.16),
                "frame line",
            ),
            ("Written to several files", split, ["part_01", "part_02", "part_03"], [], "either of the above"),
        ],
    )
    build_setup_figure(
        file_name="video_setup_triggered.png",
        title="A triggered camera",
        rows=[
            (
                "Trial onsets only",
                trials,
                ["trial_01", "trial_02", "trial_03"],
                [start for start, _ in trials],
                "trigger line",
            ),
            (
                "A pulse per frame",
                trials,
                ["trial_01", "trial_02", "trial_03"],
                frame_pulses(trials, interval=0.16),
                "frame line",
            ),
        ],
    )


BOX_BOTTOM = 0.30
BOX_HEIGHT = 0.26
BOX_MIDDLE = BOX_BOTTOM + BOX_HEIGHT / 2
BOX_TOP = BOX_BOTTOM + BOX_HEIGHT


def wiring_endpoints(ax, *, title, note):
    """The camera on the left and the recording system on the right, at the same place in every panel.

    Only what runs between them changes from panel to panel, which is the whole distinction being drawn,
    so the endpoints are shared and drawn once.
    """
    ax.set_title(title, fontsize=11, loc="left", pad=10)
    for x, label, is_camera in ((0.03, "Camera", True), (0.67, "Recording system", False)):
        ax.add_patch(
            mpatches.Rectangle(
                (x, BOX_BOTTOM),
                0.30,
                BOX_HEIGHT,
                facecolor=FILL if is_camera else "0.93",
                edgecolor=EDGE if is_camera else "0.55",
                lw=1.6,
                joinstyle="miter",
            )
        )
        ax.text(
            x + 0.15, BOX_MIDDLE, label, ha="center", va="center", fontsize=9, color=EDGE if is_camera else "0.25"
        )
    ax.text(0.5, 0.19, note, ha="center", va="top", fontsize=8.5, color=NOTE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0.0, 0.95)
    ax.axis("off")


def wiring_panel(ax, *, title, signal_travels_to_system, arrow_label, note):
    """One cable, pointing one way or the other."""
    wiring_endpoints(ax, title=title, note=note)
    tail, head = (0.35, 0.65) if signal_travels_to_system else (0.65, 0.35)
    ax.annotate(
        "", xy=(head, BOX_MIDDLE), xytext=(tail, BOX_MIDDLE), arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.8)
    )
    ax.text(0.50, BOX_MIDDLE + 0.05, arrow_label, ha="center", va="bottom", fontsize=8.5, color=RED, linespacing=1.4)


def sync_panel(ax, *, title, arrow_label, note):
    """A third box driving both, so the same instants are written down on both clocks."""
    wiring_endpoints(ax, title=title, note=note)
    ax.add_patch(
        mpatches.Rectangle(
            (0.35, 0.74), 0.30, 0.17, facecolor="1.0", edgecolor=RED, lw=1.6, joinstyle="miter", zorder=3
        )
    )
    ax.text(0.50, 0.825, "Sync source", ha="center", va="center", fontsize=9, color=RED, zorder=4)
    for x_head in (0.18, 0.82):
        ax.annotate(
            "",
            xy=(x_head, BOX_TOP),
            xytext=(0.50 - 0.10 if x_head < 0.5 else 0.50 + 0.10, 0.74),
            arrowprops=dict(arrowstyle="-|>", color=RED, lw=1.8),
        )
    # Two short lines rather than one long one, so the label sits inside the wedge the arrows leave.
    ax.text(0.50, 0.71, arrow_label, ha="center", va="top", fontsize=8.5, color=RED, linespacing=1.4)


def build_wiring():
    """The three arrangements, which decide how well a rig can be aligned."""
    figure, axes = plt.subplots(2, 2, figsize=(10.4, 5.8))
    axes = axes.ravel()
    wiring_panel(
        axes[0],
        title="The camera reports",
        signal_travels_to_system=True,
        arrow_label="frame-out line\none pulse per frame",
        note="Each pulse is evidence that a frame was exposed, so the\npulse count can be checked against the file on disk.",
    )
    wiring_panel(
        axes[1],
        title="The camera is commanded",
        signal_travels_to_system=False,
        arrow_label="trigger line\none pulse per trial",
        note="The trigger is recorded on its way out, so its time is known,\nbut the delay to the first exposed frame is not measured.",
    )
    sync_panel(
        axes[2],
        title="A shared sync source",
        arrow_label="one line\ninto both",
        note="Neither system commands the other. Both write down when each\npulse arrived, so the pairs map one clock onto the other.",
    )
    # The endpoints with nothing between them, which is the fourth arrangement rather than a blank cell.
    wiring_endpoints(
        axes[3],
        title="No cable",
        note="Nothing relates the two clocks after the instant someone\nwrote down, and nothing in either file records that either.",
    )
    figure.tight_layout()
    figure.savefig(OUTDIR / "video_wiring.png", dpi=200, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    build_recording_setups()
    build_wiring()
