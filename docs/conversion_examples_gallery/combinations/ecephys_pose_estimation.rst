Electrophysiology and Behavior
------------------------------

This example showcases a conversion that combines two modalities of data electrophysiology and behavior in the form of pose estimation.
For this specific example were are combining a OpenEphys recording with KiloSort sorting results and PoseEstimation from DeepLabCut using the
:py:class:`~neuroconv.datainterfaces.ecephys.blackrock.blackrockdatainterface.BlackrockRecordingInterface`,
:py:class:`~neuroconv.datainterfaces.ecephys.kilosort.kilosortdatainterface.KiloSortSortingInterface`, and
:py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`. classes.

.. code-block:: python


    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv import ConverterPipe
    >>> from neuroconv.datainterfaces import BlackrockRecordingInterface, KiloSortSortingInterface, DeepLabCutInterface
    >>>
    >>>
    >>> file_path = f"{ECEPHY_DATA_PATH}/blackrock/FileSpec2.3001.ns5"
    >>> # Change the file_path to the location in your system
    >>> interface_blackrock = BlackrockRecordingInterface(file_path=file_path, verbose=False)
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/phy/phy_example_0"
    >>> # Change the folder_path to the location of the data in your system
    >>> interface_kilosort = KiloSortSortingInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Change the file_path and config_file_path to point to your DeepLabCut files
    >>> file_path = BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
    >>> interface_dlc = DeepLabCutInterface(file_path=file_path, verbose=False)
    >>>
    >>> # Now that we have defined the two interfaces we pass them to the ConverterPipe which will coordinate the
    >>> # concurrent conversion of the data
    >>> converter = ConverterPipe(data_interfaces=[interface_blackrock, interface_kilosort, interface_dlc], verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific")).isoformat()
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path,  metadata=metadata)
