ABF data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert ABF intracellular electrophysiology data to NWB using :py:class:`~neuroconv.datainterfaces.icephys.abf.abfdatainterface.AbfInterface`.

.. code-block:: python

    >>> from neuroconv import NWBConverter, AbfInterface

    >>> # Define the Data Interfaces for your converter
    >>> class MyIcephysConverter(NWBConverter):
    >>>     data_interface_classes = dict(AbfInterface=AbfInterface)
    >>> 
    >>> # Metadata info
    >>> icephys_metadata = {
    >>>     "cell_id": "20220512001",
    >>>     "slice_id": "20220512001",
    >>>     "targeted_layer": "L2-3(medial)",
    >>>     "inferred_layer": "",
    >>>     "recording_sessions": [
    >>>         {
    >>>             "abf_file_name": "2022_05_12_0000.abf",
    >>>             "stimulus_type": "Long_Square_currentClamp_-50 to100_step10pA",
    >>>             "icephys_experiment_type": "current_clamp"
    >>>         }
    >>>     ]
    >>> }
    >>> 
    >>> # Source data
    >>> source_data = dict(
    >>>     AbfInterface=dict(
    >>>         file_paths=["path_to/my_file.abf"],
    >>>         icephys_metadata=icephys_metadata
    >>>     )
    >>> )
    >>> 
    >>> # Initialize converter
    >>> converter = MyIcephysConverter(source_data=source_data)
    >>> 
    >>> # Get metadata from source data and modify any values you want
    >>> metadata = converter.get_metadata()
    >>> metadata['NWBFile']['identifier'] = "ID12345"
    >>> metadata['NWBFile']['session_description'] = "Intracellular electrophysiology experiment."
    >>> metadata['NWBFile']['lab'] = "My lab name"
    >>> metadata['NWBFile']['institution'] = "My University"
    >>> metadata['NWBFile']['experimenter'] = ["John Doe", "Jane Doe"]
    >>> metadata["Subject"] = dict(
    >>>     subject_id="subject_ID123",
    >>>     species="Mus musculus",
    >>>     sex="M",
    >>>     date_of_birth="2022-03-15T00:00:00"
    >>> )
    >>> 
    >>> # Run conversion
    >>> converter.run_conversion(metadata=metadata, nwbfile_path='converted_icephys.nwb')