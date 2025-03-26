Video data conversion (multimedia formats)
------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading multimedia data.

.. code-block:: bash

    pip install "neuroconv[video]"

This interface can handle conversions from avi, mov, mp4, wmv, flv and most `FFmpeg <https://ffmpeg.org/>_` supported formats to NWB.

When storing videos of natural behavior, it is recommended to store this data as an external file with a link pointing
from the ImageSeries in NWB to the external file
(see `best practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>_`).
To follow this convention use the
:py:class:`~neuroconv.datainterfaces.behavior.video.externalvideodatainterface.ExternalVideoInterface` class.

Specify the metadata (optional)
~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    # video_metadata.yaml
    Behavior:
      Video:
        MyExternalVideo:
          description: "My description of the video data"
          unit: "Frames"
          ...


Run the conversion
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path

    >>> from neuroconv.datainterfaces import ExternalVideoInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> LOCAL_PATH = Path(".") # Path to neuroconv
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> editable_metadata_path = LOCAL_PATH / "tests" / "test_behavior" / "video_metadata.yaml"
    >>> interface = ExternalVideoInterface(file_paths=[video_file_path], verbose=False, video_name="MyExternalVideo")

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> editable_metadata = load_dict_from_file(editable_metadata_path)
    >>> metadata = dict_deep_update(metadata, editable_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)

If storing data directly in NWB, use the
:py:class:`~neuroconv.datainterfaces.behavior.video.internalvideodatainterface.InternalVideoInterface` class.

Specify the metadata (optional)
~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    # video_metadata.yaml
    Behavior:
      Video:
        MyInternalVideo:
          description: "My description of the video data"
          unit: "Frames"
          ...


Run the conversion
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path

    >>> from neuroconv.datainterfaces import InternalVideoInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> LOCAL_PATH = Path(".") # Path to neuroconv
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> editable_metadata_path = LOCAL_PATH / "tests" / "test_behavior" / "video_metadata.yaml"
    >>> interface = InternalVideoInterface(file_path=video_file_path, verbose=False, video_name="MyInternalVideo")

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> editable_metadata = load_dict_from_file(editable_metadata_path)
    >>> metadata = dict_deep_update(metadata, editable_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)


If using an older version of neuroconv, you can use the :py:class:`~neuroconv.datainterfaces.behavior.video.videodatainterface.VideoInterface` class.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import VideoInterface
    >>>
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = VideoInterface(file_paths=[video_file_path], verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
