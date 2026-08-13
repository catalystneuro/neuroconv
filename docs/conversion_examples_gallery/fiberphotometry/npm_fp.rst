Neurophotometrics (NPM) Fiber Photometry data conversion
--------------------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neurophotometrics (NPM)
Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[npm_fp]"

The NPM format is a raw acquisition format that stores **interleaved** channels in a single
multi-column CSV: the excitation channels are multiplexed frame-by-frame, labeled by a
``Flags``/``LedState`` column, and each remaining column (e.g. ``Region0G``) is a region of interest.

``NPMFiberPhotometryInterface`` reads the one channel named by ``excitation_wavelength_in_nm`` into a
single ``FiberPhotometryResponseSeries``, so instantiate one interface per channel (with distinct
``metadata_key`` values) and combine them in a converter.

Two classmethods, callable before construction, report what to pass:
``get_available_excitation_wavelengths`` lists the excitation wavelengths (nm) present in the file,
and ``get_available_regions`` lists the region columns to choose ``regions`` from. The columns NPM
writes around the regions (the clock and frame index, the excitation/TTL word, the digital lines) are a
closed set, so the regions are what is left once they are subtracted; the inherited
``get_available_columns`` is still there when you want the raw header instead.
For how the ``Flags``/``LedState`` word maps frames onto channels, see the
:py:class:`interface's API documentation <neuroconv.datainterfaces.fiber_photometry.npm.npmfiberphotometrydatainterface.NPMFiberPhotometryInterface>`.

Header-less Neurophotometrics output (Bonsai's stock ``CsvWriter``, without the ``Flags``/
``LedState`` column) has no NPM-specific structure and should be read with the generic
:doc:`CSVFiberPhotometryInterface <csv_fp>` instead.

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

    >>> # Discover the excitation wavelengths and the regions before construction.
    >>> NPMFiberPhotometryInterface.get_available_excitation_wavelengths(file_path=file_path)
    [415, 470]
    >>> NPMFiberPhotometryInterface.get_available_regions(file_path=file_path)
    ['Region0G', 'Region1G', 'Region2G']

    >>> # One interface reads one channel; 415 nm is the isosbestic channel here.
    >>> interface = NPMFiberPhotometryInterface(file_path=file_path, excitation_wavelength_in_nm=415, regions="Region0G", metadata_key="isosbestic_region0", verbose=False)
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

Filling the device models
~~~~~~~~~~~~~~~~~~~~~~~~~~

The CSV carries no hardware specifications, but Neurophotometrics publishes what the FP3002 contains,
so the excitation sources can be looked up and put into the metadata ``get_metadata()`` returned.
The company states no per-part model number for them, so the part is named rather than numbered:

.. code-block:: python

    >>> from neuroconv.tools.fiber_photometry_hardware_catalogue import (
    ...     get_reference_excitation_source_model,
    ... )

    >>> metadata = interface.get_metadata()
    >>> metadata["DeviceModels"]["excitation_source_model"] = get_reference_excitation_source_model(
    ...     manufacturer="Neurophotometrics", part="FP3002 415 nm"
    ... )
    >>> metadata["DeviceModels"]["excitation_source_model"]["wavelength_range_in_nm"]
    [400.0, 425.0]

Two Neurophotometrics parts stay yours to fill. The FP3002's camera is published only as an sCMOS
sensor: its manufacturer, model number and gain appear nowhere, so the catalogue records the sensor
type and leaves the rest unset rather than guessing. And the patch cords are published with a
numerical aperture given as a range, 0.37 to 0.4, where ``OpticalFiberModel`` requires a single
number, so pick the value matching the cord you have.

The rest of the metadata (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces.
:ref:`annotate_fiber_photometry_metadata` fills it in one block at a time, and
:ref:`fiber_photometry_metadata_template` is that same structure with its blanks unfilled, ready to
copy and edit. :ref:`fiber_photometry_device_models` lists every part the catalogue covers, with the
vendor page each value came from.
