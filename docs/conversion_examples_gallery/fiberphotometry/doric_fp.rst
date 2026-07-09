Doric Fiber Photometry data conversion
---------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Doric Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[doric_fp]"

Discover available signal streams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Streams are auto-discovered from the ``.doric`` HDF5 file by walking ``DataAcquisition``
for groups that contain a ``Time`` sibling dataset.  Each non-``Time`` 1-D dataset becomes a stream
whose name is built from its HDF5 path (relative to ``DataAcquisition``) with ``/`` replaced by ``_``.
Call :py:meth:`~neuroconv.datainterfaces.DoricFiberPhotometryInterface.get_available_streams` (callable
before construction) to discover stream names.

.. code-block:: python

    >>> from pathlib import Path
    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"
    >>> available_streams = DoricFiberPhotometryInterface.get_available_streams(file_path=file_path)

Specify the minimal metadata required for the conversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All hardware metadata must be supplied by the user — this interface does not inject hardware defaults.
Shared containers (device models, devices, indicators, and the table) are dicts keyed by an arbitrary
``metadata_key`` handle; entries reference each other with ``_metadata_key`` fields. See
:ref:`fiber_photometry_metadata_structure` for the full format reference.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "FiberPhotometry": {
    ...         "OpticalFiberModels": {
    ...             "ofm": {
    ...                 "name": "optical_fiber_model",
    ...                 "manufacturer": "Doric Lenses",
    ...                 "numerical_aperture": 0.48,
    ...                 "core_diameter_in_um": 400.0,
    ...             }
    ...         },
    ...         "OpticalFibers": {
    ...             "fiber_dms": {
    ...                 "name": "optical_fiber",
    ...                 "model_metadata_key": "ofm",
    ...                 "fiber_insertion": {"depth_in_mm": 2.8},
    ...             }
    ...         },
    ...         "ExcitationSourceModels": {
    ...             "esm": {
    ...                 "name": "excitation_source_model",
    ...                 "manufacturer": "Doric Lenses",
    ...                 "source_type": "LED",
    ...                 "excitation_mode": "one-photon",
    ...             }
    ...         },
    ...         "ExcitationSources": {
    ...             "led_465": {
    ...                 "name": "excitation_source_465nm",
    ...                 "model_metadata_key": "esm",
    ...             }
    ...         },
    ...         "PhotodetectorModels": {
    ...             "pdm": {
    ...                 "name": "photodetector_model",
    ...                 "manufacturer": "Doric Lenses",
    ...                 "detector_type": "photodiode",
    ...             }
    ...         },
    ...         "Photodetectors": {
    ...             "pd": {
    ...                 "name": "photodetector",
    ...                 "model_metadata_key": "pdm",
    ...             }
    ...         },
    ...         "FiberPhotometryIndicators": {
    ...             "gcamp": {
    ...                 "name": "green_fluorophore",
    ...                 "description": "GCaMP7b calcium indicator.",
    ...                 "label": "GCaMP7b",
    ...             }
    ...         },
    ...         "FiberPhotometryTable": {
    ...             "name": "fiber_photometry_table",
    ...             "description": "Fiber photometry system metadata.",
    ...             "rows": {
    ...                 "dms_465": {
    ...                     "location": "DMS",
    ...                     "excitation_wavelength_in_nm": 465.0,
    ...                     "emission_wavelength_in_nm": 525.0,
    ...                     "indicator_metadata_key": "gcamp",
    ...                     "optical_fiber_metadata_key": "fiber_dms",
    ...                     "excitation_source_metadata_key": "led_465",
    ...                     "photodetector_metadata_key": "pd",
    ...                 }
    ...             },
    ...         },
    ...         "calcium_signal_dms": {
    ...             "name": "calcium_signal_dms",
    ...             "description": "GCaMP7b fluorescence from DMS.",
    ...             "unit": "a.u.",
    ...             "fiber_photometry_table_region": ["dms_465"],
    ...             "fiber_photometry_table_region_description": "DMS fiber photometry row.",
    ...         },
    ...     }
    ... }


Convert Doric Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert Doric Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.fiber_photometry.doric.doricfiberphotometrydatainterface.DoricFiberPhotometryInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import DoricFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update

    >>> file_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "doric" / "BBC300_Acq_0093_stub.doric"

    >>> # Each interface writes a single FiberPhotometryResponseSeries, assembled from one or more input
    >>> # streams. Combine multiple interfaces (with distinct metadata_key values) in a converter to
    >>> # share one FiberPhotometryTable.
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

.. seealso::

    :ref:`fiber_photometry_metadata_structure` for the full metadata format reference shared by all
    single-series fiber photometry interfaces.
