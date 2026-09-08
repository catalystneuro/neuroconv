.. _align_external_video:

How to Time Align Behavior Videos to Other Modalities
=====================================================

A camera is its own acquisition system and it is almost never on the same clock as the rest of the rig.
Its frame times are on its own clock. Before a frame can be compared with another signal, those times have
to be expressed on the session clock. This guide is about how to do that.

Most rigs record behavior video next to something else: extracellular electrophysiology, fiber
photometry, optical imaging, an operant box. The camera is on its own clock in all of these, so the
recipes below apply to all of them. What changes from rig to rig is how the camera split its output into
files and what the cable between the two systems carried.

This guide covers :py:class:`~neuroconv.datainterfaces.behavior.video.externalvideointerface.ExternalVideoInterface`.
It leaves the video on disk and writes an ``ImageSeries`` that points at it. The general alignment methods
are described in the :doc:`temporal alignment user guide <../user_guide/temporal_alignment>`.

What the session produced
-------------------------

Two things: a recording that ran for the whole session, and video that ran either for the whole session or
only during the trials. The recording is the other modality, whichever it is. It matters here for two
reasons. Its clock is normally the session
clock, because everything else in the rig is wired into it. And its digital inputs are where the camera's
timing signal was recorded, so it is also what measures the video.

The video comes in one of two arrangements and each has its own section below. The figures all follow the
same layout: the video files on top, the digital line that timed them below, and the recording system
running underneath. The dashed line marks the session start, so the gap before the first file of a row is
that row's offset.

**A free-running camera.** It starts with the session and stops with it. The recording software may have
written one file or several, depending on a file size limit or a timer. That does not change the timing.
The frames are one continuous stream either way.

.. image:: ../_static/images/video_setup_free_running.png
   :width: 720px
   :align: center
   :alt: Three cases on one session clock. A single long block with one start pulse beneath it. The same
         block over a line pulsing continuously. And three blocks touching end to end, written by a
         recorder that rotated its output, whose line is labelled "either of the above" because the split
         is a storage detail rather than a timing one.

**A triggered camera.** A pulse starts it at each trial, so the session produces one file per trial with
real gaps between them. This is the trialized case. Here the gaps are intended.

.. image:: ../_static/images/video_setup_triggered.png
   :width: 720px
   :align: center
   :alt: Two cases on one session clock. Three short blocks separated by gaps, over a trigger line carrying
         one pulse at each block's start. And the same separated blocks over a line pulsing only while a
         block runs, so the pulses arrive in three bursts.

The two figures show the same three files, touching in one and separated in the other. The files on disk
look identical in both cases. Only knowing what the rig did tells them apart.

How they are wired, and where the times come from
-------------------------------------------------

There is usually a cable between the camera and the recording system, and what runs along it decides how
precise the alignment can be. The arrangement above says how many files you have to place. The cable says
how well you can place each one.

.. image:: ../_static/images/video_wiring.png
   :width: 760px
   :align: center
   :alt: Four panels in a two by two grid, each holding a camera box on the left and a recording system box
         on the right, so the only thing that differs between them is what runs in between. In "the camera
         reports" an arrow runs from the camera to the recording system, labelled frame-out line, one pulse
         per frame, with a note that each pulse is evidence a frame was exposed so the count can be checked
         against the file. In "the camera is commanded" the arrow runs the other way, from the recording
         system to the camera, labelled trigger line, one pulse per trial, with a note that the trigger is
         recorded on its way out so its time is known but the delay to the first exposed frame is not
         measured. In "a shared sync source" a third box sits above the two and one line fans out from it
         into both, with a note that neither system commands the other and both write down when each pulse
         arrived, so the pairs map one clock onto the other. In "no cable" the two boxes stand alone with
         nothing between them.

**The camera reports.** The camera has a frame-out or strobe pin that fires each time it exposes a frame,
and the pin is wired into a digital input on the recording system. Every frame then has a time measured on
the session clock. This is the best case. It corrects drift, and since each pulse means a frame was
exposed, you can check the pulse count against the frame count in the file.

**The camera is commanded.** The line runs the other way, from the controller or the recording system into
the camera's trigger input. The same line is recorded on a digital input, so the time of the command is
known. But the command is not a confirmation. The delay between the trigger and the first exposed frame is
not measured and nothing in the file records it. Within a trial the frame times come from the nominal frame
rate instead of a measurement.

