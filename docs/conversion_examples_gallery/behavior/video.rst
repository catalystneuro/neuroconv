Video data conversion (multimedia formats)
------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading multimedia data.

.. code-block:: bash

    pip install "neuroconv[video]"

This interface can handle conversions from avi, mov, mp4, wmv, flv and most `FFmpeg <https://ffmpeg.org/>`_ supported formats to NWB.

.. note::
    If your video files are not in a DANDI-compatible format, see our guide on
    :doc:`../../how_to/convert_video_formats_with_ffmpeg` to convert them before processing with NeuroConv.

When storing videos of natural behavior, it is recommended to store this data as an external file with a link pointing
from the ImageSeries in NWB to the external file
(see `best practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>`_).
To follow this convention use the
:py:class:`~neuroconv.datainterfaces.behavior.video.externalvideodatainterface.ExternalVideoInterface` class.


.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path

    >>> from neuroconv.datainterfaces import ExternalVideoInterface

    >>> LOCAL_PATH = Path(".") # Path to neuroconv
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = ExternalVideoInterface(file_paths=[video_file_path], verbose=False, video_name="MyExternalVideo")

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, overwrite=True)

When storing videos of neural data, lossy compression should not be used and it is best to store within the NWB file
(see `best practices <https://nwbinspector.readthedocs.io/en/dev/best_practices/image_series.html#storage-of-imageseries>`_).
To follow this convention use the
:py:class:`~neuroconv.datainterfaces.behavior.video.internalvideodatainterface.InternalVideoInterface` class.


.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path

    >>> from neuroconv.datainterfaces import InternalVideoInterface

    >>> LOCAL_PATH = Path(".") # Path to neuroconv
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = InternalVideoInterface(file_path=video_file_path, verbose=False, video_name="MyInternalVideo")

    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)


If using an older version of neuroconv (<0.8), you can use the :py:class:`~neuroconv.datainterfaces.behavior.video.videodatainterface.VideoInterface` class.

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
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The examples above show how to convert video data without specifying any metadata, in which case the metadata will be
automatically generated with default values. To ensure that the NWB file is properly annotated, specify the metadata
using the formats described below.

For :py:class:`~neuroconv.datainterfaces.behavior.video.externalvideodatainterface.ExternalVideoInterface`,
use the following structure:

.. code-block:: python

    >>> video_metadata = {
    ...     "Behavior": {
    ...         "ExternalVideos": {
    ...             "MyExternalVideo": {  # This should match the video_name used in the interface
    ...                 "description": "My description of the video data",
    ...                 "device": {
    ...                     "name": "MyCamera",
    ...                     "description": "My description of the camera",
    ...                 },
    ...             }
    ...         }
    ...     }
    ... }

This metadata can then be easily incorporated into the conversion by updating the metadata dictionary.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import ExternalVideoInterface
    >>> from neuroconv.utils import dict_deep_update
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = ExternalVideoInterface(file_paths=[video_file_path], verbose=False, video_name="MyExternalVideo")
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata = dict_deep_update(metadata, video_metadata)
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

Similarly for :py:class:`~neuroconv.datainterfaces.behavior.video.internalvideodatainterface.InternalVideoInterface`:

.. code-block:: python

    >>> video_metadata = {
    ...     "Behavior": {
    ...         "InternalVideos": {
    ...             "MyInternalVideo": {  # This should match the video_name used in the interface
    ...                 "description": "My description of the video data",
    ...                 "device": {
    ...                     "name": "MyCamera",
    ...                     "description": "My description of the camera",
    ...                 },
    ...             }
    ...         }
    ...     }
    ... }
    >>>
    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import InternalVideoInterface
    >>> from neuroconv.utils import dict_deep_update
    >>> video_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = InternalVideoInterface(file_path=video_file_path, verbose=False, video_name="MyInternalVideo")
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> metadata = dict_deep_update(metadata, video_metadata)
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = f"{path_to_save_nwbfile}"  # This should be something like: "saved_file.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
