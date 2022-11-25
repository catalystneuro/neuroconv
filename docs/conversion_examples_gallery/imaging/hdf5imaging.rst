HDF5 data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading HDF5 data.

.. code-block:: bash

    pip install neuroconv[hdf5]

Convert HDF5 imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.hdf5.hdf5datainterface.Hdf5ImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import Hdf5ImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "hdf5" / "demoMovie.hdf5"
    >>> interface = Hdf5ImagingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
