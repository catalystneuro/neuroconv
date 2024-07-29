ScanImage data conversion
-------------------------

Install NeuroConv with the additional dependencies necessary for reading ScanImage data.

.. code-block:: bash

    pip install "neuroconv[scanimage]"

Convert single plane single file imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterfaces.ScanImageImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"
    >>> interface = ScanImageImagingInterface(file_path=file_path, channel_name="Channel 1", plane_name="0", verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Convert multi-plane (volumetric) single file imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert ScanImage volumetric imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterfaces.ScanImageImagingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ScanImageImagingInterface
    >>>
    >>> file_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage" / "scanimage_20220923_roi.tif"
    >>> interface = ScanImageImagingInterface(file_path=file_path, channel_name="Channel 1", verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/scanimage_multi_plane.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Convert single plane multi-file (buffered) imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert multi-file ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterfaces.ScanImageMultiFileImagingInterface`.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import ScanImageMultiFileImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"
    >>> file_pattern = "scanimage_20240320_multifile*.tif"
    >>> channel_name = "Channel 1"
    >>> interface = ScanImageMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/scanimage_single_plane_multi_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Convert multi-plane (volumetric) multi-file (buffered) imaging data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert volumetric multi-file ScanImage imaging data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.scanimage.scanimageimaginginterfaces.ScanImageMultiPlaneMultiFileImagingInterface`.

.. code-block:: python

    >>> from zoneinfo import ZoneInfo
    >>> from neuroconv.datainterfaces import ScanImageMultiFileImagingInterface
    >>>
    >>> folder_path = OPHYS_DATA_PATH / "imaging_datasets" / "ScanImage"
    >>> file_pattern = "scanimage_20220923_roi.tif"
    >>> channel_name = "Channel 1"
    >>> interface = ScanImageMultiFileImagingInterface(folder_path=folder_path, file_pattern=file_pattern, channel_name=channel_name, verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{output_folder}/scanimage_multi_plane_multi_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
