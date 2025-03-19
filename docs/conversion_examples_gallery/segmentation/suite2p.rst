suite2p
-------

Install NeuroConv with the additional dependencies necessary for reading suite2p data.

.. code-block:: bash

    pip install "neuroconv[suite2p]"

Convert suite2p segmentation data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.suite2p.suite2pdatainterface.Suite2pSegmentationInterface`.

Suite2p segmentation output is saved for each plane in a separate folder (e.g. "plane0", "plane1").
To specify which plane to convert, use the `plane_name` argument (to see what planes are available use the
`Suite2pSegmentationInterface.get_available_planes(folder_path)` method).
For multichannel recordings, use the `channel_name` argument to specify the channel name
(to see what channels are available use the `Suite2pSegmentationInterface.get_channel_names(folder_path)` method).
When not specified, the first plane and channel are used.

The optional `plane_segmentation_name` argument specifies the name of the :py:class:`~pynwb.ophys.PlaneSegmentation` to be created.
When multiple planes and/or channels are present, the name should be unique for each plane and channel combination (e.g. "PlaneSegmentationChan1Plane0").

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import Suite2pSegmentationInterface
    >>>
    >>> folder_path= OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> interface = Suite2pSegmentationInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

**Multi-plane example**

This example shows how to convert multiple planes from the same dataset.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import Suite2pSegmentationInterface
    >>>
    >>> folder_path= OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> interface_first_plane = Suite2pSegmentationInterface(folder_path=folder_path, plane_name="plane0", verbose=False)
    >>> interface_second_plane = Suite2pSegmentationInterface(folder_path=folder_path, plane_name="plane1", verbose=False)
    >>>
    >>> converter = ConverterPipe(data_interfaces=[interface_first_plane, interface_second_plane], verbose=False)
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/file2.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