**A shared sync source.** A third device, an Arduino or a Bonsai workflow, sends pulses into a
general-purpose input on the camera and into a digital input on the recording system at the same time.
Neither system commands the other. Both write down when each pulse arrived. The same instants then appear
in the camera's metadata and in the recording, and those pairs define the map between the two clocks.
Pulses are often sent in coded groups, a "barcode", so the pairs cannot be matched wrong even if one system
missed a pulse.

**No cable.** Then all you have is what someone wrote down, usually a start time, and nothing that relates
the two clocks after that.

One combination has no recipe: one file per trial and no line. Nothing in the recording says where the
trials sit. The starting times have to come from somewhere else, a behavioral log or the modification times
of the files, and you set them by hand.

**Reading the line.** Whichever way it points, the line ends on a digital input of the recording system and
is read the same way. Configure the line and read the event times back without writing anything:

.. code-block:: python

    from neuroconv.datainterfaces import IntanDigitalInterface, IntanRecordingInterface

    recording_interface = IntanRecordingInterface(file_path="session.rhd")
    digital_interface = IntanDigitalInterface(
        file_path="session.rhd",
        detection_configuration={
            "DIGITAL-IN-02": [
                {
                    "signal_conditioning": {"binarize": "midpoint"},
                    "detection": "rising",
                    "event_name": "camera_frame",
                }
            ]
        },
    )

    frame_pulse_times = digital_interface.get_event_times("camera_frame")

The pulses are on the clock of the system that recorded them. Times read from an Intan digital line are on
the Intan clock, so the frames you give them to land on that clock too. That is the session clock as long
as the recording interface is not shifted, and that is the usual arrangement: one system is the master
because everything else is wired into it, and every other stream is expressed in its clock. If you do shift
the recording, shift it before you read the pulses, so they come back with the shift included.

What goes in ``detection_configuration`` is :ref:`how a signal becomes a line <events_conditioning>` and
:ref:`how a line becomes events <events_detection>`.

A free-running camera
---------------------

One camera, running for the whole session, writing one file. The interface writes one ``ImageSeries``. The
only question is what timed it.

.. code-block:: python

    from neuroconv.datainterfaces import ExternalVideoInterface

    interface = ExternalVideoInterface(file_paths=["session.avi"], video_name="BehaviorCamera")
    interface.alignment.keys()
    # ('session',)

Each video file is addressed for alignment by the stem of its path, so a single video has one key. A single
video also writes with no alignment call at all. That claims it started exactly at ``session_start_time``,
so check it instead of accepting it.

If a session has more than one camera, give each interface its own ``metadata_key``. The key addresses that
camera's entry in ``metadata["Behavior"]["ExternalVideos"]`` and keeps the two ``ImageSeries`` and their
devices apart. It is also what a ``PoseEstimation`` container names to say which video its keypoints were
tracked from (see :ref:`annotate_pose_metadata`).

**Known offset.** All you know is when the camera started relative to the session start.

.. code-block:: python

    interface.alignment.shift_times(12.5)

The frame times come from the video's own frame rate, shifted by the offset. This corrects the start and
nothing else. Two clocks drift apart, so on a long session the error at the end of the video grows and no
single number can fix it.

**A pulse per frame.** The camera sent a pulse for every frame it captured, so the recording system
timestamped each frame directly. This is accurate and corrects drift. Prefer it whenever the pulses exist.

.. code-block:: python

    frame_pulse_times = digital_interface.get_event_times("camera_frame")

    interface.alignment["session"].set_times(frame_pulse_times)

You do not have to count them first. The interface throws an error when the number of times does not match
the number of frames and says by how much. Many more pulses than frames usually means the line was running
before the camera started, so you want the tail of the pulses. A few pulses short means dropped frames. Do
not trim the pulses to fit. Most recorders stamp each frame with its index instead of its time, so a
dropped frame closes the gap instead of leaving one, and every later frame is written early. The pulses are
the only record of where the missing frames were.

