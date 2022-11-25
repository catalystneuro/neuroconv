Scanbox data conversion
-----------------------

Install NeuroConv with the additional dependencies necessary for reading Scanbox data.

.. code-block:: bash

    pip install neuroconv[scanbox]

Convert Scanbox imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.sbx.sbxdatainterface.SbxImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SbxImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Scanbox" / "sample.sbx"
    >>> interface = SbxImagingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
