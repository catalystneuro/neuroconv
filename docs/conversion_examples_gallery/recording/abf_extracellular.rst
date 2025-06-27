ABF extracellular data conversion
----------------------------------

Install NeuroConv with the additional dependencies necessary for reading Axon Binary File (ABF) data.

.. code-block:: bash

    pip install "neuroconv[abf]"

Convert ABF extracellular electrophysiology data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.abf.abfrecordinginterface.AbfRecordingInterface`.

.. code-block:: python

    >>> from neuroconv.datainterfaces import AbfRecordingInterface
    >>>
    >>> # For extracellular multi-electrode data
    >>> interface = AbfRecordingInterface(file_path="path/to/extracellular_data.abf")
    >>>
    >>> # Get metadata from source data
    >>> metadata = interface.get_metadata()
    >>> metadata['NWBFile'].update(
    ...     identifier="ID1234",
    ...     session_description="Extracellular electrophysiology experiment.",
    ...     lab="my lab name",                       # <- optional
    ...     institution="My University",             # <- optional
    ...     experimenter=["John Doe", "Jane Doe"],   # <- optional
    ... )
    >>> metadata["Subject"] = dict(
    ...     subject_id="subject_ID123",
    ...     species="Mus musculus",
    ...     sex="M",
    ...     date_of_birth="2022-03-15T00:00:00"
    ... )
    >>>
    >>> # Run conversion
    >>> interface.run_conversion(nwbfile_path="extracellular_abf_conversion.nwb", metadata=metadata)


For intracellular data, use the :py:class:`~neuroconv.datainterfaces.icephys.abf.abfdatainterface.AbfInterface` instead.

The AbfRecordingInterface treats ABF files as extracellular recording data suitable for multi-electrode arrays,
while AbfInterface is designed for intracellular electrophysiology experiments.