SpikeGLX data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading SpikeGLX data.

.. code-block:: bash

    pip install "neuroconv[spikeglx]"



SpikeGLXConverter
~~~~~~~~~~~~~~~~~

We can easily convert all data stored in the native SpikeGLX folder structure to NWB using
:py:class:`~neuroconv.converters.SpikeGLXConverterPipe`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.converters import SpikeGLXConverterPipe
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> converter = SpikeGLXConverterPipe(folder_path=folder_path)
    >>> # Extract what metadata we can from the source files
    >>> metadata = converter.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_converter_session.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Note that by default, the converter includes synchronization channels from Neuropixel probes (one per probe, preferring AP over LF).
To exclude sync channels, explicitly pass a ``streams`` argument with a list of streams without the '-SYNC' streams.

Single-stream
~~~~~~~~~~~~~

Defining a 'stream' as a single band on a single NeuroPixels probe, we can convert either an AP or LF SpikeGLX stream to NWB using
:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxdatainterface.SpikeGLXRecordingInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXRecordingInterface
    >>>
    >>> # For this interface we need to pass the location of the ``.bin`` file
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0"
    >>> # Options for the streams are "imec0.ap", "imec0.lf", "imec1.ap", "imec1.lf", etc.
    >>> # Depending on the device and the band of interest, choose the appropriate stream
    >>> interface = SpikeGLXRecordingInterface(folder_path=folder_path, stream_id="imec0.ap", verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_session.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


NIDQ Board
~~~~~~~~~~

In SpikeGLX, the NIDQ stream is used to record both analog and digital (usually non-neural) signals.
The :py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxnidqinterface.SpikeGLXNIDQInterface` interface
can be used to convert these streams to NWB.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> # For this interface we need to pass the folder containing the .nidq files
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> interface = SpikeGLXNIDQInterface(folder_path=folder_path, verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_session.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Customizing analog channel metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Analog channels (XA and MA channels) can be split into separate TimeSeries objects by specifying
channel groups at interface initialization. This is useful when different analog channels represent
different signal types (e.g., audio, sensors, accelerometers).

.. code-block:: python

    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> metadata_key = "my_custom_metadata_key"
    >>>
    >>> # Specify channel groups at initialization
    >>> analog_channel_groups = {
    ...     "audio": {
    ...         "channels": ["nidq#XA0"],  # Single channel for audio
    ...     },
    ...     "accel": {
    ...         "channels": ["nidq#XA3", "nidq#XA4", "nidq#XA5"],  # Group 3 channels for accelerometer
    ...     },
    ... }
    >>> interface = SpikeGLXNIDQInterface(
    ...     folder_path=folder_path,
    ...     metadata_key=metadata_key,
    ...     analog_channel_groups=analog_channel_groups,
    ... )
    >>>
    >>> # Get metadata - groups are automatically structured with CamelCase default names
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Customize metadata (names, descriptions, etc.)
    >>> metadata["TimeSeries"][metadata_key].update({
    ...     "audio": {
    ...         "name": "TimeSeriesAudioSignal",
    ...         "description": "Microphone audio recording",
    ...     },
    ...     "accel": {
    ...         "name": "TimeSeriesAccelerometer",
    ...         "description": "3-axis accelerometer (X, Y, Z)",
    ...     },
    ... })
    >>>
    >>> # Run conversion - only specified channels are written
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_custom_analog.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Customizing digital channel metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Digital channels (XD channels) can be customized with semantic labels and descriptions. This is useful when you
know what each digital channel represents (e.g., camera frames, TTL pulses, etc.). The ``digital_channel_groups``
parameter is specified at initialization, similar to ``analog_channel_groups``.

.. code-block:: python

    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/DigitalChannelTest_g0"
    >>> metadata_key = "SpikeGLXNIDQ"
    >>>
    >>> # Configure digital channels at initialization with semantic labels
    >>> # The labels_map maps raw extractor values (0, 1, ...) to meaningful and descriptive names
    >>> digital_channel_groups = {
    ...     "camera": {
    ...         "channels": {
    ...             "nidq#XD0": {"labels_map": {0: "exposure_end", 1: "frame_start"}},
    ...         },
    ...     },
    ... }
    >>> interface = SpikeGLXNIDQInterface(
    ...     folder_path=folder_path,
    ...     metadata_key=metadata_key,
    ...     digital_channel_groups=digital_channel_groups,
    ... )
    >>>
    >>> # Get metadata and customize NWB properties (name, description, meanings)
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Customize the NWB properties for the camera group
    >>>
    >>> metadata["Events"][metadata_key] = {
    ...     "camera": {
    ...         "name": "CameraFrameEvents",
    ...         "description": "Camera frame timing events",
    ...         "meanings": {
    ...             "exposure_end": "Camera exposure period ended, frame readout complete",
    ...             "frame_start": "New camera frame acquisition started",
    ...         },
    ...     },
    ... }
    >>>
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> # Run conversion - only configured channels are written
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_custom_digital.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Note: If ``digital_channel_groups`` is ``None`` (default), all digital channels with events
are written using auto-generated labels from the extractor. Use an empty dict ``{}`` to exclude
all digital channels from the conversion.



Synchronization Channel
~~~~~~~~~~~~~~~~~~~~~~~

By default, the :py:class:`~neuroconv.converters.SpikeGLXConverterPipe` includes sync channels (one per probe,
preferring AP over LF when both are available). For more control over the addition of the sync channels, you can use
:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxsyncchannelinterface.SpikeGLXSyncChannelInterface` directly.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import SpikeGLXSyncChannelInterface
    >>>
    >>> # For this interface we need to specify the sync stream ID
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> # Options for sync streams: "imec0.ap-SYNC", "imec0.lf-SYNC", "imec1.ap-SYNC", etc.
    >>> interface = SpikeGLXSyncChannelInterface(folder_path=folder_path, stream_id="imec0.ap-SYNC", verbose=False)
    >>>
    >>> # Extract what metadata we can from the source files
    >>> metadata = interface.get_metadata()
    >>> # For data provenance we add the time zone information to the conversion
    >>> session_start_time = metadata["NWBFile"]["session_start_time"].replace(tzinfo=ZoneInfo("US/Pacific"))
    >>> metadata["NWBFile"].update(session_start_time=session_start_time)
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_sync.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Note: If ``analog_channel_groups`` is not specified (default), all analog channels are written
to a single TimeSeries. Each group creates a separate TimeSeries in the NWB file, allowing you
to organize related signals together and customize their metadata independently.
