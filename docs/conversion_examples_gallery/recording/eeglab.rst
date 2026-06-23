EEGLAB data conversion
----------------------

Install NeuroConv with the additional dependencies necessary for reading EEGLAB data.

.. code-block:: bash

    pip install "neuroconv[eeglab]"

Convert EEGLAB EEG data (``.set`` / ``.fdt``) to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.eeglab.eeglabdatainterface.EEGLABRecordingInterface`.

EEGLAB datasets come in two layouts, both handled transparently by pointing at the ``.set`` file:

* a self-contained ``.set`` file that stores the data inline, or
* a ``.set`` file paired with an external ``.fdt`` binary (the ``.fdt`` must be kept next to the ``.set``).

The signal is written as an ``ElectricalSeries`` with channel names and locations in the electrodes
table, and the ``EEG.event`` markers are written to a ``TimeIntervals`` table named ``"events"``.

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from neuroconv.datainterfaces import EEGLABRecordingInterface

    file_path = f"{ECEPHY_DATA_PATH}/eeglab/eeglab_data.set"

    # Point at the .set file; an external .fdt next to it (if present) is read automatically
    interface = EEGLABRecordingInterface(file_path=file_path)

    # Extract what metadata we can from the source files
    metadata = interface.get_metadata()
    # EEGLAB files often do not store a recording date, so set the session start time explicitly
    session_start_time = datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("US/Pacific"))
    metadata["NWBFile"].update(session_start_time=session_start_time)
    # Add subject information (required for DANDI upload)
    metadata["Subject"] = dict(subject_id="subject1", species="Homo sapiens", sex="M", age="P30Y")

    # Choose a path for saving the nwb file and run the conversion
    nwbfile_path = f"{path_to_save_nwbfile}"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

To skip writing the event markers, pass ``write_events=False`` as a conversion option:

.. code-block:: python

    interface.run_conversion(
        nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, write_events=False
    )

Epoched datasets
^^^^^^^^^^^^^^^^

A single NWB ``ElectricalSeries`` is continuous, so epoched EEGLAB datasets (``EEG.trials > 1``) cannot
be stored in one file. Instead, write one NWB file per epoch with ``run_conversion_split_by_epoch``.
Each file holds a single epoch with an epoch-relative time axis (the time-locking event at ``t = 0``,
i.e. the series starts at ``EEG.xmin``) and only the events belonging to that epoch. The output paths
are derived from ``nwbfile_path`` by inserting an ``_epoch{index}`` suffix
(e.g. ``recording.nwb`` -> ``recording_epoch0.nwb``, ``recording_epoch1.nwb``, ...).

.. code-block:: python

    interface = EEGLABRecordingInterface(file_path=f"{ECEPHY_DATA_PATH}/eeglab/eeglab_data_epochs.set")

    metadata = interface.get_metadata()
    metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("US/Pacific")))
    metadata["Subject"] = dict(subject_id="subject1", species="Homo sapiens", sex="M", age="P30Y")

    # Writes one NWB file per epoch and returns the written paths
    written_paths = interface.run_conversion_split_by_epoch(
        nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata, overwrite=True
    )

For finer control you can call ``interface.split_by_epoch()`` to obtain one interface per epoch and run
the conversion on each yourself. A continuous dataset converts normally with ``run_conversion``; calling
``run_conversion`` directly on an epoched dataset raises an informative error directing you here.
