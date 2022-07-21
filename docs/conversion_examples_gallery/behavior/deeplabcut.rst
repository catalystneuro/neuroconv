DeepLabCut data conversion
^^^^^^^^^^^^^^^^^^^^^^^^^^

Convert DeepLabCut imaging data to NWB using :py:class:`~nwb_conversion_tools.datainterfaces.behavior.deeplabcut.deeplabcutdatainterface.DeepLabCutInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>> from nwb_conversion_tools import DeepLabCutInterface
    >>>
    >>> file_path = BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
    >>> config_file_path = BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"
    >>> subject_name = "ind1"
    >>>
    >>> interface = DeepLabCutInterface(file_path=file_path, config_file_path=config_file_path, subject_name=subject_name, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> metadata.update(NWBFile=dict())
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(nwbfile_path).is_file()
    True
