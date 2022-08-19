ABF data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert ABF intracellular electrophysiology data to NWB using :py:class:`~neuroconv.datainterfaces.icephys.abf.abfdatainterface.AbfInterface`.

.. code-block:: python

    >>> from neuroconv import AbfInterface
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
    >>> interface.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata)



If you have multiple ABF files for the same experiment, one file per recording stimulus type, you can organize a multi-file conversion as such:


.. code-block:: python

    >>> from neuroconv import AbfInterface
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
    >>> interface.run_conversion(nwbfile_path=f"{path_to_save_nwbfile}", metadata=metadata)
