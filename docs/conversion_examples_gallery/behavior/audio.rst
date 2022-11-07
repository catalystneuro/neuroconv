Audio data conversion
---------------------

Install NeuroConv with the additional dependencies necessary for reading audio data.

.. code-block:: bash

    pip install neuroconv[audio]

This interface can handle conversions from `WAV` format to NWB using the
:py:class:`~neuroconv.datainterfaces.behavior.audio.audiointerface.AudioInterface` class.

.. code-block:: python

    >>> from datetime import datetime
    >>> from dateutil import tz
    >>> from pathlib import Path
    >>>
    >>> from neuroconv.datainterfaces.behavior.audio.audiointerface import AudioInterface
    >>>
    >>> audio_file_path = BEHAVIOR_DATA_PATH / "audio" / "audio_recording.wav"
    >>> interface = AudioInterface(file_paths=[audio_file_path], verbose=False)
    >>>
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = datetime(2020, 1, 1, 12, 30, 0, tzinfo=tz.gettz("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> interface.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata)
