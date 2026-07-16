TDT Fiber Photometry + GuPPy data conversion
--------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading a `GuPPy <https://github.com/LernerLab/GuPPy>`_ session recorded with `Tucker-Davis Technologies (TDT) <https://www.tdt.com/>`_ hardware.

.. code-block:: bash

    pip install "neuroconv[guppy_tdt]"

The :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter` bundles the three parts of a GuPPy session into a single NWB file: the raw TDT acquisition traces, the raw discrete TDT events that GuPPy processed, and the GuPPy-derived products (ΔF/F and z-score traces, transient tables, PSTHs, peak/AUCs, and cross-correlations). GuPPy and TDT share the recording-start clock, so no cross-system re-alignment is needed.

Specify the minimal metadata required for the conversion.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The converter discovers the acquisition channels from the GuPPy ``storesList.csv`` -- each recording site contributes its ``signal`` and ``control`` store -- and builds one raw ``FiberPhotometryResponseSeries`` (and one ``FiberPhotometryTable`` row) per store, keyed by ``<recording_site>_<role>`` (here ``dms_signal``/``dms_control`` and ``dls_signal``/``dls_control``). The GuPPy-derived traces reference each recording site's ``FiberPhotometryTable`` rows through the ``GuppyRecordingSitesTable`` registry. ``converter.get_metadata()`` returns a runnable scaffold with placeholder values; fill in the real optical hardware, indicator, and per-row location/wavelengths by row key (they must match the keys above), and ``run_conversion`` warns about any placeholder left behind.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "DeviceModels": {
    ...         "optical_fiber_model": {"manufacturer": "Doric Lenses", "numerical_aperture": 0.48},
    ...         "excitation_source_model": {"manufacturer": "Doric Lenses", "source_type": "LED", "excitation_mode": "one-photon"},
    ...         "photodetector_model": {"manufacturer": "Doric Lenses", "detector_type": "photodiode"},
    ...     },
    ...     "FiberPhotometry": {
    ...         "FiberPhotometryIndicators": {
    ...             "indicator": {"label": "GCaMP7b", "description": "GCaMP7b calcium indicator."},
    ...         },
    ...         "FiberPhotometryTable": {
    ...             "description": "Fiber photometry acquisition table for the dual-recording-site GuPPy session.",
    ...             "rows": {
    ...                 "dms_signal": {"location": "DMS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0},
    ...                 "dms_control": {"location": "DMS", "excitation_wavelength_in_nm": 405.0, "emission_wavelength_in_nm": 525.0},
    ...                 "dls_signal": {"location": "DLS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0},
    ...                 "dls_control": {"location": "DLS", "excitation_wavelength_in_nm": 405.0, "emission_wavelength_in_nm": 525.0},
    ...             },
    ...         },
    ...     },
    ... }

Convert TDT Fiber Photometry + GuPPy data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert a full GuPPy session to NWB using :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter`.
The ``session_start_time`` is read from the TDT tank, and the converter auto-derives the link from each GuPPy recording site to its fiber photometry table rows.

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
