Doric Fiber Photometry data conversion
---------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Doric Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[doric_fp]"

Discover available signal streams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface` reads the formats produced by
Doric Neuroscience Studio, chosen automatically from the ``file_path`` extension and, for ``.doric``,
the internal HDF5 layout:

* ``.doric`` (HDF5), newer layout: streams are auto-discovered by walking ``DataAcquisition`` for
  groups that contain a ``Time`` sibling dataset.  Each non-``Time`` 1-D dataset becomes a stream
  whose name is built from its HDF5 path (relative to ``DataAcquisition``) with ``/`` replaced by
  ``_``.
* ``.doric`` (HDF5), legacy "EPConsole" layout: each stream is its own group nested under
  ``Traces/<console>/`` holding a single dataset of the same name (e.g.
  ``Traces/Console/AIn-1 - Raw/AIn-1 - Raw``), with the shared timestamps in a sibling time-like
  group (e.g. ``Traces/Console/Time(s)/...``). Stream names are built the same way, relative to
  ``Traces`` (e.g. ``Console_AIn-1 - Raw``). This layout is tried automatically when the newer one
  yields no streams.
* ``.csv`` (DoricStudio CSV export): one shared time column (matched case-insensitively against
  ``"time"``/``"Time(s)"``) plus one or more data columns; each data column is a stream named after
  its column header (e.g. ``sig``, ``ref``). Older exports that prepend a channel/device "group"
  line above the real header (e.g. ``---,Analog In. | Ch.1,...`` followed by
  ``Time(s),AIn-1 - Dem (ref),...``) are handled automatically, as are trailing empty columns.

Call :py:meth:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface.get_available_streams` (callable
before construction) to discover stream names for any of these variants.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"
    >>> available_streams = DoricFiberPhotometryInterface.get_available_streams(file_path=file_path)

    >>> # The CSV export works the same way
    >>> csv_file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "oft_2024-03-01T10_16_32_signal.csv"
    >>> csv_streams = DoricFiberPhotometryInterface.get_available_streams(file_path=csv_file_path)
    >>> print(csv_streams)
    ['ref', 'sig']

    >>> # As does the legacy "EPConsole" HDF5 layout
    >>> legacy_file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "D2-EPConsole_0039_stub.doric"
    >>> legacy_streams = DoricFiberPhotometryInterface.get_available_streams(file_path=legacy_file_path)
    >>> print(legacy_streams)
    ['Console_AIn-1 - Raw', 'Console_AIn-2 - Raw', 'Console_DI--O-1']

Convert Doric Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert Doric Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.doric.doricfiberphotometrydatainterface.DoricFiberPhotometryInterface`.
Each interface writes a single ``FiberPhotometryResponseSeries``, assembled from one or more input
streams; combine multiple interfaces (with distinct ``metadata_key`` values) in a converter to write
several series sharing one ``FiberPhotometryTable``.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"

    >>> interface = DoricFiberPhotometryInterface(
    ...     file_path=file_path,
    ...     stream_names="BBC300_ROISignals_Series0001_CAM1EXC1_ROI01",
    ...     metadata_key="calcium_signal_dms",
    ...     verbose=False,
    ... )
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Eastern"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> # get_metadata() returns an editable scaffold; the required fiber photometry fields (excitation/
    >>> # emission wavelengths, indicator, location, ...) are pre-filled with placeholder values that
    >>> # should be replaced before archiving. add_to_nwbfile warns about any that remain unset.
    >>> # See :ref:`fiber_photometry_metadata_structure` for the full metadata format reference
    >>> # (device models, devices, indicators, and the FiberPhotometryTable), and how to fill in the
    >>> # scaffold above with real values via dict_deep_update.

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path = Path("doric_fiber_photometry.nwb")
    >>> # stub_test writes only the first stub_samples samples, which is useful for quick tests
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True, stub_test=True)

The CSV export is converted the same way — only ``file_path`` and ``stream_names`` change, since the
interface picks the reader based on the file extension:

.. code-block:: python

    >>> csv_file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "oft_2024-03-01T10_16_32_signal.csv"
    >>> csv_interface = DoricFiberPhotometryInterface(
    ...     file_path=csv_file_path,
    ...     stream_names="sig",
    ...     metadata_key="calcium_signal_dms",
    ...     verbose=False,
    ... )

.. note::

    The newer ``DataAcquisition``-based ``.doric`` HDF5 layout embeds a session start time (read
    from the file's ``Created`` attribute) that is set automatically in ``get_metadata()``. Neither
    the legacy "EPConsole" HDF5 layout nor the ``.csv`` export embeds one, so
    ``metadata["NWBFile"]["session_start_time"]`` must always be set by hand when converting from
    either of those.

.. seealso::

    :ref:`fiber_photometry_metadata_structure` for the full metadata format reference shared by all
    single-series fiber photometry interfaces.
