MaxOne conversion
-----------------

Install NeuroConv with the additional dependencies necessary for reading MaxOne data.

.. code-block:: bash

    pip install neuroconv[maxwell]

Convert MaxOne data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.maxwell.maxonedatainterface.MaxOneRecordingInterface`.

.. code-block:: python

    >>> import os
    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import MaxOneRecordingInterface
    >>>
    >>> # If you do not have the Maxwell HDF5 plugin installed, call this first to automatically set it up.
    >>> hdf5_plugin_path = f"{HDF5_PLUGIN_PATH}"
    >>> MaxOneRecordingInterface.auto_install_maxwell_hdf5_compression_plugin(hdf5_plugin_path=hdf5_plugin_path)
    >>> os.environ['HDF5_PLUGIN_PATH'] = hdf5_plugin_path
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/maxwell/MaxOne_data/Record/000011/data.raw.h5"
    >>> # Change the file_path to the location in your system
    >>> interface = MaxOneRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