**The camera keeps its own clock.** The camera writes a timestamp for every frame it captures, and a shared
sync source sends pulses into both systems. The camera's log then holds a time for every frame and a time
for every sync pulse, all on the camera's clock. The frame times are already one per frame but on the wrong
clock. The sync pulses were written down by both systems, so they are what maps one clock onto the other.
A shift will not do it because the two clocks drift.

.. code-block:: python

    # Read from whatever the camera's acquisition software wrote, both on the camera's own clock.
    frame_times = ...  # one per frame
    camera_sync_times = ...  # one per sync pulse

    # The same pulses, as the recording system timestamped them, on the session clock.
    recording_system_sync_times = digital_interface.get_event_times("camera_sync")

    interface.alignment["session"].set_times(frame_times)
    interface.alignment["session"].remap_times(
        local_sync_times=camera_sync_times,
        reference_sync_times=recording_system_sync_times,
    )

Set the times from the log first. That puts the video on the camera's clock. Then remap that clock onto the
session clock. The two pulse arrays are paired by position, so they have to be the same length and in the
same order, and a pulse that only one system recorded has to be dropped from both. Frames between two
pulses are interpolated. No data is resampled, only the times move.

``remap_times`` can also be called on ``alignment`` with no key, and then it re-times every file of the
interface at once. The drift belongs to the camera's clock, not to one file, so that is the form for a
triggered camera on its own clock: place each of its files first, then one ``alignment.remap_times`` call
corrects all of them.

**When the recorder split the session into several files.** Still one continuous recording, but the software
opened a new file every few minutes, so it arrives as several. If the recorder dropped no frames between
closing one file and opening the next, the files run back to back and each starts where the previous one
ended. The frame counts and rates give you those starts. This is also what the interface assumes when
several files are written and nothing has been said about them, and it warns you because it is a choice you
did not make. To make it explicit, place each file where the previous one ends:

.. code-block:: python

    import numpy as np

    interface = ExternalVideoInterface(file_paths=["part_01.avi", "part_02.avi", "part_03.avi"])

    durations = np.array(interface.get_header_frame_counts()) / np.array(interface.get_header_frame_rates())
    starting_times = np.concatenate([[0.0], np.cumsum(durations)[:-1]])

    for segment_key, start in zip(interface.alignment.keys(), starting_times):
        interface.alignment[segment_key].start_at(start)

``start_at`` moves one file so that its first frame sits at the time you give on the session clock. It reads
nothing inside the file. If the camera also started late, shift the interface as in the known-offset case
and the files keep their layout. Nothing in the files records a gap between them if there was one. If the
rig has a frame-out line, use it and take each file's times from the pulses instead, as in the trialized
case below.

A triggered camera, one file per trial
--------------------------------------

One camera again, but a pulse triggers it at the start of each trial, so the session produces one file per
trial with real gaps between them. Each file has to be placed on its own, with ``alignment[key].start_at``.

``ExternalVideoInterface(file_paths=[...])`` writes a **single** ``ImageSeries`` with one ``external_file``
entry per input file. A session of forty trials is one container with forty entries. The container carries
the trial order in the ``external_file`` list and the frame numbering in ``starting_frame``, over one
timestamps vector, so a reader gets the structure of the session from the object itself. Split into forty
containers, that structure would have to be reconstructed from their names. ``starting_frame`` marks where
each file begins within the series. It is computed from the frame counts and never appears in your code.

.. code-block:: python

    interface = ExternalVideoInterface(file_paths=["trial_01.avi", "trial_02.avi", "trial_03.avi"])
    interface.alignment.keys()
    # ('trial_01', 'trial_02', 'trial_03')

If two trials wrote files with the same name in different folders, rename them. The stem is how a file is
addressed, so it has to be unique. The interface throws an error at construction instead of silently
merging the two.

**Trial onsets only.** The digital line recorded the triggers and nothing else.

.. code-block:: python

    trial_onsets = digital_interface.get_event_times("camera_trigger")
    segment_keys = interface.alignment.keys()
    assert len(trial_onsets) == len(segment_keys)

    for segment_key, onset in zip(segment_keys, trial_onsets):
        interface.alignment[segment_key].start_at(onset)

Each file is placed where its trigger fired. Within a file the frame times come from the nominal frame
rate, so the drift caveat from the known-offset case applies again, per trial instead of once for the
session. That is usually fine. A trial is short and a camera does not drift far in ten seconds.

