EXTRACT
-------

Install NeuroConv with the additional dependencies necessary for reading EXTRACT data.

.. code-block:: bash

    pip install neuroconv[extract]

Convert EXTRACT segmentation data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.extract.extractdatainterface.ExtractSegmentationInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ExtractSegmentationInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "extract"/ "2014_04_01_p203_m19_check01_extractAnalysis.mat"
    >>> sampling_frequency = 20.0 # The sampling frequency in units of Hz
    >>> interface = ExtractSegmentationInterface(file_path=file_path, sampling_frequency=sampling_frequency, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
