TIFF data conversion
--------------------

Install NeuroConv with the additional dependencies necessary for reading TIFF data.

.. code-block:: bash

    pip install "neuroconv[tiff]"

Convert TIFF imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import TiffImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"
    >>> interface = TiffImagingInterface(file_path=file_path, sampling_frequency=15.0, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


.. note::

    The :py:class:`~neuroconv.datainterfaces.ophys.tiff.tiffdatainterface.TiffImagingInterface` is designed for
    imaging data where all of the frames are in a multi-page TIFF file. It is not appropriate for datasets where the
    TIFF data is distributed across many files, for example from Bruker acquisition software.
