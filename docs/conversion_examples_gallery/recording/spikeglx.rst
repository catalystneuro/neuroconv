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


Converting digital lines to events
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The NIDQ board's digital lines (the ``XD`` channels) are written as ``pynwb`` ``EventsTable`` objects
into ``nwbfile.events``, one table per event type.

SpikeGLX does not save each digital line as its own channel. It packs up to sixteen of them into one
integer *word* per sample, so ``~snsChanMap`` lists a single ``XD0`` entry and a line is addressed as
word plus bit, which is the same addressing SpikeGLX's own CatGT tool uses. That is what
``detection_configuration`` spells out: it maps a signal to a list of detection specs, one per event
type you want derived from it.

.. code-block:: python

    >>> from neuroconv.datainterfaces import SpikeGLXNIDQInterface
    >>>
    >>> folder_path = f"{ECEPHY_DATA_PATH}/spikeglx/DigitalChannelTest_g0"
    >>>
    >>> # Two lines carved out of the same word, each read the way its signal calls for.
    >>> detection_configuration = {
    ...     "XD0": [
    ...         {
    ...             "signal_conditioning": {"bits": [0]},
    ...             "detection": "high_period",
    ...             "event_name": "camera_exposure",
    ...         },
    ...         {
    ...             "signal_conditioning": {"bits": [1]},
    ...             "detection": "rising",
    ...             "event_name": "trial_start",
    ...         },
    ...     ],
    ... }
    >>> interface = SpikeGLXNIDQInterface(
    ...     folder_path=folder_path,
    ...     detection_configuration=detection_configuration,
    ... )
    >>>
    >>> metadata = interface.get_metadata()
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>>
    >>> nwbfile_path = output_folder / "my_spikeglx_nidq_events.nwb"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

This writes two tables, ``CameraExposure`` and ``TrialStart``. Both lines are carved out of the one
``XD0`` word, and the word is read from disk once however many lines you take from it.

The two readings are different on purpose. A camera exposure line is meaningfully durative, so
``high_period`` records each pulse as an onset plus the span to its falling edge, in a ``duration``
column. A trial-start pulse only marks an instant, so ``rising`` records the onset alone and the table
has no ``duration`` column at all. (In this particular fixture only line 0 ever toggles, so
``TrialStart`` comes out with zero rows.)

To customize how these events are named, described and grouped into tables once they are derived, see
:ref:`annotate_events_metadata`. ``detection_configuration`` decides *which* events exist; the events
metadata decides how they are presented.

``detection`` says which transitions become events and is required. ``"rising"`` and ``"falling"``
give a point event at each edge; ``"high_period"`` and ``"low_period"`` give a durative event, an
onset plus the span to the opposite edge. ``event_name`` replaces the derived identifier and also
names the written table (``camera_exposure`` above becomes a table named ``CameraExposure``); without it
the identifier is derived from the signal and its reading, for example ``XD0_bit0_high_period``.

If ``detection_configuration`` is ``None`` (the default), every line the file's ``niXDChans1`` header
field declares is read as a ``high_period``. That reading is lossless, since every transition is
preserved. A declared line that never toggles still gets its table, written with zero rows: the line
existed in the recording and nothing fired on it, and knowing which is which would require reading
the samples, which building metadata deliberately does not do. Pass an explicit configuration naming
only the lines you care about to avoid the empty tables, or ``{}`` to write no events at all while
still writing the analog channels.

The analog channels can be read as events too, since a TTL wired into an analog input is a common way
to get more lines out of a board. An analog signal is cut into a discrete one with ``binarize``
instead of ``bits``:

.. code-block:: python

    >>> detection_configuration = {
    ...     "XA3": [
    ...         {"signal_conditioning": {"binarize": 550.0}, "detection": "rising"},
    ...     ],
    ... }

Cut points are expressed in the signal's **stored values**, not in volts. The companion ``TimeSeries``
written for the same channel declares its physical unit and a conversion factor, so the two numbers
differ; ``interface.recording_extractor.get_traces(channel_ids=["nidq#XA3"])`` shows the values a
threshold is compared against (the reader keeps neo's stream-qualified ids; this interface's own
arguments take the board's names).

.. note::

    The older ``digital_channel_groups`` argument is deprecated and will be removed on or after
    August 2027. It still works, translated onto the grammar above: a group becomes a rising and a
    falling reading of its line routed into one table, so it still yields one object holding every
    edge, and its ``labels_map`` still names the two edges. What changes is that the object is an
    ``EventsTable`` in ``nwbfile.events`` rather than an ``ndx-events`` ``LabeledEvents`` in
    ``acquisition``, the state is carried by an ``event_type`` column rather than by an index into a
    ``labels`` list, and the timestamps sit on the recording's own clock. Use
    ``detection_configuration`` instead.

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
    ...         "channels": ["XA0"],  # Single channel for audio
    ...     },
    ...     "accel": {
    ...         "channels": ["XA3", "XA4", "XA5"],  # Group 3 channels for accelerometer
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

Note: If ``analog_channel_groups`` is ``None`` (default), all analog channels are written
to a single TimeSeries. If ``analog_channel_groups`` is specified, only channels included
in a group will be written and the rest will be ignored. Use an empty dict ``{}`` to exclude
all analog channels from the conversion.


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