``start_at`` states where a file begins instead of how far to move it. Running the loop twice leaves the
files where it says instead of moving them twice. A ``shift_times`` on the interface afterwards moves every
file together.

Within a trial the frame times depend entirely on the rate the container declares, and a header can be
wrong without the file saying so. An IBL Brain Wide Map camera declares exactly 150 fps while the
hardware-measured rate is 150.4083. That is 11.5 seconds of error by the end of a session, on frames that
are evenly spaced. Over a ten-second trial the error is a millisecond and does not matter. Over a long
trial, or a session written as one file, use the pulses below instead.

**A pulse per frame.** This is the best case and the one to ask for when a rig is being designed. A
frame-out line that is active only while the camera runs gives you both things at once. The pulses arrive
in bursts, one burst per trial. The burst onsets are where the files start and the pulses within a burst
are the frame times of that file.

.. code-block:: python

    import numpy as np

    frame_pulse_times = digital_interface.get_event_times("camera_frame")

    # The gap between trials is far larger than the frame interval, so the split is unambiguous.
    frame_interval = np.median(np.diff(frame_pulse_times))
    gap_indices = np.flatnonzero(np.diff(frame_pulse_times) > 10 * frame_interval) + 1
    bursts = np.split(frame_pulse_times, gap_indices)

    segment_keys = interface.alignment.keys()

    assert len(bursts) == len(segment_keys), f"{len(bursts)} bursts for {len(segment_keys)} files."
    for segment_key, burst in zip(segment_keys, bursts):
        interface.alignment[segment_key].set_times(burst)

Keep the assertion on the burst count. Without it ``zip`` stops at the shorter of the two lists and the
result looks fine. The interface checks the count within a file and throws an error when a burst does not
have one pulse per frame. In either case the pulse record and the files disagree about
the session, and you have to find the cause before the timestamps mean anything. The usual cause is a trial
that was triggered but never reached disk. That puts every later file onto the pulses of the wrong trial.

**A second line makes the split more robust.** If the rig also has a line that marks when each trial began,
bin the frame pulses between consecutive trial onsets instead of splitting on the gaps. This needs no
threshold. A trial that recorded no frames comes back as an empty burst and the interface's count check
catches it, instead of it being silently merged into its neighbour.

.. code-block:: python

    trial_onsets = digital_interface.get_event_times("camera_trigger")
    bursts = np.split(frame_pulse_times, np.searchsorted(frame_pulse_times, trial_onsets[1:]))

One case this does not cover: a camera that free-runs while only some of its frames are written to disk.
The counts no longer say which frames were saved, so neither the gaps nor the onsets can reconstruct the
mapping. No alignment recipe repairs this. It needs per-frame metadata from the acquisition software.

Recording which file is which trial
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A single ``ImageSeries`` with several ``external_file`` entries has no per-file timing metadata. The
structure is in the concatenated ``timestamps`` and in ``starting_frame``, but no field says "file 2 covers
trial 2 and ran from here to here", and a single file within the series cannot be addressed on its own.
That is a limitation of the schema, tracked in
`nwb-schema#677 <https://github.com/NeurodataWithoutBorders/nwb-schema/issues/677>`_. Write the mapping
somewhere that can hold it: a column on the trials table when the segments are your trials, or a
``TimeIntervals`` of its own when a trial begins before the camera does or ends after it. See
:ref:`adding_trials` for what else a trials table can carry.

.. code-block:: python

    durations = np.array(interface.get_header_frame_counts()) / np.array(interface.get_header_frame_rates())

    nwbfile.add_trial_column(name="video_file", description="The external_file entry holding this trial's frames.")
    for onset, duration, file_path in zip(trial_onsets, durations, file_paths):
        nwbfile.add_trial(start_time=onset, stop_time=onset + duration, video_file=str(file_path))

A setup this guide does not cover
---------------------------------

The recipes here come from the rigs we have seen, and rigs vary more than a guide can cover. If yours does
not fit any of them, or fits but produces something these calls cannot express, please
`open an issue <https://github.com/catalystneuro/neuroconv/issues/new>`_ describing what the camera did and
what the recording system captured. That is the information this page is built from.
