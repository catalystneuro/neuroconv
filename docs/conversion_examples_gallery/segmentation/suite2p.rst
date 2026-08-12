suite2p
-------

Install NeuroConv with the additional dependencies necessary for reading suite2p data.

.. code-block:: bash

    pip install "neuroconv[suite2p]"

**Convert a suite2p output folder**

Suite2p writes its segmentation output to one folder per plane ("plane0", "plane1"), each holding the
traces of every channel it segmented. Point :py:class:`~neuroconv.converters.Suite2pConverter` at the
folder containing them.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.converters import Suite2pConverter
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> converter = Suite2pConverter(folder_path=folder_path, verbose=False)
    >>>
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

That call covers any suite2p output folder, one plane or many, one channel or two. Each plane and
channel is written as its own :py:class:`~pynwb.ophys.PlaneSegmentation` and ``ImagingPlane`` with its
own traces, named for the pair it came from ("PlaneSegmentationChan1Plane0"). The "combined" folder
suite2p writes for a multi-plane session is skipped, since its ROIs are the per-plane ones
concatenated.

**Converting a single plane and channel**

Use :py:class:`~neuroconv.datainterfaces.ophys.suite2p.suite2pdatainterface.Suite2pSegmentationInterface`
to write one plane and one channel, chosen with the `plane_name` and `channel_name` arguments. To see
what is available, use `Suite2pSegmentationInterface.get_available_planes(folder_path)` and
`Suite2pSegmentationInterface.get_available_channels(folder_path)`. When neither is specified, the
first plane and channel are used.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import Suite2pSegmentationInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"
    >>> interface = Suite2pSegmentationInterface(folder_path=folder_path, plane_name="plane0", channel_name="chan1", verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/file2.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
