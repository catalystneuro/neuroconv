Inscopix data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading Inscopix imaging data form .isxd files.

.. code-block:: bash

    pip install neuroconv[inscopix]

Convert Inscopix .isxd imaging data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.inscopix.inscopiximaginginterface.InscopixImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import InscopixImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "inscopix" / "movie_longer_than_3_min.isxd"
    >>> interface = InscopixImagingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
