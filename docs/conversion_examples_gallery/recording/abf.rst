Axon Binary Format (ABF) data conversion
----------------------------------------

Convert intracellular electrophysiology recorded in Axon Binary Format (ABF) to NWB using
:py:class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularinterface.AxonIntracellularInterface`.
One interface instance corresponds to one channel: one electrode's recording in one ABF file. You tell it
which recorded channel is the response and how it was clamped (the arguments are explained below). Combine
several channels in a converter for a dual-patch or multi-file recording (see below).

Install NeuroConv with the additional dependencies necessary for reading Axon Binary Format (ABF) data.

.. code-block:: bash

    pip install "neuroconv[abf]"

.. code-block:: python

    >>> from neuroconv.datainterfaces import AxonIntracellularInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/axon/File_axon_5.abf"
    >>> interface = AxonIntracellularInterface(
    ...     file_path=file_path,
    ...     response_channel_name="_Ipatch",   # the recorded channel
    ...     mode="current_clamp",         # voltage_clamp | current_clamp | izero
    ...     stimulus_command="Cmd 0",     # optional: reconstruct the stimulus from this command channel
    ... )
    >>>
    >>> # Extract what metadata we can from the source files (session_start_time is read from the ABF file)
    >>> metadata = interface.get_metadata()
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

The interface does not guess which recorded channel is the cell and which is an auxiliary monitor, so the
recording is described explicitly through the constructor arguments:

- ``response_channel_name`` (required): the recorded analog-to-digital converter channel for the electrode's
  response, given as the channel name (for example ``"_Ipatch"`` or ``"IN0"``) or its integer index.
- ``mode`` (required): the clamp mode, one of ``"voltage_clamp"``, ``"current_clamp"`` or ``"izero"``.
  This selects the NWB series type (``VoltageClampSeries``, ``CurrentClampSeries`` or ``IZeroClampSeries``).
- The stimulus (optional) comes from one of two mutually-exclusive sources: ``stimulus_command``, a
  digital-to-analog converter command channel (for example ``"Cmd 0"``) whose waveform is reconstructed from
  the protocol (ABF version 2 only); or ``stimulus_channel_name``, a recorded monitor channel holding the actual
  delivered signal (works for ABF v1 and v2). ``izero`` takes no stimulus.

To find out the names of the channels and commands, neuroconv provides two utility methods:

.. code-block:: python

    >>> from neuroconv.datainterfaces import AxonIntracellularInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/axon/File_axon_5.abf"
    >>>
    >>> # The recorded channels: the options for `response_channel_name` and `stimulus_channel_name`.
    >>> channel_names = AxonIntracellularInterface.get_channel_names(file_path=file_path)
    >>>
    >>> # The command channels: the options for `stimulus_command` (an empty list for ABF v1, which has no protocol).
    >>> command_names = AxonIntracellularInterface.get_command_names(file_path=file_path)

What these names are and where they come from:

- The **channel names** are the recorded analog-to-digital (ADC) channels, the signals the amplifier digitized
  (the cell's response and any monitor outputs). neuroconv reads them from the ABF header, exactly as the
  acquisition software (Clampex) stored them; these are the values you give to ``response_channel_name`` (and to
  ``stimulus_channel_name`` if you are using one of the recorded channels as a monitor).
- The **command names** are the digital-to-analog (DAC) command channels from the protocol, the waveforms the
  amplifier was told to deliver. neuroconv reads them from the protocol's DAC table, so they exist only in ABF
  version 2 files (version 1 has no protocol section, hence the empty list); these are the values you give to
  ``stimulus_command``.

A channel or command whose stored name is blank falls back to ``ch{index}`` / ``cmd{index}``, so every one is
always addressable by a non-empty name.

The interface writes one continuous ``PatchClampSeries`` per electrode and records each sweep through the NWB
``IntracellularRecordings`` table.

Combining channels and files with the converter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A single ``AxonIntracellularInterface`` writes one channel's per-sweep recordings rows but not the upper icephys
hierarchy tables, because those can only be built once the full set of channels and files is known.
:py:class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularconverter.AxonIntracellularConverter`
combines several interfaces and builds that hierarchy over them: the ``SimultaneousRecordings`` (channels
recorded together) and ``SequentialRecordings`` (one per run, carrying the stimulus type) tables, and the
``Repetitions`` / ``ExperimentalConditions`` levels when you label the runs. You give it one interface per
channel: a single cell is the one-interface case; pass one per electrode for a **dual-patch** recording (the
channels of each sweep grouped into one simultaneous recording), or one per file for a **multi-file** experiment
(each run becomes its own sequential recording, the runs placed on a single timeline from each file's header
start time, which requires ABF version 2). The example below combines two channels recorded in one file.

