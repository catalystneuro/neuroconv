CaImAn
^^^^^^

Convert CaImAn segmentation data to NWB using :py:class:`~neuroconv.datainterfaces.ophys.caiman.caimandatainterface.CaimanSegmentationInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces.ophys.caiman import CaimanSegmentationInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5"
    >>> interface = CaimanSegmentationInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> metadata.update(NWBFile=dict())
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>>
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
