Biocam conversion
-----------------

Install NeuroConv with the additional dependencies necessary for reading Biocam data.

.. code-block:: bash

    pip install neuroconv[biocam]

Convert Biocam data to NWB using :py:class:`~neuroconv.datainterfaces.ecephys.biocam.biocamdatainterface.BiocamRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import BiocamRecordingInterface
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/biocam/biocam_hw3.0_fw1.6.brw"
    >>> # Change the file_path to the location in your system
    >>> interface = BiocamRecordingInterface(file_path=file_path, verbose=False)
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
