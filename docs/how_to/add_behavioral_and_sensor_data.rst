.. _add_behavioral_and_sensor_data:

How to Add Behavioral and Sensor Data from Acquisition Systems
===============================================================

This guide demonstrates how to add behavioral, analog, and other non-neural data from acquisition systems to NWB.

Many acquisition systems used primarily for electrophysiology can also record behavioral and analog signals alongside neural data.
Common examples include:

* **Position tracking**: X/Y coordinates from video tracking systems
* **Head direction**: Compass/orientation sensors
* **Eye tracking**: Gaze position or pupil diameter
* **Behavioral sensors**: Lick detectors, wheel encoders, lever presses
* **Analog inputs**: Temperature, light levels, custom TTL signals
* **Physiological signals**: Heart rate, respiration

When to Use This Guide
----------------------

For most common acquisition formats, NeuroConv provides dedicated ``DataInterface`` classes that automatically handle both neural and non-neural data.
Check the :ref:`Conversion Gallery <conversion_gallery>` to see if your format is already supported.

Some interfaces already support non-neural data streams:

* **SpikeGLX**: ``SpikeGLXNIDQInterface`` for analog/digital input channels
* **Open Ephys**: Interfaces for analog streams
* **Intan**: ``IntanRecordingInterface`` for analog channels

However, in many cases it may not be feasible to use these interfaces, or the functionality is not yet implemented in NeuroConv.
**This guide provides a workaround** using NeuroConv's integration with SpikeInterface to provide a
flexible way to add behavioral and analog data from any acquisition format supported by SpikeInterface.

The general workflow is:

1. Instantiate a SpikeInterface extractor directly for your format
2. Select the appropriate stream and channels
3. Add the data to an NWB file using NeuroConv helper functions
4. Customize metadata (names, descriptions, units, etc.)

This approach requires a bit more work but provides maximum flexibility for handling heterogeneous behavioral data.

Methods for Adding Data
------------------------

NeuroConv provides two methods to write SpikeInterface recordings to NWB:

1. :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_time_series_to_nwbfile` - For general time series data
2. :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_spatial_series_to_nwbfile` - For spatial/directional behavioral data (1D, 2D, or 3D)

When to Use SpatialSeries
~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~pynwb.behavior.SpatialSeries` is a specialized NWB data type (subclass of :py:class:`~pynwb.base.TimeSeries`) designed for storing spatial position
or directional data in 1D, 2D, or 3D coordinates. It includes fields for reference frames and is specifically
intended for behavioral tracking data that represents location or direction in space.

Concrete examples of data that should use ``SpatialSeries``:

* Position tracking (X, Y coordinates or X, Y, Z)
* Head direction / compass data (1D angle)
* Gaze position (X, Y)
* Any spatial location or directional data

If your data represents spatial position or direction, use the :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_spatial_series_to_nwbfile` method.

When to Use TimeSeries
~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~pynwb.base.TimeSeries` is the most general NWB data type for storing any time series data. It provides fields for data values,
timestamps, units, and descriptions, making it suitable for any temporal measurements that don't require the specialized
features of its subclasses.

Concrete examples of data that should use ``TimeSeries``:

* Behavioral measurements (e.g., lick sensor, wheel velocity, lever presses)
* Physiological signals (e.g., heart rate, respiration, temperature)
* Analog sensor readings (e.g., light levels, sound intensity, voltage traces)
* Environmental measurements (e.g., temperature, humidity, sound level)

If your data fits these categories, use the :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_time_series_to_nwbfile` method.

Loading Data from Acquisition Systems with SpikeInterface
-----------------------------------------------------------

SpikeInterface supports loading data from many acquisition formats (see the `SpikeInterface documentation <https://spikeinterface.readthedocs.io/en/latest/modules/extractors.html>`_ for a full list).
To correctly write behavioral data to NWB, you need to understand two key concepts: **data streams** and **channel selection**.

Understanding Data Streams
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Many acquisition formats organize data into multiple **streams**. A stream is a logical grouping of channels recorded together,
typically sharing the same sampling rate and data type.

For example, a SpikeGLX recording might contain:

* ``imec0.ap`` - High-frequency neural data (action potentials)
* ``imec0.lf`` - Low-frequency local field potentials
* ``nidq`` - Analog/digital input channels (behavioral sensors, triggers, etc.)

