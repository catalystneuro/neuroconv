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
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_converter_session.nwb"
    >>> converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)



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
    >>>
    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_session.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Customizing digital channel metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Digital channels (XD channels) can be customized with semantic labels and descriptions. This is useful when you
know what each digital channel represents (e.g., camera frames, TTL pulses, etc.). When using multiple NIDQ
interfaces in the same conversion, each interface must have a unique ``metadata_key`` to avoid metadata collisions.

.. code-block:: python

    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> # The metadata_key organizes metadata when using multiple NIDQ interfaces
    >>> # It must be unique for each interface to avoid metadata collisions
    >>> metadata_key = "SpikeGLXNIDQ"
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/DigitalChannelTest_g0"
    >>> interface = SpikeGLXNIDQInterface(folder_path=folder_path, metadata_key=metadata_key)
    >>>
    >>> # Get default metadata - digital channels are populated with extractor labels
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Customize multiple digital channels with semantic labels
    >>> # Channel XD0 represents camera frame events
    >>> metadata["Events"][metadata_key]["nidq#XD0"] = {
    ...     "name": "CameraEvents",
    ...     "description": "Camera frame events with exposure timing",
    ...     "labels_map": {0: "exposure_end", 1: "frame_start"}
    ... }
    >>>
    >>> # Channel XD1 represents TTL pulses from stimulation device
    >>> metadata["Events"][metadata_key]["nidq#XD1"] = {
    ...     "name": "StimulationTTL",
    ...     "description": "TTL pulses triggering stimulation events",
    ...     "labels_map": {0: "stim_off", 1: "stim_on"}
    ... }
    >>>
    >>> # Run conversion with custom metadata
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_custom.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)


Customizing analog channel metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Analog channels (XA and MA channels) can be split into separate TimeSeries objects with custom
metadata. This is useful when different analog channels represent different signal types (e.g.,
audio, sensors, accelerometers).

.. code-block:: python

    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> interface = SpikeGLXNIDQInterface(folder_path=folder_path)
    >>>
    >>> # Get default metadata
    >>> metadata = interface.get_metadata()
    >>>
    >>> # Customize analog channels with flat dictionary structure
    >>> metadata["TimeSeries"]["SpikeGLXNIDQ"] = {
    ...     "audio": {  # Arbitrary key for organization
    ...         "channels": ["nidq#XA0"],  # Required: list of channel IDs with nidq# prefix
    ...         "name": "TimeSeriesAudioSignal",  # Required: NWB TimeSeries name
    ...         "description": "Microphone audio recording",
    ...     },
    ...     "accel": {
    ...         "channels": ["nidq#XA3", "nidq#XA4", "nidq#XA5"],  # Group multiple channels
    ...         "name": "TimeSeriesAccelerometer",
    ...         "description": "3-axis accelerometer (X, Y, Z)",
    ...     }
    ... }
    >>>
    >>> # Run conversion - only nidq#XA0, nidq#XA3, nidq#XA4, nidq#XA5 written
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_custom.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

Note: Channels not listed in the configuration will not be written to the NWB file.
Each TimeSeries can contain one or more channels, allowing you to group related signals together.
