Multi-File CSV Fiber Photometry data conversion
-----------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading CSV Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[csv_fp]"

Some acquisition formats write one CSV file per channel/region rather than one wide CSV — GuPPy, for
instance, stores each region in its own file whose channel identity lives in the *filename*. This
interface reads ``data_columns`` from each file, in file-then-column order, and column-stacks them
into a single ``FiberPhotometryResponseSeries``. The channels share one time axis, taken from the
first file's ``timestamps_column``.

Because only channels on a common timebase can share one series, the first file must contain the
``timestamps_column``. Secondary files may omit it (their timestamps would be redundant); when a
secondary file *does* contain it, the interface asserts it matches the first file's timestamps, so
files that do not share a timebase fail loudly instead of producing a silently mis-timed series.

For the common single-file case, use :doc:`CSVFiberPhotometryInterface <csv_fp>` instead.

Convert multi-file CSV Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert per-channel CSV Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.csv.multifilecsvfiberphotometrydatainterface.MultiFileCSVFiberPhotometryInterface`.

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

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

    >>> from datetime import datetime
    >>> from zoneinfo import ZoneInfo

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

The full metadata format (device models, devices, indicators, the ``FiberPhotometryTable``, and the
per-interface response series) is shared across the fiber photometry interfaces and documented at
:ref:`fiber_photometry_metadata_structure`.
