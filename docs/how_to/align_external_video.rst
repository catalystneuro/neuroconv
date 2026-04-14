.. _align_external_video:

Aligning Multiple External Video Files
=======================================

When a single camera produces multiple video files (for example, one file per trial, or files split by
acquisition software), you need to tell NeuroConv how these segments are aligned in time. All segments
from the same camera are written into a single ``ImageSeries`` with multiple entries in ``external_file``,
and the timestamps describe the full concatenated timeline.

The :py:class:`~neuroconv.datainterfaces.behavior.video.externalvideodatainterface.ExternalVideoInterface`
provides three alignment methods for different scenarios.

Trialized recordings with gaps
------------------------------

This is the most common multi-file scenario: each file corresponds to a trial or acquisition segment that
started at a known time relative to the session start. All segments share the same constant frame rate.

Use ``set_aligned_segment_starting_times_and_rate`` to provide the per-segment starting times and the rate.
The interface reads the frame count from each file's metadata and constructs the concatenated timestamps
array automatically.

.. code-block:: python

    from neuroconv.datainterfaces import ExternalVideoInterface

    interface = ExternalVideoInterface(M
        file_paths=["trial_1.avi", "trial_2.avi", "trial_3.avi"],
        video_name="BehaviorCamera",
        verbose=False,
    )

    # Each trial started at a known time (seconds relative to session start)
    interface.set_aligned_segment_starting_times_and_rate(
        aligned_segment_starting_times=[0.0, 65.0, 130.0],
        rate=30.0,  # Hz
    )

For trial 1 (100 frames at 30 fps), the timestamps would be ``[0.0, 0.033, 0.067, ...]``.
For trial 2, they would be ``[65.0, 65.033, 65.067, ...]``, and so on.

You can combine this with ``set_aligned_starting_time`` to shift all segments by a global offset
(for example, to align with other data streams):

.. code-block:: python

    interface.set_aligned_segment_starting_times_and_rate(
        aligned_segment_starting_times=[0.0, 65.0, 130.0],
        rate=30.0,
    )
    # Shift everything by 5 seconds to align with electrophysiology
    interface.set_aligned_starting_time(aligned_starting_time=5.0)
    # Resulting starting times: [5.0, 70.0, 135.0]


Hardware-synchronized timestamps
--------------------------------

When you have precise per-frame timestamps from a hardware synchronization system (for example, TTL
pulses logged by an acquisition system), provide them directly as a list of arrays, one per segment.

.. code-block:: python

    import numpy as np
    from neuroconv.datainterfaces import ExternalVideoInterface

    interface = ExternalVideoInterface(
        file_paths=["segment_1.avi", "segment_2.avi"],
        video_name="BehaviorCamera",
        verbose=False,
    )

    # Timestamps from your synchronization system (seconds relative to session start)
    timestamps_segment_1 = np.array([0.000, 0.033, 0.067, 0.100])
    timestamps_segment_2 = np.array([50.000, 50.034, 50.067, 50.101])

    interface.set_aligned_timestamps(
        aligned_timestamps=[timestamps_segment_1, timestamps_segment_2],
    )

This writes the concatenated timestamps directly. If the timestamps happen to be perfectly regular,
the interface detects this and stores ``starting_time`` + ``rate`` instead of the full array.


Gapless file splits
-------------------

Some acquisition software splits a continuous recording into multiple files when a size limit is reached.
In this case there are no gaps between segments. Provide a single starting time and the frame rate is
read from the video metadata.

.. code-block:: python

    from neuroconv.datainterfaces import ExternalVideoInterface

    interface = ExternalVideoInterface(
        file_paths=["recording_part1.avi", "recording_part2.avi"],
        video_name="BehaviorCamera",
        verbose=False,
    )

    interface.set_aligned_starting_time(aligned_starting_time=0.0)


Automatic ``starting_frame`` computation
-----------------------------------------

NWB's ``ImageSeries`` uses a ``starting_frame`` array to indicate where each file's frames begin
in the concatenated timeline. For all multi-file scenarios, the interface computes this automatically
from the video frame counts. You do not need to provide ``starting_frames`` manually.

If you do provide explicit ``starting_frames`` in the conversion options, they will be used instead
of the auto-computed values.
