Legacy Neurophotometrics (NPM) Fiber Photometry data conversion
---------------------------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neurophotometrics (NPM)
Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[npm_fp]"

The legacy NPM format is a raw, **header-less** acquisition CSV: the first column is the timestamp
(in milliseconds) and the remaining columns are region-of-interest values, with the interleaved
channels stored in a fixed row-cycling order (row ``i`` belongs to channel ``i %
number_of_channels``).

``NPMLegacyFiberPhotometryInterface`` is a thin wrapper over
:doc:`CSVFiberPhotometryInterface <csv_fp>`: with no header to key on, you pass how many channels are
interleaved (``number_of_channels``) and which one this interface reads (``index``), and it reads the
selected region column(s) into a single ``FiberPhotometryResponseSeries``. Columns are addressed by
0-based position. Legacy NPM timestamps are typically in milliseconds, so ``time_unit`` defaults to
``"milliseconds"`` (scaled to seconds on read). Because each interface writes one series, you
instantiate one per channel (with distinct ``metadata_key`` values) and combine them in a converter.
For the modern header-bearing NPM format (with a ``Flags``/``LedState`` column), use
:doc:`NPMFiberPhotometryInterface <npm_fp>` instead.

Convert legacy NPM Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert legacy NPM Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.npm.npmfiberphotometrydatainterface.NPMLegacyFiberPhotometryInterface`.

NPM recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

Here the file interleaves two channels; ``index=0`` reads the even rows (the isosbestic channel) and
column 1 is the region of interest:

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import NPMLegacyFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "led_multiplexing" / "by_row" / "PagCeAVgatFear_1512_1.csv"

    >>> interface = NPMLegacyFiberPhotometryInterface(file_path=file_path, number_of_channels=2, index=0, data_columns=1, metadata_key="isosbestic_column1", verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # NPM recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

To write the signal channel too, instantiate a second interface with ``index=1`` and a distinct
``metadata_key`` and combine them in a converter sharing one ``FiberPhotometryTable``.

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
