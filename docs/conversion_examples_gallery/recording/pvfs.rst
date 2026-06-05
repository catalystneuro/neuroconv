Pinnacle PVFS conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading
Pinnacle PVFS (Virtual File System) recordings.

.. code-block:: bash

    pip install "neuroconv[pvfs]"

To also export embedded video tracks as ``ImageSeries`` (via PyAV), use the
``pvfs_video`` extra:

.. code-block:: bash

    pip install "neuroconv[pvfs_video]"

.. note::

    A publicly available sample ``.pvfs`` recording (mouse EEG/EMG, scored
    sleep) is hosted by Pinnacle Technology at
    https://www.pinnaclet.com/data_sets/sleep_data.zip.  Unzip it to obtain
    ``EEG_EMG_MOUSE_SCORED.pvfs`` and use that path in the examples below.
    The file is several hundred megabytes; a full conversion typically takes
    a few minutes.

    NeuroConv's ``test_on_data`` PVFS tests look for a sample file in this
    order: the ``PVFS_TEST_FILE`` environment variable, then
    ``<repo>/pvfs/example.pvfs`` (a local scratch copy, not committed), then
    ``ECEPHY_DATA_PATH/pvfs/``.  Tests are skipped when none of those paths
    exist.

Converting PVFS Recordings
^^^^^^^^^^^^^^^^^^^^^^^^^^

Use :py:class:`~neuroconv.datainterfaces.ecephys.pvfs.pvfsdatainterface.PvfsRecordingInterface`
to convert a single sampling-rate group of indexed channels (e.g. the EEG
channels at 400 Hz) from a Pinnacle ``.pvfs`` container.

A PVFS container can hold channels at several different sampling rates (for
example, EEG channels at 400 Hz alongside EMG channels at 2000 Hz).  An NWB
``ElectricalSeries`` requires a uniform sampling frequency, so a single
``PvfsRecordingInterface`` only writes one rate group:

* By default it picks the **most common** sampling rate in the file and
  ignores channels at any other rate.
* Pass ``sampling_rate_hz=<value>`` to choose a specific group.
* Pass ``channel_names=[...]`` to restrict to a known subset (all of which
  must share one rate).

If your ``.pvfs`` file contains more than one sampling-rate group and you
want all of them in the resulting NWB file, use
:py:class:`~neuroconv.datainterfaces.ecephys.pvfs.pvfsconverter.PvfsConverter`
(shown in the next section) instead -- it builds one
``PvfsRecordingInterface`` per rate group automatically, producing one
``ElectricalSeries`` per rate (e.g. ``ElectricalSeriesPVFS400Hz`` and
``ElectricalSeriesPVFS2000Hz``) inside a single ``.nwb`` output.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import PvfsRecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/pvfs/example.pvfs"

    interface = PvfsRecordingInterface(file_path=file_path, verbose=False)

    # Extract what metadata we can from experiment.db3
    metadata = interface.get_metadata()
    # For data provenance we add the time zone information to the conversion
    session_start_time = metadata["NWBFile"]["session_start_time"].astimezone(
        ZoneInfo("US/Pacific")
    )
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Converting All PVFS Streams (Recordings + Annotations + Sleep Scoring + Video)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PVFS files can hold multiple sampling-rate groups, per-channel annotations,
sleep-stage scoring (all stored in ``experiment.db3``) and embedded video
tracks.  Use the
:py:class:`~neuroconv.datainterfaces.ecephys.pvfs.pvfsconverter.PvfsConverter`
to wire every PVFS data type into a single NWB file in one call.

.. code-block:: python

    from pathlib import Path
    from zoneinfo import ZoneInfo
    from neuroconv.converters import PvfsConverter

    file_path = f"{ECEPHY_DATA_PATH}/pvfs/example.pvfs"

    converter = PvfsConverter(
        file_path=file_path,
        include_annotations=True,
        include_sleep_scoring=True,
        include_video=True,
        video_output_dir=None,  # defaults to the .nwb output directory
        embed_frames=False,     # if True, decode and inline video frames
    )

    metadata = converter.get_metadata()
    session_start_time = metadata["NWBFile"]["session_start_time"].astimezone(
        ZoneInfo("US/Pacific")
    )
    metadata["NWBFile"].update(session_start_time=session_start_time)
    metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    nwbfile_path = f"{path_to_save_nwbfile}"
    converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

``PvfsConverter`` introspects the PVFS file once and creates one
``PvfsRecordingInterface`` for **every** sampling-rate group of indexed
channels, so each rate becomes its own ``ElectricalSeries`` in the output
NWB (e.g. ``ElectricalSeriesPVFS400Hz``, ``ElectricalSeriesPVFS2000Hz``).
All channels share a single electrodes table grouped under one ``PVFSGroup``
electrode group.  Within a single rate group, channels are truncated to the
shortest length so they share a uniform frame axis; different rate groups
remain independent.

Annotations are written as rows in ``nwbfile.epochs`` with custom ``label``
and ``channel`` columns.  Embedded video tracks are exported as external
``.webm`` files next to the NWB file and referenced from an ``ImageSeries``;
pass ``embed_frames=True`` to inline the decoded frames instead.

Sleep-stage scoring (when present) is exported through
:py:class:`~neuroconv.datainterfaces.ecephys.pvfs.pvfssleepscoringinterface.PvfsSleepScoringInterface`.
For each populated scoring session in the PVFS file, one
:py:class:`~pynwb.epoch.TimeIntervals` table is attached at
``nwbfile.intervals["sleep_stages_session_<n>"]`` -- distinct from
``nwbfile.epochs``, which is reserved for the free-text PVFS annotations.
Each table carries the columns ``start_time``, ``stop_time``,
``stage_label`` (resolved name, e.g. ``"Wake"``, ``"Non REM"``, ``"REM"``,
``"Artifact"``), ``stage_value`` (the raw PVFS integer score), ``flags``
(``0`` for wake/artifact/unscored, ``1`` for sleep stages, ``2`` for the
``X`` variants), and ``epoch_uid`` (the per-epoch GUID preserved from PVFS
so external scoring tools can round-trip edits).  Pass
``include_sleep_scoring=False`` to skip this step.  When the PVFS file has
no scoring tables (or no populated scoring sessions) the converter silently
omits the interface, so it is safe to leave the flag on by default.

.. note::

    ``start_time`` is expressed relative to ``NWBFile.session_start_time``
    (which the converter aligns to the earliest recording sample).  Pinnacle
    scoring sometimes covers a brief setup window that precedes the indexed
    data, so the first few sleep-stage rows can have **negative**
    ``start_time`` values -- this is permitted by NWB and intentional, not a
    bug.  ``stop_time > start_time`` always holds and epoch durations stay
    consistent with the session's ``epoch_length`` (10 s in the public
    sample).
