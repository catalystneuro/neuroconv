ABF data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert ABF intracellular electrophysiology data to NWB using :py:class:`~neuroconv.datainterfaces.icephys.abf.abfdatainterface.AbfInterface`.

.. code-block:: python

    >>> from neuroconv import AbfInterface
    >>>
    >>> # Metadata info
    >>> icephys_metadata = {
    >>>     "cell_id": "20220512001",
    >>>     "slice_id": "20220512001",
    >>>     "targeted_layer": "L2-3(medial)",
    >>>     "inferred_layer": "",
    >>>     "recording_sessions": [
    >>>         {
    >>>             "abf_file_name": "my_file.abf",
    >>>             "stimulus_type": "Long_Square_currentClamp_-50 to100_step10pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         }
    >>>     ]
    >>> }
    >>>
    >>> # Instantiate data interface
    >>> interface = AbfInterface(
    >>>     file_paths=["path_to/my_file.abf"],
    >>>     icephys_metadata=icephys_metadata
    >>> )
    >>>
    >>> # Get metadata from source data and modify any values you want
    >>> metadata = interface.get_metadata()
    >>> metadata['NWBFile'].update(
    >>>     identifier="ID1234",
    >>>     session_description="Intracellular electrophysiology experiment.",
    >>>     lab="my lab name",                       # <-- optional
    >>>     institution="My University",             # <-- optional
    >>>     experimenter=["John Doe", "Jane Doe"],   # <-- optional
    >>> )
    >>> metadata["Subject"] = dict(
    >>>     subject_id="subject_ID123",
    >>>     species="Mus musculus",
    >>>     sex="M",
    >>>     date_of_birth="2022-03-15T00:00:00"
    >>> )
    >>>
    >>> # Run conversion
    >>> interface.run_conversion(metadata=metadata, save_path='converted_icephys.nwb')



If you have multiple ABF files for the same experimental session, one file per stimulus type, you can organize a multi-file conversion as such:


.. code-block:: python

    >>> from neuroconv import AbfInterface
    >>>
    >>> # Metadata info
    >>> icephys_metadata = {
    >>>     "cell_id": "20220512001",
    >>>     "slice_id": "20220512001",
    >>>     "targeted_layer": "L2-3(medial)",
    >>>     "inferred_layer": "",
    >>>     "recording_sessions": [
    >>>         {
    >>>             "abf_file_name": "my_file_1.abf",
    >>>             "stimulus_type": "Long_Square_currentClamp_-50 to100_step10pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         },
    >>>         {
    >>>             "abf_file_name": "my_file_2.abf",
    >>>             "stimulus_type": "short_Square_100pAstepMa1500pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         },
    >>>         {
    >>>             "abf_file_name": "my_file_3.abf",
    >>>             "stimulus_type": "Ramp_250pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         },
    >>>         {
    >>>             "abf_file_name": "my_file_4.abf",
    >>>             "stimulus_type": "Long_Square_currentClamp_-50 to100_step10pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         },
    >>>         {
    >>>             "abf_file_name": "my_file_5.abf",
    >>>             "stimulus_type": "short_Square_100pAstepMa1500pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         },
    >>>         {
    >>>             "abf_file_name": "my_file_6.abf",
    >>>             "stimulus_type": "Ramp_250pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         }
    >>>     ]
    >>> }
    >>>
    >>> # Instantiate data interface
    >>> interface = AbfInterface(
    >>>     file_paths=[
    >>>         "path_to/my_file_1.abf",
    >>>         "path_to/my_file_2.abf",
    >>>         "path_to/my_file_3.abf",
    >>>         "path_to/my_file_4.abf",
    >>>         "path_to/my_file_5.abf",
    >>>         "path_to/my_file_6.abf",
    >>>     ],
    >>>     icephys_metadata=icephys_metadata
    >>> )
    >>>
    >>> # Get metadata from source data and modify any values you want
    >>> metadata = interface.get_metadata()
    >>> metadata['NWBFile'].update(
    >>>     identifier="ID1234",
    >>>     session_description="Intracellular electrophysiology experiment.",
    >>>     lab="my lab name",                       # <-- optional
    >>>     institution="My University",             # <-- optional
    >>>     experimenter=["John Doe", "Jane Doe"],   # <-- optional
    >>> )
    >>> metadata["Subject"] = dict(
    >>>     subject_id="subject_ID123",
    >>>     species="Mus musculus",
    >>>     sex="M",
    >>>     date_of_birth="2022-03-15T00:00:00"
    >>> )
    >>>
    >>> # Run conversion
    >>> interface.run_conversion(metadata=metadata, save_path='converted_icephys.nwb')
