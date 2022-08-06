DeepLabCut data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert DeepLabCut imaging data to NWB using :py:class:`~neuroconv.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`.

#.. code-block:: python

#    >>> from datetime import datetime
#    >>> from dateutil import tz
#    >>> from pathlib import Path
#    >>> from neuroconv import DeepLabCutInterface
#    >>>
#    >>> file_path = BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
#    >>> config_file_path = BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"
#    >>>
#    >>> interface = DeepLabCutInterface(file_path=file_path, config_file_path=config_file_path, subject_name="ind1",
#verbose=False)
#    >>> metadata = interface.get_metadata()
##    >>> # For data provenance we add the time zone information to the conversion
#    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
#    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
#    >>> # Choose a path for saving the nwb file and run the conversion
#    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
#    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
#    >>> Path(path_to_save_nwbfile).is_file()
#    True
