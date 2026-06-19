CSV Fiber Photometry data conversion
------------------------------------

Install NeuroConv with the additional dependencies necessary for reading CSV Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[csv_fp]"

GuPPy can read raw fiber photometry recordings stored as CSV files, with one CSV per stream
(e.g. a signal channel and an isosbestic control channel). Each data CSV has three columns --
``timestamps``, ``data``, and ``sampling_rate`` -- and is named after its stream
(``<stream_name>.csv``).

Specify the minimal metadata required for the conversion.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

  >>> fiber_photometry_metadata = {
  ...     "Ophys": {
  ...         "FiberPhotometry": {
  ...             "OpticalFiberModels": [
  ...                 {
  ...                     "name": "optical_fiber_model",
  ...                     "manufacturer": "Doric Lenses",
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
  ...                     "manufacturer": "Doric Lenses",
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
  ...                     "manufacturer": "Doric Lenses",
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
  ...                         "excitation_wavelength_in_nm": 465.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_calcium_signal",
  ...                         "photodetector": "photodetector"
  ...                     },
  ...                     {
  ...                         "name": "1",
  ...                         "location": "region",
  ...                         "excitation_wavelength_in_nm": 405.0,
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
  ...                     "stream_name": "Sample_Signal_Channel",
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [0],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the calcium signal."
  ...                 },
  ...                 {
  ...                     "name": "isosbestic_control",
  ...                     "description": "The fluorescence from the isosbestic control channel.",
  ...                     "stream_name": "Sample_Control_Channel",
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [1],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the isosbestic control."
  ...                 }
  ...             ]
  ...         }
  ...     }
  ... }


Convert CSV Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert CSV Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.csv_fp.csvfiberphotometrydatainterface.CSVFiberPhotometryInterface`.

CSV recordings carry no embedded recording-start timestamp, so ``session_start_time`` must be
supplied explicitly in the metadata.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import CSVFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "CSV" / "sample_data_csv_1"
    >>> LOCAL_PATH = Path(".") # Path to neuroconv

    >>> interface = CSVFiberPhotometryInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> # CSV recordings have no embedded start time, so it must be set explicitly.
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> # Add subject information (required for DANDI upload)
    >>> metadata["Subject"] = dict(subject_id="subject1", species="Mus musculus", sex="M", age="P30D")
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # stub_test=True writes only a short stub of each trace for a fast example conversion
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, stub_test=True, overwrite=True)