.. code-block:: python

    >>> from neuroconv.datainterfaces import AxonIntracellularInterface
    >>> from neuroconv.converters import AxonIntracellularConverter
    >>>
    >>> # One interface per channel; here two electrodes recorded in the same file.
    >>> current_clamp = AxonIntracellularInterface(
    ...     file_path=f"{ECEPHY_DATA_PATH}/axon/File_axon_6.abf",
    ...     response_channel_name="_Ipatch",
    ...     mode="current_clamp",
    ... )
    >>> voltage_clamp = AxonIntracellularInterface(
    ...     file_path=f"{ECEPHY_DATA_PATH}/axon/File_axon_6.abf",
    ...     response_channel_name="IN1",
    ...     mode="voltage_clamp",
    ... )
    >>> converter = AxonIntracellularConverter(data_interfaces=[current_clamp, voltage_clamp])
    >>>
    >>> # The converter groups the two channels of each sweep into the icephys tables.
    >>> metadata = converter.get_metadata()
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Legacy AbfInterface
~~~~~~~~~~~~~~~~~~~~

.. note::

    ``AbfInterface`` is legacy and will be deprecated. Prefer ``AxonIntracellularInterface`` above for new
    conversions; it writes one continuous series per electrode and records each sweep through the NWB
    intracellular recordings table.

Convert ABF intracellular electrophysiology data to NWB using :py:class:`~neuroconv.datainterfaces.icephys.abf.abfdatainterface.AbfInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import AbfInterface
    >>>
    >>> # Metadata info
    >>> icephys_metadata = {
    ...     "cell_id": "20220818001",
    ...     "slice_id": "20220818001",
    ...     "targeted_layer": "L2-3(medial)",
    ...     "inferred_layer": "",
    ...     "recording_sessions": [
    ...         {
    ...             "abf_file_name": "File_axon_5.abf",
    ...             "stimulus_type": "long_square",
    ...             "icephys_experiment_type": "voltage_clamp"
    ...         }
    ...     ]
    ... }
    >>>
    >>> # Instantiate data interface
    >>> interface = AbfInterface(
    ...     file_paths=[f"{ECEPHY_DATA_PATH}/axon/File_axon_5.abf"],
    ...     icephys_metadata=icephys_metadata
    ... )
    >>>
    >>> # Get metadata from source data and modify any values you want
    >>> metadata = interface.get_metadata()
    >>> metadata['NWBFile'].update(
    ...     identifier="ID1234",
    ...     session_description="Intracellular electrophysiology experiment.",
    ...     lab="my lab name",                       # <-- optional
    ...     institution="My University",             # <-- optional
    ...     experimenter=["John Doe", "Jane Doe"],   # <-- optional
    ... )
    >>> metadata["Subject"] = dict(
    ...     subject_id="subject_ID123",
    ...     species="Mus musculus",
    ...     sex="M",
    ...     date_of_birth="2022-03-15T00:00:00"
    ... )
    >>>
    >>> # Run conversion
    >>> interface.run_conversion(nwbfile_path=output_folder / "single_abf_conversion.nwb", metadata=metadata)



If you have multiple ABF files for the same experiment, one file per recording stimulus type, you can organize a multi-file conversion as such:


.. code-block:: python

    >>> from neuroconv.datainterfaces import AbfInterface
    >>>
    >>> # Metadata info
    >>> icephys_metadata = {
    ...     "cell_id": "20220818001",
    ...     "slice_id": "20220818001",
    ...     "targeted_layer": "L2-3(medial)",
    ...     "inferred_layer": "",
    ...     "recording_sessions": [
    ...         {
    ...             "abf_file_name": "File_axon_5.abf",
    ...             "stimulus_type": "long_square",
    ...             "icephys_experiment_type": "voltage_clamp"
    ...         },
    ...         {
    ...             "abf_file_name": "File_axon_6.abf",
    ...             "stimulus_type": "short_square",
    ...             "icephys_experiment_type": "voltage_clamp"
    ...         }
    ...     ]
    ... }
    >>>
    >>> # Instantiate data interface
    >>> interface = AbfInterface(
    ...     file_paths=[
    ...         f"{ECEPHY_DATA_PATH}/axon/File_axon_5.abf",
    ...         f"{ECEPHY_DATA_PATH}/axon/File_axon_6.abf",
    ...     ],
    ...     icephys_metadata=icephys_metadata
    ... )
    >>>
    >>> # Get metadata from source data and modify any values you want
    >>> metadata = interface.get_metadata()
    >>> metadata['NWBFile'].update(
    ...     identifier="ID1234",
    ...     session_description="Intracellular electrophysiology experiment.",
    ...     lab="my lab name",                       # <-- optional
    ...     institution="My University",             # <-- optional
    ...     experimenter=["John Doe", "Jane Doe"],   # <-- optional
    ... )
    >>> metadata["Subject"] = dict(
    ...     subject_id="subject_ID123",
    ...     species="Mus musculus",
    ...     sex="M",
    ...     date_of_birth="2022-03-15T00:00:00"
    ... )
    >>>
    >>> # Run conversion
    >>> interface.run_conversion(nwbfile_path=output_folder / "multiple_abf_conversion.nwb", metadata=metadata)