When loading data from formats with multiple streams, you must specify which stream to load:

.. code-block:: python

    import spikeinterface.extractors as se

    # First, discover available streams
    stream_names, stream_ids = se.read_spikeglx.get_streams(folder_path)
    print(f"Available streams: {stream_names}")
    # Output: ['imec0.ap', 'imec0.lf', 'nidq']

    # Load the behavioral/analog stream
    recording = se.read_spikeglx(folder_path, stream_name='nidq')

Similarly for other formats:

.. code-block:: python

    import spikeinterface.extractors as se

    # Neuralynx
    stream_names, stream_ids = se.read_neuralynx.get_streams(folder_path)
    recording = se.read_neuralynx(folder_path, stream_name='analog_inputs')

    # Open Ephys
    stream_names, stream_ids = se.read_openephys.get_streams(folder_path)
    recording = se.read_openephys(folder_path, stream_name='Acquisition_Board-100.Rhythm Data')

    # Blackrock
    stream_names, stream_ids = se.read_blackrock.get_streams(file_path)
    recording = se.read_blackrock(file_path, stream_name='analog')

Selecting Specific Channels
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Even after selecting the correct stream, you may need to select specific channels. For example, an ``nidq`` stream might contain
multiple behavioral sensors, but you want to write position data (X/Y channels) separately from other analog inputs.

Use ``recording.select_channels()`` to extract specific channels:

.. code-block:: python

    import spikeinterface.extractors as se

    # Load full NIDQ stream
    full_recording = se.read_spikeglx(folder_path, stream_name='nidq')

    # Select only position channels (X, Y)
    position_recording = full_recording.select_channels(channel_ids=['nidq#0', 'nidq#1'])

    # Select wheel encoder channel
    wheel_recording = full_recording.select_channels(channel_ids=['nidq#2'])

Adding Data
-----------

Before adding behavioral and sensor data, you must have an in-memory NWBFile object.

Creating an NWBFile
~~~~~~~~~~~~~~~~~~~

An NWBFile can be created using NeuroConv interfaces/converters (via the Interface method :py:meth:`~neuroconv.basedatainterface.BaseDataInterface.create_nwbfile`
or the Converter method :py:meth:`~neuroconv.nwbconverter.NWBConverter.create_nwbfile`) or directly with PyNWB:

.. code-block:: python

    from pynwb import NWBFile
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from uuid import uuid4

    nwbfile = NWBFile(
        session_description="Spatial navigation task in open field",
        identifier=str(uuid4()),  # Generate globally unique identifier
        session_start_time=datetime(2025, 1, 15, 10, 30, 0, tzinfo=ZoneInfo("US/Pacific")),
    )

These three fields are required. The ``identifier`` must be globally unique - using :py:func:`uuid.uuid4` ensures this.

Once you have an ``nwbfile`` object in-memory, you can add behavioral data using the methods below.

Adding Data as TimeSeries
~~~~~~~~~~~~~~~~~~~~~~~~~~

Example: Adding a Wheel Encoder Signal (Neuralynx)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from neuroconv.tools.spikeinterface import add_recording_as_time_series_to_nwbfile
    import spikeinterface.extractors as se

    # Load Neuralynx analog stream and select wheel encoder channel
    analog_recording = se.read_neuralynx(folder_path, stream_name='AnalogIO')
    wheel_recording = analog_recording.select_channels(channel_ids=['AIN1'])

    # Prepare metadata with descriptive name and detailed description
    metadata = {
        "TimeSeries": {
            "WheelEncoder": {
                "name": "TimeSeriesWheelEncoder",
                "description": (
                    "Wheel encoder signal from running wheel. "
                    "Positive values indicate forward rotation, negative values indicate backward rotation. "
                    "Recorded via Neuralynx analog input AIN1 at 2000 Hz. "
                    "Wheel diameter: 20 cm. Encoder resolution: 1024 pulses per revolution."
                ),
                "unit": "degrees",
                "comments": "Data low-pass filtered at 100 Hz to remove high-frequency noise",
            }
        }
    }

    # Add to NWB file
    add_recording_as_time_series_to_nwbfile(
        recording=wheel_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="WheelEncoder",
    )

