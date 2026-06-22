Legacy Neurophotometrics (NPM) Fiber Photometry data conversion
---------------------------------------------------------------

Install NeuroConv with the additional dependencies necessary for reading Neurophotometrics (NPM)
Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[npm_fp]"

The legacy NPM format is a raw, **header-less** acquisition CSV: the first column is the timestamp
(in milliseconds) and the remaining columns are region-of-interest values, with the interleaved
channels stored in a fixed row-cycling order (row ``i`` belongs to channel ``i %
number_of_channels``). This interface demultiplexes the raw file in memory into per-channel streams
named ``file{i}_chev{j}`` (isosbestic) and ``file{i}_chod{j}``/``file{i}_chpr{j}`` (signal
channels), where ``i`` indexes the source file and ``j`` indexes the region column. For the modern
header-bearing NPM format (with a ``Flags``/``LedState`` column), use
``NPMFiberPhotometryInterface`` instead.

Specify the minimal metadata required for the conversion.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

  >>> fiber_photometry_metadata = {
  ...     "Ophys": {
  ...         "FiberPhotometry": {
  ...             "OpticalFiberModels": [
  ...                 {
  ...                     "name": "optical_fiber_model",
  ...                     "manufacturer": "Neurophotometrics",
  ...                     "numerical_aperture": 0.48
  ...                 }
  ...             ],
  ...             "OpticalFibers": [
  ...                 {
  ...                     "name": "optical_fiber",
  ...                     "model": "optical_fiber_model",
  ...                     "fiber_insertion": {
  ...                         "depth_in_mm": 2.8
  ...                     }
  ...                 }
  ...             ],
  ...             "ExcitationSourceModels": [
  ...                 {
  ...                     "name": "excitation_source_model",
  ...                     "manufacturer": "Neurophotometrics",
  ...                     "source_type": "LED",
  ...                     "excitation_mode": "one-photon"
  ...                 }
  ...             ],
  ...             "ExcitationSources": [
  ...                 {
  ...                     "name": "excitation_source_calcium_signal",
  ...                     "model": "excitation_source_model"
  ...                 },
  ...                 {
  ...                     "name": "excitation_source_isosbestic_control",
  ...                     "model": "excitation_source_model"
  ...                 }
  ...             ],
  ...             "PhotodetectorModels": [
  ...                 {
  ...                     "name": "photodetector_model",
  ...                     "manufacturer": "Neurophotometrics",
  ...                     "detector_type": "photodiode"
  ...                 }
  ...             ],
  ...             "Photodetectors": [
  ...                 {
  ...                     "name": "photodetector",
  ...                     "model": "photodetector_model"
  ...                 }
  ...             ],
  ...             "FiberPhotometryIndicators": [
  ...                 {
  ...                     "name": "green_fluorophore",
  ...                     "description": "GCaMP7b indicator for fiber photometry experiments.",
  ...                     "label": "GCaMP7b"
  ...                 }
  ...             ],
  ...             "FiberPhotometryTable": {
  ...                 "name": "fiber_photometry_table",
  ...                 "description": "Fiber photometry system metadata table.",
  ...                 "rows": [
  ...                     {
  ...                         "name": "0",
  ...                         "location": "region",
  ...                         "excitation_wavelength_in_nm": 470.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_calcium_signal",
  ...                         "photodetector": "photodetector"
  ...                     },
  ...                     {
  ...                         "name": "1",
  ...                         "location": "region",
  ...                         "excitation_wavelength_in_nm": 415.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_isosbestic_control",
  ...                         "photodetector": "photodetector"
  ...                     }
  ...                 ]
  ...             },
  ...             "FiberPhotometryResponseSeries": [
  ...                 {
  ...                     "name": "calcium_signal",
  ...                     "description": "The fluorescence from the calcium-dependent signal channel.",
  ...                     "stream_name": "file0_chod1",
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [0],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the calcium signal."
  ...                 },
  ...                 {
  ...                     "name": "isosbestic_control",
  ...                     "description": "The fluorescence from the isosbestic control channel.",
  ...                     "stream_name": "file0_chev1",
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [1],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the isosbestic control."
  ...                 }
  ...             ]
  ...         }
  ...     }
  ... }


Convert legacy NPM Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert legacy NPM Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.npm_fp.npmfiberphotometrydatainterface.NPMLegacyFiberPhotometryInterface`.

NPM recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import NPMLegacyFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "sampleData_NPM_5"
    >>> LOCAL_PATH = Path(".") # Path to neuroconv

    >>> # number_of_channels (rows cycle through the channels in order) and time_unit are required:
    >>> # the header-less legacy format gives no way to infer them.
    >>> interface = NPMLegacyFiberPhotometryInterface(
    ...     folder_path=folder_path, number_of_channels=2, time_unit="milliseconds", verbose=False
    ... )
    >>> metadata = interface.get_metadata()
    >>> # NPM recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # stub_test=True writes only a short stub of each trace for a fast example conversion
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, stub_test=True, overwrite=True)
