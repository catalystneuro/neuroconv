SpikeGLX data conversion
------------------------

Install NeuroConv with the additional dependencies necessary for reading SpikeGLX data.

.. code-block:: bash

    pip install "neuroconv[spikeglx]"



SpikeGLXConverter
~~~~~~~~~~~~~~~~~

We can easily convert all data stored in the native SpikeGLX folder structure to NWB using
:py:class:`~neuroconv.converters.SpikeGLXConverterPipe`.

By default, the converter includes synchronization channels from Neuropixel probes (one per probe).
These channels contain a 16-bit status word where bit 6 carries a 1 Hz square wave (toggling every
0.5 seconds) used for sub-millisecond timing alignment across acquisition devices. To exclude sync
channels, set ``include_sync_channels=False``.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo
    >>> from pathlib import Path
    >>> from neuroconv.converters import SpikeGLXConverterPipe
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0"
    >>> # Sync channels are included by default
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


Synchronization Channels
~~~~~~~~~~~~~~~~~~~~~~~~~

SpikeGLX records synchronization channels (labeled as SY0) as the last channel in Neuropixel probe data streams.
These channels contain a 16-bit status word where **bit 6** carries a **1 Hz square wave** (toggling between 0 and 1
every 0.5 seconds) used for sub-millisecond timing alignment across multiple acquisition devices and data streams.
The other bits in the status word carry hardware status and error flags.

**Key technical details:**

- For **Neuropixels 1.0**, the sync channel appears **identically** in both AP and LF files, providing redundant
  timing information for alignment.
- For **Neuropixels 2.0** (full-band), the sync channel appears in the single AP file.
- The sync signal can be generated either **internally** by the Imec module (PXIe or OneBox) or **externally**
  by an NI-DAQ device acting as the master sync generator.
- In **multi-probe** setups, the same 1 Hz sync pulse is distributed to all probes, enabling precise cross-probe
  alignment by matching the rising edges in each stream's sync channel.
- When using **NIDQ**, the sync pulse is typically recorded on a designated analog or digital input channel
  rather than in a dedicated status word.

By default, the :py:class:`~neuroconv.converters.SpikeGLXConverterPipe` includes sync channels (one per probe,
preferring AP over LF when both are available). For more control over specific sync channels, you can use
:py:class:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxsyncchannelinterface.SpikeGLXSyncChannelInterface`.

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