Adding Data as SpatialSeries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example: Adding 2D Position Tracking Data (Blackrock)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from neuroconv.tools.spikeinterface import add_recording_as_spatial_series_to_nwbfile
    import spikeinterface.extractors as se

    # Load Blackrock analog stream and select position channels (X, Y)
    analog_recording = se.read_blackrock(file_path, stream_name='analog')
    position_recording = analog_recording.select_channels(channel_ids=['ainp1', 'ainp2'])

    # Prepare metadata with descriptive information
    metadata = {
        "SpatialSeries": {
            "Position2D": {
                "name": "SpatialSeriesPosition2D",
                "description": (
                    "Position of the animal in the 2D arena tracked via overhead camera. "
                    "Channel ainp1 (X): horizontal position, left to right. "
                    "Channel ainp2 (Y): vertical position, bottom to top. "
                    "Tracking performed using DeepLabCut with post-processing smoothing (Gaussian kernel, sigma=3 frames). "
                    "Arena dimensions: 1.0 x 1.0 meters. "
                    "Camera framerate: 30 Hz, synchronized to Blackrock system via digital input."
                ),
                "unit": "meters",
                "reference_frame": "Origin at bottom-left corner of arena, X-axis pointing right, Y-axis pointing up",
                "comments": "NaN values indicate tracking loss, typically during grooming behavior",
            }
        }
    }

    # Add to NWB file
    add_recording_as_spatial_series_to_nwbfile(
        recording=position_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="Position2D",
    )

Example: Adding 2D Gaze Position Data (Plexon)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from neuroconv.tools.spikeinterface import add_recording_as_spatial_series_to_nwbfile
    import spikeinterface.extractors as se

    # Load Plexon file and select eye tracking analog channels
    # Plexon systems record analog inputs that can include eye position from eye tracking systems
    stream_names, stream_ids = se.read_plexon.get_streams(file_path)
    analog_recording = se.read_plexon(file_path, stream_name='Analog')

    # Select the two channels corresponding to horizontal and vertical eye position
    gaze_recording = analog_recording.select_channels(channel_ids=['AI01', 'AI02'])

    metadata = {
        "SpatialSeries": {
            "GazePosition": {
                "name": "SpatialSeriesGazePosition",
                "description": (
                    "Eye position in 2D screen coordinates tracked via video-based eye tracker. "
                    "Channel AI01 (X): horizontal gaze position across screen (left to right). "
                    "Channel AI02 (Y): vertical gaze position (bottom to top). "
                    "Eye tracking performed using EyeLink 1000 at 500 Hz, analog output synchronized to Plexon system. "
                    "Screen dimensions: 1920x1080 pixels, 53 cm x 30 cm physical size. "
                    "Viewing distance: 57 cm. Data has been calibrated using 9-point calibration at session start. "
                    "Blinks and saccades >500 deg/s are marked as NaN."
                ),
                "unit": "degrees",  # degrees of visual angle
                "reference_frame": "Screen center (0, 0), X-axis pointing right, Y-axis pointing up, range ±20 degrees visual angle",
            }
        }
    }

    add_recording_as_spatial_series_to_nwbfile(
        recording=gaze_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="GazePosition",
    )

Writing the NWB File to Disk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After using :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_spatial_series_to_nwbfile` (or :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_time_series_to_nwbfile`),
the data has been added to the ``nwbfile`` object, but it still exists only in memory.
You can continue adding more data or metadata to the file. When ready to save, use :py:func:`~neuroconv.tools.configure_and_write_nwbfile`
to write the file to disk with optimized chunking and compression:

.. code-block:: python

    from neuroconv.tools import configure_and_write_nwbfile

    # The nwbfile now contains the SpatialSeries data in memory
    # You can add more data here if needed...

    # Write to disk with automatic chunking and compression
    nwb_file_path = "behavioral_data.nwb"
    configure_and_write_nwbfile(
        nwbfile=nwbfile,
        nwbfile_path=nwb_file_path,
        backend="hdf5",  # or "zarr"
    )

This function ensures that proper chunking and compression are applied to your data for efficient storage and access.
For advanced control over chunking and compression settings, see the :doc:`Backend Configuration <../user_guide/backend_configuration>` guide.

