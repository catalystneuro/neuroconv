Neurophotometrics (NPM) Fiber Photometry data conversion
--------------------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neurophotometrics (NPM)
Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[npm_fp]"

The modern NPM format is a raw acquisition format that stores **interleaved** channels in a single
multi-column CSV. An isosbestic channel and one or more signal channels are multiplexed
frame-by-frame, distinguished by a ``Flags``/``LedState`` column, and each remaining column (e.g.
``Region0G``) is a region of interest.

``NPMFiberPhotometryInterface`` is a thin wrapper over
:doc:`CSVFiberPhotometryInterface <csv_fp>`: it auto-detects whether the file uses ``Flags`` or
``LedState`` and reads the one channel whose state equals ``led_state`` into a single
``FiberPhotometryResponseSeries``. Because each interface writes one series, you instantiate one per
channel (with distinct ``metadata_key`` values) and combine them in a converter. The startup frame
(an all-LEDs-on first frame, e.g. ``Flags=16``) is excluded for free by not being any interface's
``led_state``. For the older header-less NPM format, use
:doc:`NPMLegacyFiberPhotometryInterface <npm_legacy_fp>` instead.

Discovering channels and regions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two classmethods (callable before construction) report what to pass: ``get_available_led_states``
returns the ``Flags``/``LedState`` values (one per interleaved channel, plus the startup frame you
skip), and ``get_available_regions`` returns the region column names to choose ``data_columns`` from.

Convert NPM Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert modern NPM Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.npm.npmfiberphotometrydatainterface.NPMFiberPhotometryInterface`.

NPM recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import NPMFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "led_multiplexing" / "by_column" / "PagCeAVgatFear_14421.csv"

    >>> # Discover the channels (Flags/LedState values) and region columns before construction.
    >>> NPMFiberPhotometryInterface.get_available_led_states(file_path=file_path)
    [16, 17, 18]
    >>> NPMFiberPhotometryInterface.get_available_regions(file_path=file_path)
    ['Region0G', 'Region1G', 'Region2G']

    >>> # One interface reads one channel; Flags 17 is the isosbestic channel here.
    >>> interface = NPMFiberPhotometryInterface(file_path=file_path, led_state=17, data_columns="Region0G", metadata_key="isosbestic_region0", verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # NPM recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

To write both the isosbestic and the signal channels (and their regions) into one file sharing a
single ``FiberPhotometryTable``, instantiate one interface per channel — e.g. a second interface with
``led_state=18`` and a distinct ``metadata_key`` — and combine them in a converter.

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
