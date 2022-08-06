Neuralynx data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Neuralynx data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.neuralynx.neuralynxdatainterface.NeuralynxSortingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces.ecephys.neuralynx import NeuralynxSortingInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/neuralynx/Cheetah_v5.5.1/original_data"
    >>> # Change the folder_path to the location of the data in your system
    >>> interface = NeuralynxSortingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./neuralynx_conversion.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