Understanding Metadata Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The metadata dictionaries passed to :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_time_series_to_nwbfile`
and :py:func:`~neuroconv.tools.spikeinterface.add_recording_as_spatial_series_to_nwbfile` follow a specific nested structure.

Metadata Dictionary Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Metadata is organized as nested dictionaries. The ``metadata_key`` parameter selects which nested dictionary to use:

.. code-block:: python

    # TimeSeries metadata structure
    metadata = {
        "TimeSeries": {                    # Top-level key: data type
            "WheelEncoder": {              # metadata_key: identifies this specific data stream
                "name": "TimeSeriesWheelEncoder",     # Required: unique object name in NWB file
                "description": "Wheel encoder signal...",  # Required: detailed description
                "unit": "degrees",         # Required: measurement unit
                "comments": "Optional additional notes",  # Optional
            }
        }
    }

    # SpatialSeries metadata structure
    metadata = {
        "SpatialSeries": {                 # Top-level key: data type
            "Position": {                  # metadata_key: identifies this specific data stream
                "name": "SpatialSeriesPosition",  # Required: unique object name in NWB file
                "description": "2D position tracking...",  # Required: detailed description
                "unit": "meters",          # Required: measurement unit for spatial coordinates
                "reference_frame": "Arena center (0,0), X-axis right, Y-axis forward",  # Required: coordinate system
                "comments": "Optional notes",  # Optional
            }
        }
    }

Combining Metadata From Multiple Series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When adding multiple data streams, combine them in a single metadata dictionary. The ``metadata_key`` parameter
selects which stream's metadata to use for each function call:

.. code-block:: python

    # Metadata for multiple data streams
    combined_metadata = {
        "TimeSeries": {
            "WheelSpeed": {
                "name": "TimeSeriesWheelSpeed",  # Each TimeSeries must have unique name
                "description": "Wheel rotation speed from optical encoder",
                "unit": "degrees_per_second",
            },
            "LickSensor": {
                "name": "TimeSeriesLickSensor",  # Different name from WheelSpeed
                "description": "Lick detection from capacitive sensor",
                "unit": "volts",
            }
        },
        "SpatialSeries": {
            "Position": {
                "name": "SpatialSeriesPosition",  # Can reuse "Position" since it's in SpatialSeries
                "description": "2D position from overhead camera",
                "unit": "meters",
                "reference_frame": "Arena center (0,0), X-axis right, Y-axis forward",
            }
        }
    }

    # Add each stream using metadata_key to select the appropriate metadata
    add_recording_as_time_series_to_nwbfile(
        recording=wheel_recording,
        nwbfile=nwbfile,
        metadata=combined_metadata,
        metadata_key="WheelSpeed",  # Selects TimeSeries -> WheelSpeed metadata
    )

    add_recording_as_time_series_to_nwbfile(
        recording=lick_recording,
        nwbfile=nwbfile,
        metadata=combined_metadata,
        metadata_key="LickSensor",  # Selects TimeSeries -> LickSensor metadata
    )

    add_recording_as_spatial_series_to_nwbfile(
        recording=position_recording,
        nwbfile=nwbfile,
        metadata=combined_metadata,
        metadata_key="Position",  # Selects SpatialSeries -> Position metadata
    )

.. note::
   All objects in an NWB file must have unique names. When adding multiple TimeSeries or SpatialSeries objects,
   ensure each has a distinct ``name`` field to avoid conflicts.

Full Example: Combining Neural and Behavioral Data in Intan
-----------------------------------------------------------

Here's a complete workflow that demonstrates adding both neural data (using NeuroConv's ``IntanRecordingInterface``)
and behavioral data (using the SpikeInterface integration) from the same Intan recording file:

.. code-block:: python

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from uuid import uuid4
    import spikeinterface.extractors as se
    from neuroconv.datainterfaces import IntanRecordingInterface, KilosortSortingInterface
    from neuroconv.tools.spikeinterface import (
        add_recording_as_spatial_series_to_nwbfile,
        add_recording_as_time_series_to_nwbfile,
    )
    from neuroconv.tools import configure_and_write_nwbfile

    # Path to Intan RHD file
    file_path = "/path/to/intan/recording_2025_03_20.rhd"

    # STEP 1: Create IntanRecordingInterface and get base metadata
    interface = IntanRecordingInterface(file_path=file_path, verbose=False)
    base_metadata = interface.get_metadata()

    # STEP 2: Define complete metadata for session and behavioral data
    metadata = {
        "NWBFile": {
            "session_description": "Visual discrimination task with lick response and wheel running",
            "identifier": str(uuid4()),
            "session_start_time": datetime(2025, 3, 20, 14, 30, 0, tzinfo=ZoneInfo("US/Pacific")),  # Note: Intan does not store session start time
            "lab": "Systems Neuroscience Lab",
            "institution": "University",
        },
        "SpatialSeries": {
            "Accelerometer": {
                "name": "SpatialSeriesAccelerometer",
                "description": (
                    "3D acceleration data from Intan headstage-mounted accelerometer recorded via auxiliary inputs. "
                    "AUX1 (X): medial-lateral acceleration. "
                    "AUX2 (Y): anterior-posterior acceleration. "
                    "AUX3 (Z): dorsal-ventral acceleration (gravity axis). "
                    "Used to detect movement, jumps, rearing, and head orientation relative to gravity. "
                    "Accelerometer range: ±2g. Calibration performed at session start."
                ),
                "unit": "meters_per_second_squared",
                "reference_frame": "Headstage coordinate system: X=left-right, Y=forward-back, Z=up-down relative to head",
                "comments": "Data includes gravity component. Z-axis at rest ~9.8 m/s² when head level",
            }
        },
        "TimeSeries": {
            "Photodiode": {
                "name": "TimeSeriesPhotodiode",
                "description": (
                    "Photodiode signal detecting visual stimulus onset for precise synchronization. "
                    "Recorded via Intan USB board ADC input channel 0 (ADC-0). "
                    "Signal changes from 0V (screen dark) to ~3.3V (screen bright) at stimulus onset. "
                    "Used to align neural responses with exact visual stimulus timing, "
                    "compensating for monitor refresh delays and software latencies."
                ),
                "unit": "volts",
                "comments": "Rising edges indicate stimulus onset; falling edges indicate stimulus offset",
            },
            "LickSensor": {
                "name": "TimeSeriesLickSensor",
                "description": (
                    "Capacitive lick sensor detecting tongue contact with water port. "
                    "Recorded via Intan USB board ADC input channel 1 (ADC-1). "
                    "Baseline ~0.5V, increases to ~4V during lick contact. "
                    "Sampled at 20 kHz to capture rapid lick events (6-8 Hz typical lick rate)."
                ),
                "unit": "volts",
            },
            "WheelVelocity": {
                "name": "TimeSeriesWheelVelocity",
                "description": (
                    "Running wheel velocity from rotary encoder. "
                    "Recorded via Intan USB board ADC input channel 2 (ADC-2). "
                    "Analog output from encoder: 0-5V maps to -50 to +50 cm/s. "
                    "Positive values indicate forward rotation, negative indicate backward. "
                    "Low-pass filtered at 100 Hz to remove encoder noise."
                ),
                "unit": "centimeters_per_second",
            }
        }
    }

    # STEP 3: Create NWBFile using interface with complete metadata
    # Note: create_nwbfile() automatically adds the neural data from the interface
    nwbfile = interface.create_nwbfile(metadata=metadata)

    # STEP 4: Add spike sorting data using KilosortSortingInterface
    sorting_folder_path = "/path/to/kilosort/output/folder"
    sorting_interface = KilosortSortingInterface(folder_path=sorting_folder_path, verbose=False)
    sorting_interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    # STEP 5: Load and add behavioral data streams
    # Load 3D accelerometer data from auxiliary inputs (AUX1, AUX2, AUX3)
    aux_recording = se.read_intan(file_path, stream_name='RHD2000 auxiliary input channel')
    accel_recording = aux_recording.select_channels(channel_ids=['AUX1', 'AUX2', 'AUX3'])

    add_recording_as_spatial_series_to_nwbfile(
        recording=accel_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="Accelerometer",
    )

    # Load analog signals from USB board ADC inputs
    adc_recording = se.read_intan(file_path, stream_name='USB board ADC input channel')

    # Add photodiode signal (ADC-0) for stimulus synchronization
    photodiode_recording = adc_recording.select_channels(channel_ids=['ADC-0'])
    add_recording_as_time_series_to_nwbfile(
        recording=photodiode_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="Photodiode",
    )

    # Add lick sensor signal (ADC-1)
    lick_recording = adc_recording.select_channels(channel_ids=['ADC-1'])
    add_recording_as_time_series_to_nwbfile(
        recording=lick_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="LickSensor",
    )

    # Add wheel velocity signal (ADC-2)
    wheel_recording = adc_recording.select_channels(channel_ids=['ADC-2'])
    add_recording_as_time_series_to_nwbfile(
        recording=wheel_recording,
        nwbfile=nwbfile,
        metadata=metadata,
        metadata_key="WheelVelocity",
    )

    # STEP 6: Save NWB file with optimized settings
    nwb_file_path = "intan_neural_behavioral_session.nwb"
    configure_and_write_nwbfile(
        nwbfile=nwbfile,
        nwbfile_path=nwb_file_path,
        backend="hdf5",
    )


Best Practices
--------------

Naming Conventions
^^^^^^^^^^^^^^^^^^

Follow `NWB best practices for naming <https://nwbinspector.readthedocs.io/en/dev/best_practices/general.html#naming-conventions>`_ TimeSeries and SpatialSeries objects:

