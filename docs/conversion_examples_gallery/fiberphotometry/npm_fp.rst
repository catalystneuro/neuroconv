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

NeuroConv aims to automatically add all the metadata annotations that are present in the source format.
It is often the case that crucial information is not available there, such as the anatomical location,
the meaning of the values, or a semantically meaningful description of the data. Follow
:ref:`the fiber photometry how-to <annotate_fiber_photometry_metadata>` for a modality-relevant guide to adding
this extra metadata, which makes the data more useful for future users and for the community as a whole.
Its :ref:`section on templates <how_to_annotate_from_a_template>` starts from scratch, and the
:ref:`reference template <fiber_photometry_metadata_template>` lists every element the metadata accepts.
