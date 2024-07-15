Neuralynx data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading Neuralynx data.

.. code-block:: bash

    pip install "neuroconv[neuralynx]"

Convert Neuralynx data to NWB using
:py:class:`~.neuroconv.datainterfaces.ecephys.neuralynx.neuralynxdatainterface.NeuralynxRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import NeuralynxRecordingInterface
    >>>
    >>> # For this data interface we need to pass the folder where the data is
    >>> folder_path = f"{ECEPHY_DATA_PATH}/neuralynx/Cheetah_v5.7.4/original_data"
    >>> # Change the folder_path to the appropriate location in your system
    >>> interface = NeuralynxRecordingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = metadata["NWBFile"]["session_start_time"]
    >>> session_start_time = session_start_time.replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"]["session_start_time"] = session_start_time
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


.. note::
    For Neuralynx NVT files, see :ref:`neuralynx_nvt_conversion`.