* Use CamelCase format: ``TimeSeriesWheelVelocity``, ``SpatialSeriesPosition2D``
* Pattern: ``TimeSeries{DataType}`` or ``SpatialSeries{DataType}``
* Examples:
    * ``TimeSeriesLickSensor``
    * ``TimeSeriesTemperature``
    * ``SpatialSeriesGazePosition``
    * ``SpatialSeriesReachEndpoint``
* Avoid special characters (slashes, colons) that confuse HDF5/Zarr parsers
* Make names self-documenting but keep them concise

Writing Descriptions
^^^^^^^^^^^^^^^^^^^^

Behavioral data can be highly heterogeneous, so **write detailed, self-contained descriptions** that include:

* **What the data represents** (physical meaning, sensor type)
* **Channel mapping** (which channel is X vs Y, voltage mapping, etc.)
* **Acquisition details** (sampling rate, hardware model, synchronization method)
* **Preprocessing applied** (filtering, smoothing, interpolation)
* **Coordinate systems** (reference frames, origin location, axis directions)
* **Units and scales** (physical units after conversion from voltage)
* **Data quality notes** (expected noise, artifacts, missing data handling)

Bad example:

.. code-block:: python

    "description": "Position data"  # Too vague!

Good example:

.. code-block:: python

    "description": (
        "Position of the animal in the 2D circular arena tracked via overhead camera. "
        "Channel 0 (X): radial distance from center in meters (0-0.5 m range). "
        "Channel 1 (Y): angular position in radians (0-2π range). "
        "Tracking performed using Bonsai + FlyCapture at 60 Hz. "
        "Data synchronized to ephys via frame TTL pulses on NIDQ channel AI7."
    )

