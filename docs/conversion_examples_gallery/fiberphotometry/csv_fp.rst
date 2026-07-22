CSV Fiber Photometry data conversion
------------------------------------

Install NeuroConv with the additional dependencies necessary for reading CSV Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[csv_fp]"

This is a general-purpose CSV reader: point it at one CSV file and name the column holding the
timestamps in seconds (``timestamps_column``) and the data column(s) whose fluorescence samples form
the series (``data_columns``). Columns are addressed by name (for a CSV with a header row) or by
0-based positional index (for a header-less CSV).

The interface writes a single ``FiberPhotometryResponseSeries``; its channels are the ``data_columns``
read from the file, in column order, column-stacked into one series. This covers a narrow one-column
file (the GuPPy acquisition format's ``<stream>.csv`` with ``timestamps`` and ``data``) and a wide
file with several data columns. To aggregate *several* per-channel CSV files (e.g. GuPPy's per-region
files) into one series, use :doc:`MultiFileCSVFiberPhotometryInterface <multifile_csv_fp>`. To write
several *separate* series (e.g. a signal and an isosbestic control) sharing one
``FiberPhotometryTable``, combine one interface per series (with distinct ``metadata_key`` values) in
a converter.

Interleaved (multiplexed) files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some CSVs **interleave** the excitation channels frame-by-frame down the rows rather than giving each
channel its own column, so one row is one channel at one timepoint. Pass a ``demux`` config to read a
single channel out of such a file. There are two shapes, chosen by ``by``:

- ``{"by": "column", "column": ..., "value": ...}`` when a column labels each row's channel (e.g. a
  Neurophotometrics ``LedState``): reads the rows whose ``column`` equals ``value``. A startup frame is
  excluded simply by not being any interface's ``value``.
- ``{"by": "stride", "channels": k, "index": i, "skip_rows": n}`` when a header-less file cycles the
  channels in a fixed order with no label column: reads every ``k``-th row from offset ``i`` after
  dropping ``n`` leading calibration rows.

The interface stays single-series, so instantiate one interface per channel (with distinct
``metadata_key`` values) and combine them in a converter:

.. code-block:: python

    # A LedState column labels each row's excitation channel; one interface per channel.
    signal = CSVFiberPhotometryInterface(
        file_path=interleaved_path, data_columns="Region0G", timestamps_column="Timestamp",
        demux={"by": "column", "column": "LedState", "value": 2}, metadata_key="signal",
    )
    isosbestic = CSVFiberPhotometryInterface(
        file_path=interleaved_path, data_columns="Region0G", timestamps_column="Timestamp",
        demux={"by": "column", "column": "LedState", "value": 1}, metadata_key="isosbestic",
    )

Convert CSV Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert CSV Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.csv.csvfiberphotometrydatainterface.CSVFiberPhotometryInterface`.

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

Here we use a small example signal-channel CSV (``Sample_Signal_Channel.csv``) with ``timestamps``
and ``data`` columns:

.. code-block:: text

    timestamps,data
    0.0,0.1
    0.01,0.106
    0.02,0.112
    ...

.. code-block:: python

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import CSVFiberPhotometryInterface

    >>> # Inspect the file's column headers (callable before construction)
    >>> available_columns = CSVFiberPhotometryInterface.get_available_columns(file_path=csv_signal_channel_path)

    >>> interface = CSVFiberPhotometryInterface(file_path=csv_signal_channel_path, data_columns="data", timestamps_column="timestamps", metadata_key="calcium_signal", verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
