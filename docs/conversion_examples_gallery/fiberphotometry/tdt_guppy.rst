TDT Fiber Photometry + GuPPy data conversion
--------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading a `GuPPy <https://github.com/LernerLab/GuPPy>`_ session recorded with `Tucker-Davis Technologies (TDT) <https://www.tdt.com/>`_ hardware.

.. code-block:: bash

    pip install "neuroconv[tdt_guppy]"

The :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter` bundles the three parts of a GuPPy session into a single NWB file: the raw TDT acquisition traces, the raw discrete TDT events that GuPPy processed, and the GuPPy-derived products (ΔF/F and z-score traces, transient tables, PSTHs, peak/AUCs, and cross-correlations). GuPPy and TDT share the recording-start clock, so no cross-system re-alignment is needed.

Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The converter discovers the acquisition channels from the GuPPy ``storesList.csv`` -- each recording site contributes its ``signal`` and ``control`` store -- and writes one raw ``FiberPhotometryResponseSeries`` per store under the metadata key ``<recording_site>_<role>`` (here ``dms_signal``/``dms_control`` and ``dls_signal``/``dls_control``).

As with every fiber photometry interface, the provenance chain (devices, indicator, the ``FiberPhotometryTable`` and its rows) is yours to supply -- nothing is fabricated from the source files. Give each acquisition series a ``fiber_photometry_table_region`` naming the table row it was recorded on; the converter reads those regions to link each GuPPy recording site to its acquisition fibers through the ``GuppyRecordingSitesTable`` registry. See :ref:`fiber_photometry_metadata_structure` for the full format.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "DeviceModels": {
    ...         "optical_fiber_model": {
    ...             "type": "OpticalFiberModel",
    ...             "name": "optical_fiber_model",
    ...             "manufacturer": "Doric Lenses",
    ...             "numerical_aperture": 0.48,
    ...         },
    ...         "excitation_source_model": {
    ...             "type": "ExcitationSourceModel",
    ...             "name": "excitation_source_model",
    ...             "manufacturer": "Doric Lenses",
    ...             "source_type": "LED",
    ...             "excitation_mode": "one-photon",
    ...         },
    ...         "photodetector_model": {
    ...             "type": "PhotodetectorModel",
    ...             "name": "photodetector_model",
    ...             "manufacturer": "Doric Lenses",
    ...             "detector_type": "photodiode",
    ...         },
    ...     },
    ...     "Devices": {
    ...         "optical_fiber_dms": {
    ...             "type": "OpticalFiber",
    ...             "name": "optical_fiber_dms",
    ...             "device_model_metadata_key": "optical_fiber_model",
    ...             "fiber_insertion": {"depth_in_mm": 2.8, "insertion_position_ap_in_mm": 0.8},
    ...         },
    ...         "optical_fiber_dls": {
    ...             "type": "OpticalFiber",
    ...             "name": "optical_fiber_dls",
    ...             "device_model_metadata_key": "optical_fiber_model",
    ...             "fiber_insertion": {"depth_in_mm": 3.5, "insertion_position_ap_in_mm": 0.1},
    ...         },
    ...         "excitation_source_465": {
    ...             "type": "ExcitationSource",
    ...             "name": "excitation_source_465",
    ...             "device_model_metadata_key": "excitation_source_model",
    ...         },
    ...         "excitation_source_405": {
    ...             "type": "ExcitationSource",
    ...             "name": "excitation_source_405",
    ...             "device_model_metadata_key": "excitation_source_model",
    ...         },
    ...         "photodetector": {
    ...             "type": "Photodetector",
    ...             "name": "photodetector",
    ...             "device_model_metadata_key": "photodetector_model",
    ...         },
    ...     },
    ...     "FiberPhotometry": {
    ...         "FiberPhotometryIndicators": {
    ...             "gcamp": {"name": "gcamp", "label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
    ...         },
    ...         "FiberPhotometryTable": {
    ...             "name": "fiber_photometry_table",
    ...             "description": "Fiber photometry acquisition table for the dual-recording-site GuPPy session.",
    ...             "rows": {
    ...                 "dms_signal": {
    ...                     "location": "DMS",
    ...                     "excitation_wavelength_in_nm": 465.0,
    ...                     "emission_wavelength_in_nm": 525.0,
    ...                     "indicator_metadata_key": "gcamp",
    ...                     "optical_fiber_metadata_key": "optical_fiber_dms",
    ...                     "excitation_source_metadata_key": "excitation_source_465",
    ...                     "photodetector_metadata_key": "photodetector",
    ...                 },
    ...                 "dms_control": {
    ...                     "location": "DMS",
    ...                     "excitation_wavelength_in_nm": 405.0,
    ...                     "emission_wavelength_in_nm": 525.0,
    ...                     "indicator_metadata_key": "gcamp",
    ...                     "optical_fiber_metadata_key": "optical_fiber_dms",
    ...                     "excitation_source_metadata_key": "excitation_source_405",
    ...                     "photodetector_metadata_key": "photodetector",
    ...                 },
    ...                 "dls_signal": {
    ...                     "location": "DLS",
    ...                     "excitation_wavelength_in_nm": 465.0,
    ...                     "emission_wavelength_in_nm": 525.0,
    ...                     "indicator_metadata_key": "gcamp",
    ...                     "optical_fiber_metadata_key": "optical_fiber_dls",
    ...                     "excitation_source_metadata_key": "excitation_source_465",
    ...                     "photodetector_metadata_key": "photodetector",
    ...                 },
    ...                 "dls_control": {
    ...                     "location": "DLS",
    ...                     "excitation_wavelength_in_nm": 405.0,
    ...                     "emission_wavelength_in_nm": 525.0,
    ...                     "indicator_metadata_key": "gcamp",
    ...                     "optical_fiber_metadata_key": "optical_fiber_dls",
    ...                     "excitation_source_metadata_key": "excitation_source_405",
    ...                     "photodetector_metadata_key": "photodetector",
    ...                 },
    ...             },
    ...         },
    ...         # Each acquisition series points at the table row it was recorded on.
    ...         "dms_signal": {"fiber_photometry_table_region": ["dms_signal"]},
    ...         "dms_control": {"fiber_photometry_table_region": ["dms_control"]},
    ...         "dls_signal": {"fiber_photometry_table_region": ["dls_signal"]},
    ...         "dls_control": {"fiber_photometry_table_region": ["dls_control"]},
    ...     },
    ... }

Convert TDT Fiber Photometry + GuPPy data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert a full GuPPy session to NWB using :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter`.
The ``session_start_time`` is read from the TDT tank, and the converter links each GuPPy recording site to its fiber photometry table rows.

.. code-block:: python

    >>> from neuroconv.converters import TDTFiberPhotometryGuppyConverter
    >>> from neuroconv.utils import dict_deep_update

    >>> tdt_folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_63_207-181030-103332"
    >>> guppy_folder_path = tdt_folder_path / "Photo_63_207-181030-103332_output_1"

    >>> converter = TDTFiberPhotometryGuppyConverter(tdt_folder_path=tdt_folder_path, guppy_folder_path=guppy_folder_path, verbose=False)

    >>> # Extract what metadata we can from the source files, then merge in the hardware metadata
    >>> metadata = converter.get_metadata()
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")

    >>> # Choose a path for saving the nwb file and run the conversion (stub_test writes a short stub of each trace)
    >>> converter.run_conversion(nwbfile_path=path_to_save_nwbfile, metadata=metadata, stub_test=True)

.. seealso::

    Other TDT data interfaces:

    - :doc:`tdt_fp` to convert raw TDT fiber photometry acquisition on its own.
    - :doc:`../events/tdt_events` to convert discrete TDT events (epocs such as port entries or nose pokes).
