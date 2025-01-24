Neuralynx data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading neuralynx data.

.. code-block:: bash

    pip install "neuroconv[neuralynx]"

Convert Neuralynx data to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.neuralynx.neuralynxdatainterface.NeuralynxSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import NeuralynxSortingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/neuralynx/Cheetah_v5.5.1/original_data"
    >>> # Change the folder_path to the location of the data in your system
    >>> # The stream is optional but is used to specify the sampling frequency of the data
    >>> interface = NeuralynxSortingInterface(folder_path=folder_path, verbose=False, stream_id="0")
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./neuralynx_conversion.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
