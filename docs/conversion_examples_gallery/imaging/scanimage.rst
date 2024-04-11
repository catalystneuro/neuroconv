ScanImage data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading ScanImage data.

.. code-block:: bash

    pip install neuroconv[scanimage]

Convert single plane single file imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterface.ScanImageImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "sample_scanimage.tiff"
    >>> interface = ScanImageImagingInterface(file_path=file_path, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific")) if "session_start_time" in metadata["NWBFile"] else datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Convert single plane multi-file (buffered) imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert multi-file ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterface.ScanImageSinglePlaneMultiFileImagingInterface`.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.datainterfaces import ScanImageSinglePlaneMultiFileImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"
    >>> file_pattern = "scanimage_20240320_multifile*.tif"
    >>> channel_name = "Channel 1"
    >>> interface = ScanImageSinglePlaneMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/scanimage_single_plane.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Convert multi-plane (volumetric) multi-file (buffered) imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert volumetric multi-file ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterface.ScanImageMultiPlaneMultiFileImagingInterface`.

.. code-block:: python

    >>> from dateutil import tz
    >>> from neuroconv.datainterfaces import ScanImageMultiPlaneMultiFileImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"
    >>> file_pattern = "scanimage_20220923_roi.tif"
    >>> channel_name = "Channel 1"
    >>> interface = ScanImageMultiPlaneMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/scanimage_multi_plane.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