Verifying Data
^^^^^^^^^^^^^^

After writing data to NWB, **always verify that data was correctly written** by reading back and plotting the data:

.. code-block:: python

    from pynwb import read_nwb
    import matplotlib.pyplot as plt

    # Read the NWB file
    nwbfile_read = read_nwb(nwb_file_path)

    # Access the SpatialSeries
    spatial_series = nwbfile_read.acquisition['SpatialSeriesPosition2D']

    # Get data with units and timestamps
    position_data = spatial_series.get_data_in_units()
    timestamps = spatial_series.get_timestamps()
    unit = spatial_series.unit

    print(f"Data unit: {unit}")
    print(f"Data range X: {position_data[:, 0].min():.3f} to {position_data[:, 0].max():.3f} {unit}")
    print(f"Data range Y: {position_data[:, 1].min():.3f} to {position_data[:, 1].max():.3f} {unit}")

    # Plot to visually verify
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.plot(timestamps, position_data[:, 0], label='X')
    plt.plot(timestamps, position_data[:, 1], label='Y')
    plt.xlabel('Time (s)')
    plt.ylabel(f'Position ({unit})')
    plt.legend()
    plt.title('Position over time')

    plt.subplot(1, 2, 2)
    plt.plot(position_data[:, 0], position_data[:, 1])
    plt.xlabel(f'X ({unit})')
    plt.ylabel(f'Y ({unit})')
    plt.title('Trajectory')
    plt.axis('equal')

    plt.tight_layout()
    plt.show()
