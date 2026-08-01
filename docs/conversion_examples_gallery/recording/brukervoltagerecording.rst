Bruker VoltageRecording data conversion
--------------------------------------

Convert intracellular electrophysiology recorded by Bruker PrairieView to NWB using
:py:class:`~neuroconv.datainterfaces.icephys.brukervoltagerecording.brukervoltagerecordinginterface.BrukerVoltageRecordingInterface`.
PrairieView writes one CSV/XML pair per *cycle*, a cycle being one trigger of the acquisition and so one
sweep. One interface instance corresponds to one electrode, and you give it that electrode's cycles as a list.

.. code-block:: python

    >>> from neuroconv.datainterfaces import BrukerVoltageRecordingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/bruker/voltage_recording/cc_01_cell1-001"
    >>> interface = BrukerVoltageRecordingInterface(
    ...     file_paths=[f"{folder_path}/cell1-001_Cycle00001_VoltageRecording_001.csv"],
    ... )
    >>>
    >>> # Extract what metadata we can from the source files (session_start_time is read from the XML)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

The list of cycles is explicit because nothing in the format says which cycles belong to which cell. The
folder layout usually does, but that is the experimenter's own naming rather than something the files state,
so gathering the cycles of one cell is left to your conversion script:

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import BrukerVoltageRecordingInterface
    >>>
    >>> folder_path = Path(f"{ECEPHY_DATA_PATH}/bruker/voltage_recording/cc_01_cell1-001")
    >>> cycles = sorted(folder_path.glob("*_VoltageRecording_*.csv"))
    >>> interface = BrukerVoltageRecordingInterface(file_paths=cycles)

Everything else is read from the XML that sits beside each CSV:

- The **clamp mode** comes from the unit of the amplifier's ``Primary`` output: ``mV`` means the recording is
  a voltage, so current clamp, and ``pA`` means it is a current, so voltage clamp. Pass ``mode`` only to record
  an ``izero`` run, which reads exactly like ordinary current clamp in the file, or when the response is a
  signal other than ``Primary``, whose unit does not identify the mode.
- The **scaling** comes from ``Multiplier`` and ``Divisor``. The samples are stored exactly as the CSV holds
  them and the whole chain lives in the series' ``conversion``, so what you read back is what PrairieView wrote.
- The **amplifier** comes from ``PatchclampDevice``, and the **session start time** from the cycle's
  ``DateTime``, which carries the rig's UTC offset so no timezone has to be supplied.

If a cycle recorded more than one signal, name the one that is this electrode's response with
``response_signal_name``. To see what a cycle recorded:

.. code-block:: python

    >>> from neuroconv.datainterfaces import BrukerVoltageRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/bruker/voltage_recording/cc_01_cell1-001/cell1-001_Cycle00001_VoltageRecording_001.csv"
    >>> BrukerVoltageRecordingInterface.get_signal_names(file_path=file_path)
    ['Primary']

Only signals routed through the amplifier can be written here. PrairieView's other inputs (the ``WF`` sync
trace, the photodiode channels, the wavelength channels such as ``720nm``) carry no ``PatchclampDevice`` and
are recorded in volts; they are analog monitors rather than intracellular data, and the interface refuses them.

The interface writes one continuous ``PatchClampSeries`` per electrode, with each cycle placed at its own
``DateTime`` so the dead time between cycles survives as a gap, and records each cycle through the NWB
``IntracellularRecordings`` table. It stops there: the upper icephys hierarchy tables and the per-sweep time
intervals are written only once the full set of electrodes is known. If this interface is your whole
conversion, wrap it in the converter below with that one interface, which finalizes those tables for you.

Combining electrodes with the converter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~neuroconv.datainterfaces.icephys.brukervoltagerecording.brukervoltagerecordingconverter.BrukerVoltageRecordingConverter`
combines several interfaces and builds the hierarchy over them: the ``SimultaneousRecordings`` (electrodes
recorded together) and ``SequentialRecordings`` (one per run) tables, and the two optional grouping levels
above them. It also places the electrodes on one timeline, the earliest cycle of the whole set being the
session origin, and writes a ``sweeps`` table of NWB ``TimeIntervals`` holding each cycle's start and stop
time, which any tool that knows NWB intervals and nothing about icephys can read.

You build the two upper grouping levels by labeling each interface through its ``repetition`` and ``condition``
arguments. Runs sharing a ``repetition`` label are grouped into one ``Repetitions`` entry (repeated trials of
the same protocol), and repetitions sharing a ``condition`` label are grouped into one
``ExperimentalConditions`` entry (a drug wash-in versus control, say).

PrairieView records no protocol section, so there is nothing to derive a stimulus from and no stimulus series
is written. Pass ``stimulus_type`` if you want the run described (``"somatic excitability"``, for instance);
left out, the column is omitted rather than filled with a placeholder.

.. code-block:: python

    >>> from neuroconv.datainterfaces import BrukerVoltageRecordingInterface
    >>> from neuroconv.converters import BrukerVoltageRecordingConverter
    >>>
    >>> data_path = f"{ECEPHY_DATA_PATH}/bruker/voltage_recording"
    >>>
    >>> # One interface per electrode; here two cells, each with its own cycles.
    >>> first_cell = BrukerVoltageRecordingInterface(
    ...     file_paths=[f"{data_path}/cc_03_cell2-020/cell2-020_Cycle00001_VoltageRecording_001.csv"],
    ...     stimulus_type="somatic excitability",
    ... )
    >>> second_cell = BrukerVoltageRecordingInterface(
    ...     file_paths=[f"{data_path}/cc_05_cell1-001_2016/cell1-001_Cycle00001_VoltageRecording_001.csv"],
    ...     stimulus_type="somatic excitability",
    ... )
    >>> converter = BrukerVoltageRecordingConverter(
    ...     data_interfaces=dict(FirstCell=first_cell, SecondCell=second_cell)
    ... )
    >>>
    >>> # The converter places the electrodes on one timeline and builds the icephys tables over them.
    >>> metadata = converter.get_metadata()
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
