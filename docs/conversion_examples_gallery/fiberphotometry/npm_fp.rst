Neurophotometrics (NPM) Fiber Photometry data conversion
--------------------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neurophotometrics (NPM)
Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[npm_fp]"

The NPM format is a raw acquisition format that stores **interleaved** channels in a single
multi-column CSV. An isosbestic channel and one or more signal channels are multiplexed
frame-by-frame, distinguished by a ``Flags``/``LedState`` column, and each remaining column (e.g.
``Region0G``) is a region of interest. The ``Flags``/``LedState`` value is a packed word whose three
lowest bits encode which excitation LED was on (415, 470, or 560 nm) and whose higher bits are
digital TTL lines, so a single excitation channel can appear under several ``LedState`` values that
differ only in their TTL bits.

``NPMFiberPhotometryInterface`` is a thin wrapper over
:doc:`CSVFiberPhotometryInterface <csv_fp>`: it auto-detects whether the file uses ``Flags`` or
``LedState``, masks the three lowest bits, and reads the one channel matching a given
``excitation_wavelength_in_nm`` into a single ``FiberPhotometryResponseSeries`` (gathering all the
TTL-line variants of that LED). Because each interface writes one series, you instantiate one per
channel (with distinct ``metadata_key`` values) and combine them in a converter.

Header-less Neurophotometrics output (Bonsai's stock ``CsvWriter``, without the ``Flags``/
``LedState`` column) has no NPM-specific structure and should be read with the generic
:doc:`CSVFiberPhotometryInterface <csv_fp>` instead.

Discovering channels and columns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two classmethods (callable before construction) report what to pass:
``get_available_excitation_wavelengths`` returns the excitation wavelengths (nm) present in the file
(one per interleaved channel; non-channel frames such as an all-LEDs-on startup frame are left out),
and the inherited ``get_available_columns`` lists the file's column names to choose ``data_columns``
from (the region columns, alongside metadata columns like ``FrameCounter`` and the timestamp/state
columns).

Convert NPM Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert NPM Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.npm.npmfiberphotometrydatainterface.NPMFiberPhotometryInterface`.

NPM recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import NPMFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "header_and_state_column" / "three_green_regions.csv"

    >>> # Discover the excitation wavelengths and the file's columns before construction.
    >>> NPMFiberPhotometryInterface.get_available_excitation_wavelengths(file_path=file_path)
    [415, 470]
    >>> NPMFiberPhotometryInterface.get_available_columns(file_path=file_path)
    ['FrameCounter', 'Timestamp', 'Flags', 'Region0G', 'Region1G', 'Region2G']

    >>> # One interface reads one channel; 415 nm is the isosbestic channel here.
    >>> interface = NPMFiberPhotometryInterface(file_path=file_path, excitation_wavelength_in_nm=415, data_columns="Region0G", metadata_key="isosbestic_region0", verbose=False)
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
``excitation_wavelength_in_nm=470`` and a distinct ``metadata_key`` — and combine them in a converter.

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
