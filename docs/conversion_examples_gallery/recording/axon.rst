Axon data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading Axon Binary Format (ABF) data.

.. code-block:: bash

    pip install "neuroconv[axon]"

Convert Axon ABF data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.axon.axondatainterface.AxonRecordingInterface`.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import AxonRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/axon/extracellular_data/four_electrodes/24606005_SampleData.abf"
    >>> interface = AxonRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is automatically extracted from ABF file metadata
    >>> # but can be overridden if needed
    >>>
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
