Axon Binary Format (ABF) data conversion
----------------------------------------

Convert intracellular electrophysiology recorded in Axon Binary Format (ABF) to NWB using
:py:class:`~neuroconv.datainterfaces.icephys.axon.axonintracellularinterface.AxonIntracellularInterface`.
One interface instance corresponds to one channel: one electrode's recording in one ABF file. You tell it
which recorded channel is the response and how it was clamped (the arguments are explained below).

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

The interface writes one continuous ``PatchClampSeries`` per electrode and records each sweep through the NWB
``IntracellularRecordings`` table. The upper icephys hierarchy tables (``SimultaneousRecordings`` and above)
are not built by a single interface; they are assembled once the full set of channels and files is known.

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
