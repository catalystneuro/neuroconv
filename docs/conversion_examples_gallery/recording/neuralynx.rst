Neuralynx data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^

Convert Neuralynx data to NWB using :py:class:`~.neuroconv.datainterfaces.ecephys.neuralynx.neuralynxdatainterface.NeuralynxRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces.ecephys.neuralynx import NeuralynxRecordingInterface
    >>>
    >>> # For this data interface we need to pass the folder where the data is
    >>> folder_path = f"{ECEPHY_DATA_PATH}/neuralynx/Cheetah_v5.7.4/original_data"
    >>> # Change the folder_path to the appropiate location in your system
    >>> interface = NeuralynxRecordingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # session_start_time is required for conversion. If it cannot be inferred
    >>> # automatically from the source files you must supply one.
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>>  # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "./saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
