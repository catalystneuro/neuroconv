Neuralynx NVT data conversion
-----------------------------

Neuralynx NVT files contain information about position tracking. This interface requires no additional dependencies,
so you can install NeuroConv using:

.. code-block:: bash

    pip install neuroconv

Convert Neuralynx NVT data to NWB using
:py:class:`~.neuroconv.datainterfaces.behavior.neuralynx.neuralynxnvtdatainterface.NeuralynxNvtInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from neuroconv.datainterfaces import NeuralynxNvtInterface
    >>>
    >>> # For this data interface we need to pass the folder where the data is
    >>> file_path = f"{BEHAVIOR_DATA_PATH}/neuralynx/test.nvt"
    >>> # Change the folder_path to the appropriate location in your system
    >>> interface = NeuralynxNvtInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # We add the time zone information, which is required by NWB
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
