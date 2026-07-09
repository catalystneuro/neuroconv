Doric Fiber Photometry data conversion
---------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Doric Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[doric_fp]"

Discover available signal streams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface` reads two formats produced by
Doric Neuroscience Studio, chosen automatically from the ``file_path`` extension:

* ``.doric`` (HDF5): streams are auto-discovered by walking ``DataAcquisition`` for groups that
  contain a ``Time`` sibling dataset.  Each non-``Time`` 1-D dataset becomes a stream whose name is
  built from its HDF5 path (relative to ``DataAcquisition``) with ``/`` replaced by ``_``.
* ``.csv`` (DoricStudio CSV export): one shared time column (matched case-insensitively against
  ``"time"``/``"Time(s)"``) plus one or more data columns; each data column is a stream named after
  its column header (e.g. ``sig``, ``ref``). Older exports that prepend a channel/device "group"
  line above the real header (e.g. ``---,Analog In. | Ch.1,...`` followed by
  ``Time(s),AIn-1 - Dem (ref),...``) are handled automatically, as are trailing empty columns.

Call :py:meth:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface.get_available_streams` (callable
before construction) to discover stream names for either format.

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

Specify the minimal metadata required for the conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All hardware metadata must be supplied by the user — this interface does not inject hardware defaults.
The metadata lives at the top-level key ``metadata["FiberPhotometry"]``. Shared containers (device
models, devices, indicators, and the table) are dicts keyed by an arbitrary ``metadata_key`` handle;
entries reference each other with ``_metadata_key`` fields (e.g. a table row's
``optical_fiber_metadata_key``), and the response series references table rows via
``fiber_photometry_table_region`` (a list of row keys). See :ref:`fiber_photometry_metadata_structure`
for the full format reference.

``get_metadata()`` already returns a scaffold with one entry of each container, keyed by the same
default handles used below (``"optical_fiber_model"``, ``"optical_fiber"``, ``"row0"``, ...) — this
example fills in that same scaffold with real values via :func:`~neuroconv.utils.dict_deep_update`, so
each key below must match its scaffold counterpart rather than introduce a new one, otherwise the
placeholder and the real entry are written as two separate (conflicting) objects.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "Ophys": {
    ...         "FiberPhotometry": {
    ...             "OpticalFiberModels": [
    ...                 {
    ...                     "name": "optical_fiber_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "numerical_aperture": 0.48,
    ...                     "core_diameter_in_um": 400.0,
    ...                 }
    ...             ],
    ...             "OpticalFibers": [
    ...                 {
    ...                     "name": "optical_fiber",
    ...                     "model": "optical_fiber_model",
    ...                     "fiber_insertion": {"depth_in_mm": 2.8},
    ...                 }
    ...             ],
    ...             "ExcitationSourceModels": [
    ...                 {
    ...                     "name": "excitation_source_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "source_type": "LED",
    ...                     "excitation_mode": "one-photon",
    ...                 }
    ...             ],
    ...             "ExcitationSources": [
    ...                 {
    ...                     "name": "excitation_source_465nm",
    ...                     "model": "excitation_source_model",
    ...                 }
    ...             ],
    ...             "PhotodetectorModels": [
    ...                 {
    ...                     "name": "photodetector_model",
    ...                     "manufacturer": "Doric Lenses",
    ...                     "detector_type": "photodiode",
    ...                 }
    ...             ],
    ...             "Photodetectors": [
    ...                 {
    ...                     "name": "photodetector",
    ...                     "model": "photodetector_model",
    ...                 }
    ...             ],
    ...             "FiberPhotometryIndicators": [
    ...                 {
    ...                     "name": "green_fluorophore",
    ...                     "description": "GCaMP7b calcium indicator.",
    ...                     "label": "GCaMP7b",
    ...                 }
    ...             ],
    ...             "FiberPhotometryTable": {
    ...                 "name": "fiber_photometry_table",
    ...                 "description": "Fiber photometry system metadata.",
    ...                 "rows": [
    ...                     {
    ...                         "location": "DMS",
    ...                         "excitation_wavelength_in_nm": 465.0,
    ...                         "emission_wavelength_in_nm": 525.0,
    ...                         "indicator": "green_fluorophore",
    ...                         "optical_fiber": "optical_fiber",
    ...                         "excitation_source": "excitation_source_465nm",
    ...                         "photodetector": "photodetector",
    ...                     }
    ...                 ],
    ...             },
    ...             "FiberPhotometryResponseSeries": [
    ...                 {
    ...                     "name": "calcium_signal_dms",
    ...                     "description": "GCaMP7b fluorescence from DMS.",
    ...                     "stream_name": "BBC300_ROISignals_Series0001_CAM1EXC1_ROI01",
    ...                     "unit": "a.u.",
    ...                     "fiber_photometry_table_region": [0],
    ...                     "fiber_photometry_table_region_description": "DMS fiber photometry row.",
    ...                 }
    ...             ],
    ...         }
    ...     }
    ... }


Convert Doric Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert Doric Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.doric.doricfiberphotometrydatainterface.DoricFiberPhotometryInterface`.
Each interface writes a single ``FiberPhotometryResponseSeries``, assembled from one or more input
streams; the ``metadata_key`` in the example above (``"calcium_signal_dms"``) must match the
``metadata_key`` passed to the interface below, so combine multiple interfaces (with distinct
``metadata_key`` values) in a converter to write several series sharing one ``FiberPhotometryTable``.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update

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
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

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

    The ``.doric`` HDF5 export embeds a session start time (read from the file's ``Created``
    attribute) that is set automatically in ``get_metadata()``. The ``.csv`` export does not embed
    one, so ``metadata["NWBFile"]["session_start_time"]`` must always be set by hand when converting
    from CSV.

.. seealso::

    :ref:`fiber_photometry_metadata_structure` for the full metadata format reference shared by all
    single-series fiber photometry interfaces.
