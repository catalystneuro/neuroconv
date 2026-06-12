TDT Fiber Photometry + GuPPy data conversion
--------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading a `GuPPy <https://github.com/LernerLab/GuPPy>`_ session recorded with `Tucker-Davis Technologies (TDT) <https://www.tdt.com/>`_ hardware.

.. code-block:: bash

    pip install "neuroconv[guppy_tdt]"

The :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter` bundles the three parts of a GuPPy session into a single NWB file: the raw TDT acquisition traces, the raw discrete TDT events that GuPPy processed, and the GuPPy-derived products (ΔF/F and z-score traces, transient tables, PSTHs, peak/AUCs, and cross-correlations). GuPPy and TDT share the recording-start clock, so no cross-system re-alignment is needed.

Specify the minimal metadata required for the conversion.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The converter writes the GuPPy-derived traces as ``FiberPhotometryResponseSeries`` linked back into the acquisition ``FiberPhotometryTable``, so the table and the raw response series describe the optical hardware. Each response series ``stream_name`` is the TDT store name GuPPy processed (here ``Dv2A``/``Dv1A`` for DMS and ``Dv4B``/``Dv3B`` for DLS); the converter uses these to auto-link every GuPPy region to its table rows.

.. code-block:: python

    >>> fiber_photometry_metadata = {
    ...     "Ophys": {
    ...         "FiberPhotometry": {
    ...             "OpticalFiberModels": [
    ...                 {"name": "optical_fiber_model", "manufacturer": "Doric Lenses", "numerical_aperture": 0.48}
    ...             ],
    ...             "OpticalFibers": [
    ...                 {"name": "optical_fiber", "model": "optical_fiber_model", "fiber_insertion": {"depth_in_mm": 2.8}}
    ...             ],
    ...             "ExcitationSourceModels": [
    ...                 {"name": "excitation_source_model", "manufacturer": "Doric Lenses", "source_type": "LED", "excitation_mode": "one-photon"}
    ...             ],
    ...             "ExcitationSources": [
    ...                 {"name": "excitation_source_calcium_signal", "model": "excitation_source_model"},
    ...                 {"name": "excitation_source_isosbestic_control", "model": "excitation_source_model"}
    ...             ],
    ...             "PhotodetectorModels": [
    ...                 {"name": "photodetector_model", "manufacturer": "Doric Lenses", "detector_type": "photodiode"}
    ...             ],
    ...             "Photodetectors": [
    ...                 {"name": "photodetector", "model": "photodetector_model"}
    ...             ],
    ...             "DichroicMirrorModels": [
    ...                 {"name": "dichroic_mirror_model", "manufacturer": "Doric Lenses"}
    ...             ],
    ...             "DichroicMirrors": [
    ...                 {"name": "dichroic_mirror", "model": "dichroic_mirror_model"}
    ...             ],
    ...             "FiberPhotometryIndicators": [
    ...                 {"name": "dms_green_fluorophore", "description": "GCaMP7b indicator for the DMS recording.", "label": "GCaMP7b"},
    ...                 {"name": "dls_green_fluorophore", "description": "GCaMP7b indicator for the DLS recording.", "label": "GCaMP7b"}
    ...             ],
    ...             "FiberPhotometryTable": {
    ...                 "name": "fiber_photometry_table",
    ...                 "description": "Fiber photometry system metadata table.",
    ...                 "rows": [
    ...                     {"name": "0", "location": "DMS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0, "indicator": "dms_green_fluorophore", "optical_fiber": "optical_fiber", "excitation_source": "excitation_source_calcium_signal", "photodetector": "photodetector", "dichroic_mirror": "dichroic_mirror"},
    ...                     {"name": "1", "location": "DMS", "excitation_wavelength_in_nm": 405.0, "emission_wavelength_in_nm": 525.0, "indicator": "dms_green_fluorophore", "optical_fiber": "optical_fiber", "excitation_source": "excitation_source_isosbestic_control", "photodetector": "photodetector", "dichroic_mirror": "dichroic_mirror"},
    ...                     {"name": "2", "location": "DLS", "excitation_wavelength_in_nm": 465.0, "emission_wavelength_in_nm": 525.0, "indicator": "dls_green_fluorophore", "optical_fiber": "optical_fiber", "excitation_source": "excitation_source_calcium_signal", "photodetector": "photodetector", "dichroic_mirror": "dichroic_mirror"},
    ...                     {"name": "3", "location": "DLS", "excitation_wavelength_in_nm": 405.0, "emission_wavelength_in_nm": 525.0, "indicator": "dls_green_fluorophore", "optical_fiber": "optical_fiber", "excitation_source": "excitation_source_isosbestic_control", "photodetector": "photodetector", "dichroic_mirror": "dichroic_mirror"}
    ...                 ]
    ...             },
    ...             "FiberPhotometryResponseSeries": [
    ...                 {"name": "dms_calcium_signal", "description": "The fluorescence from the DMS calcium signal.", "stream_name": "Dv2A", "unit": "a.u.", "fiber_photometry_table_region": [0], "fiber_photometry_table_region_description": "The DMS calcium signal."},
    ...                 {"name": "dms_isosbestic_control", "description": "The fluorescence from the DMS isosbestic control.", "stream_name": "Dv1A", "unit": "a.u.", "fiber_photometry_table_region": [1], "fiber_photometry_table_region_description": "The DMS isosbestic control."},
    ...                 {"name": "dls_calcium_signal", "description": "The fluorescence from the DLS calcium signal.", "stream_name": "Dv4B", "unit": "a.u.", "fiber_photometry_table_region": [2], "fiber_photometry_table_region_description": "The DLS calcium signal."},
    ...                 {"name": "dls_isosbestic_control", "description": "The fluorescence from the DLS isosbestic control.", "stream_name": "Dv3B", "unit": "a.u.", "fiber_photometry_table_region": [3], "fiber_photometry_table_region_description": "The DLS isosbestic control."}
    ...             ]
    ...         }
    ...     }
    ... }

Convert TDT Fiber Photometry + GuPPy data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert a full GuPPy session to NWB using :py:class:`~neuroconv.converters.TDTFiberPhotometryGuppyConverter`.
The ``session_start_time`` is read from the TDT tank, and the converter auto-derives the link from each GuPPy region to its fiber photometry table rows.

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
