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
files) into one series, use ``MultiFileCSVFiberPhotometryInterface``, described below. To write
several *separate* series (e.g. a signal and an isosbestic control) sharing one
``FiberPhotometryTable``, combine one interface per series (with distinct ``metadata_key`` values) in
a converter.

Interleaved (multiplexed) files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some CSVs **interleave** the excitation channels frame-by-frame down the rows rather than giving each
channel its own column, so one row is one channel at one timepoint. Pass a ``demux_configuration`` to read a
single channel out of such a file. There are two shapes, chosen by ``by``:

- ``{"by": "column", "column": ..., "values": ...}`` when a column labels each row's channel (e.g. a
  Neurophotometrics ``LedState``): reads the rows carrying this channel's label. One channel can be
  named by more than one label, and a list selects the rows carrying any of them. For example, an NPM
  ``LedState`` packs the digital input lines into the same integer as the excitation LED, so a single
  LED is written as several distinct codes. A startup frame with a label of its own is excluded for
  free, by carrying no channel's label; when its label *does* belong to a channel (an NPM
  initialization frame sets every excitation bit, so it carries every wavelength's label), pass
  ``"skip_rows": n`` to drop the ``n`` leading rows before the labels are consulted.
- ``{"by": "stride", "channels": k, "index": i, "skip_rows": n}`` when a header-less file cycles the
  channels in a fixed order with no label column: reads every ``k``-th row from offset ``i`` after
  dropping ``n`` leading calibration rows.

The interface stays single-series, so instantiate one interface per channel (with distinct
``metadata_key`` values) and combine them in a converter:

.. code-block:: python

    # A LedState column labels each row's excitation channel; one interface per channel.
    signal = CSVFiberPhotometryInterface(
        file_path=interleaved_path, data_columns="Region0G", timestamps_column="Timestamp",
        demux_configuration={"by": "column", "column": "LedState", "values": 2}, metadata_key="signal",
    )
    isosbestic = CSVFiberPhotometryInterface(
        file_path=interleaved_path, data_columns="Region0G", timestamps_column="Timestamp",
        demux_configuration={"by": "column", "column": "LedState", "values": 1}, metadata_key="isosbestic",
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

One file per channel
~~~~~~~~~~~~~~~~~~~~~

Some acquisition formats write one CSV file per channel/region rather than one wide CSV. GuPPy, for
instance, stores each region in its own file whose channel identity lives in the *filename*. Use
:py:class:`~neuroconv.datainterfaces.fiber_photometry.csv.multifilecsvfiberphotometrydatainterface.MultiFileCSVFiberPhotometryInterface`
for these. It reads ``data_columns`` from each file, in file-then-column order, and column-stacks
them into a single ``FiberPhotometryResponseSeries``. The channels share one time axis, taken from
the first file's ``timestamps_column``.

Because only channels on a common timebase can share one series, the first file must contain the
``timestamps_column``. Secondary files may omit it (their timestamps would be redundant); when a
secondary file *does* contain it, the interface asserts it matches the first file's timestamps, so
files that do not share a timebase fail loudly instead of producing a silently mis-timed series.

Here we use two per-channel CSVs (``Sample_Signal_Channel.csv`` and ``Sample_Control_Channel.csv``),
each with ``timestamps`` and ``data`` columns on a common timebase:

.. code-block:: text

    # Sample_Signal_Channel.csv     # Sample_Control_Channel.csv
    timestamps,data                 timestamps,data
    0.0,0.1                         0.0,0.05
    0.01,0.106                      0.01,0.053
    0.02,0.112                      0.02,0.056
    ...                             ...

.. code-block:: python

    >>> from neuroconv.datainterfaces import MultiFileCSVFiberPhotometryInterface

    >>> interface = MultiFileCSVFiberPhotometryInterface(file_paths=[csv_signal_channel_path, csv_control_channel_path], data_columns="data", timestamps_column="timestamps", metadata_key="calcium_signal", verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

NeuroConv writes as much metadata as is available in the source format, but most of the time the
experimenter has metadata that the records do not carry. Adding the rest improves the provenance of
the file and makes it more useful for future users and for the community as a whole. To add it, follow
:ref:`the fiber photometry how-to <annotate_fiber_photometry_metadata>`, which walks through common
experimental configurations, and in particular
:ref:`its section on templates <how_to_annotate_from_a_template>`, which starts from scratch.
For a general reference of every element the metadata accepts, see the
:ref:`reference template <fiber_photometry_metadata_template>`.
