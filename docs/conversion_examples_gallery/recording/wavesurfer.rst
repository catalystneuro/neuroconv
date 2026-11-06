WaveSurfer data conversion
--------------------------

Convert intracellular electrophysiology recorded with `WaveSurfer <https://wavesurfer.janelia.org>`_ to NWB using
:py:class:`~neuroconv.datainterfaces.icephys.wavesurfer.wavesurferintracellularinterface.WaveSurferIntracellularInterface`.
WaveSurfer writes one ``.h5`` file per run of a protocol, holding one or more sweeps. One interface instance
corresponds to one electrode in one file. Only files written by WaveSurfer 0.945 are supported; other versions raise
an error.

.. code-block:: python

    >>> from neuroconv.datainterfaces import WaveSurferIntracellularInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/wavesurfer/version_0_945/current_clamp/square_pulse_steps/m114_0279-0281.h5"
    >>> interface = WaveSurferIntracellularInterface(file_path=file_path, reconstruct_stimulus=True)
    >>>
    >>> # Extract what metadata we can from the source files (session_start_time is the run's start, in local time)
    >>> metadata = interface.get_metadata()
    >>> # Add the timezone and subject information (required for DANDI upload)
    >>> from zoneinfo import ZoneInfo
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time.replace(tzinfo=ZoneInfo("US/Central"))
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

What the interface reads from the file header:

- The **clamp mode** and the **response channel** come from the electrode's settings in WaveSurfer: its mode
  (voltage clamp, current clamp or I=0) and its monitor channel. For an electrode of type ``Axon Multiclamp`` or
  ``Heka EPC``, WaveSurfer reads the mode from the amplifier before each run. For a ``Manual`` electrode it records
  the mode the user set. If a file has more than one electrode, name the one to convert with ``electrode_name``.
- The **scaling** comes from the acquisition card's calibration and the channel's scale. The samples are stored as
  the raw int16 counts WaveSurfer wrote, with the conversion in the series' ``conversion`` and ``offset``. The
  calibration is a cubic polynomial, and NWB stores a linear conversion, so a file whose quadratic and cubic terms
  change values by more than one count raises.
- The **stimulus type** of the run is the name of the protocol file WaveSurfer had loaded.

Two stimulus series can be written, and either or both can be requested:

- ``reconstruct_stimulus=True`` rebuilds the command the stimulus library specified for the electrode's command
  channel, sweep by sweep, and writes it as the **stimulus template**. Square pulses, square pulse trains, two square
  pulses, ramps, sines and chirps are supported, in maps or sequences; ``Expression`` and ``File`` stimuli raise.
- ``stimulus_channel_name`` names an analog input that recorded the delivered command, and writes it as the
  **stimulus**. It must be in a unit of the commanded quantity (a current in current clamp, a voltage in voltage
  clamp).

The interface writes one continuous ``PatchClampSeries`` per electrode, with each sweep at its own start time so
the dead time between sweeps survives as a gap, and records each sweep through the NWB ``IntracellularRecordings``
table. A sweep's samples can be read back through its row:

.. code-block:: python

    >>> nwbfile = interface.create_nwbfile(metadata=metadata)
    >>> response = nwbfile.intracellular_recordings["responses"]["response"][1]
    >>> second_sweep_data, second_sweep_times = response.data, response.timestamps

The upper icephys hierarchy tables and the per-sweep time intervals are written only once the full set of runs is
known. If this interface is your whole conversion, wrap it in the converter below with that one interface.

Combining runs with the converter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~neuroconv.datainterfaces.icephys.wavesurfer.wavesurferintracellularconverter.WaveSurferIntracellularConverter`
combines the runs of a session, placing them on one timeline by their recorded start times, the earliest run being
the session start. It builds the ``SimultaneousRecordings`` and ``SequentialRecordings`` (one per run) tables, and
the ``Repetitions`` and ``ExperimentalConditions`` tables from the ``repetition`` and ``condition`` labels of the
interfaces, when they are given. It also writes a ``sweeps`` table of NWB ``TimeIntervals`` with each sweep's start
and stop time.

WaveSurfer has no notion of a cell: every run of a day uses the same electrode settings. By default each run gets its
own ``IntracellularElectrode``. To record that several runs were made on one cell, point their series at one
electrode entry in the metadata:

.. code-block:: python

    >>> from neuroconv.datainterfaces import WaveSurferIntracellularInterface
    >>> from neuroconv.converters import WaveSurferIntracellularConverter
    >>>
    >>> data_path = f"{ECEPHY_DATA_PATH}/wavesurfer/version_0_945"
    >>> test_pulse = WaveSurferIntracellularInterface(
    ...     file_path=f"{data_path}/voltage_clamp/stimulation_rate_above_acquisition_rate/m114_0275-0277.h5",
    ...     reconstruct_stimulus=True,
    ... )
    >>> steps = WaveSurferIntracellularInterface(
    ...     file_path=f"{data_path}/current_clamp/square_pulse_steps/m114_0279-0281.h5",
    ...     stimulus_channel_name="Current Injection",
    ...     reconstruct_stimulus=True,
    ... )
    >>> converter = WaveSurferIntracellularConverter(data_interfaces=dict(TestPulse=test_pulse, Steps=steps))
    >>>
    >>> metadata = converter.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"] = metadata["NWBFile"]["session_start_time"].replace(
    ...     tzinfo=ZoneInfo("US/Central")
    ... )
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # One electrode for the cell, shared by both runs
    >>> metadata["Icephys"]["IntracellularElectrodes"] = {
    ...     "cell1": dict(name="Cell1", description="Whole-cell patch electrode.", device_metadata_key="axon_multiclamp")
    ... }
    >>> for series_metadata in metadata["Icephys"]["PatchClampSeries"].values():
    ...     series_metadata["electrode_metadata_key"] = "cell1"
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
