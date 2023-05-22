suite2p
-------

Install NeuroConv with the additional dependencies necessary for reading suite2p data.

.. code-block:: bash

    pip install neuroconv[suite2p]

Convert suite2p segmentation data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.suite2p.suite2pdatainterface.Suite2pSegmentationInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import Suite2pSegmentationInterface
    >>>
    >>> folder_path= OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> interface = Suite2pSegmentationInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
