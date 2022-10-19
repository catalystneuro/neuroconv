Video data conversion (multimedia formats)
------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading multimedia data.

.. code-block:: bash

    pip install neuroconv[movie]

This interface can handle conversions from avi, mov, mp4, wmv, flv and most FFmpeg supported formats to NWB using the
:py:class:`~neuroconv.datainterfaces.behavior.movie.moviedatainterface.MovieInterface` class.

.. code-block:: python

    >>> from datetime import datetime
    >>> from tabnanny import verbose
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces import MovieInterface
    >>>
    >>> movie_file_path = BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi"
    >>> interface = MovieInterface(file_paths=[movie_file_path], verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
    root pynwb.file.NWBFile ...
    >>> # If the conversion was successful this should evaluate to ``True`` as the file was created.
    >>> Path(path_to_save_nwbfile).is_file()
    True
