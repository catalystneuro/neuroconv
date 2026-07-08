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

Epoched EEGLAB datasets (``EEG.trials > 1``) are handled automatically by ``run_conversion``: each epoch
is written as its own ``ElectricalSeries`` (named ``ElectricalSeriesEpoch{index}``) into the **same** NWB
file, all sharing a single electrodes table. Each series is placed at the epoch's real time in the source
recording — recovered from ``EEG.urevent`` — so the epochs live on one shared session timeline rather
than a synthetic one. The per-epoch boundaries and time-locking event types are written to the NWB
``epochs`` table, and the unique ``EEG.event`` markers are written to the ``"events"`` table at their
real times. (If the real timing cannot be recovered, epochs fall back to the epoch-relative start
``EEG.xmin``.)

.. code-block:: python

    interface = EEGLABRecordingInterface(file_path=f"{ECEPHY_DATA_PATH}/eeglab/eeglab_data_epochs.set")

    metadata = interface.get_metadata()
    metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1, 0, 0, tzinfo=ZoneInfo("US/Pacific")))
    metadata["Subject"] = dict(subject_id="subject1", species="Homo sapiens", sex="M", age="P30Y")

    # Writes one NWB file with one ElectricalSeries per epoch plus an epochs table
    interface.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata, overwrite=True)

Pass ``write_epochs=False`` to skip the epochs table.
