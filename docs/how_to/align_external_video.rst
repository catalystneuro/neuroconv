.. _align_external_video:

Aligning Multiple External Video Files
=======================================


When a single camera produces multiple video files (for example, one file per trial), you need to
tell NeuroConv how the segments are aligned in time. All segments from the same camera are written
into a single ``ImageSeries`` with multiple entries in ``external_file``, and the timestamps describe
the full concatenated timeline.

Trialized recordings with gaps
------------------------------

Each file corresponds to a trial or acquisition segment that started at a known time relative to the
session start. Use ``set_segment_starting_times`` to provide the per-segment starting times. The
interface reads the frame count and rate from the video metadata and constructs the concatenated
timestamps array automatically.

.. code-block:: python

    from neuroconv.datainterfaces import ExternalVideoInterface

    interface = ExternalVideoInterface(
        file_paths=["trial_1.avi", "trial_2.avi", "trial_3.avi"],
        video_name="BehaviorCamera",
        verbose=False,
    )

    # Each trial started at a known time (seconds relative to session start)
    interface.set_segment_starting_times(
        starting_times=[0.0, 65.0, 130.0],
    )

The frame rate is read from the video metadata. If you need to override it (for example, when the
video metadata is inaccurate), pass the ``rate`` parameter explicitly:

.. code-block:: python

    interface.set_segment_starting_times(
        starting_times=[0.0, 65.0, 130.0],
        rate=30.0,  # Hz, overrides video metadata
    )

For trial 1 (100 frames at 30 fps), the timestamps would be ``[0.0, 0.033, 0.067, ...]``.
For trial 2, they would be ``[65.0, 65.033, 65.067, ...]``, and so on.

``starting_frame`` is computed automatically from the video frame counts. You do not need to
provide it manually.
