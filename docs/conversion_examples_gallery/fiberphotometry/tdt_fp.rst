TDT Fiber Photometry data conversion
------------------------------------

Install NeuroConv with the additional dependencies necessary for reading TDT Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[tdt_fp]"

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
  ...             "DichroicMirrorModels": [
  ...                 {
  ...                     "name": "dichroic_mirror_model",
  ...                     "manufacturer": "Doric Lenses"
  ...                 }
  ...             ],
  ...             "DichroicMirrors": [
  ...                 {
  ...                     "name": "dichroic_mirror",
  ...                     "model": "dichroic_mirror_model"
  ...                 }
  ...             ],
  ...             "FiberPhotometryIndicators": [
  ...                 {
  ...                     "name": "dms_green_fluorophore",
  ...                     "description": "GCaMP7b indicator for DMS fiber photometry experiments.",
  ...                     "label": "GCaMP7b"
  ...                 }
  ...             ],
  ...             "FiberPhotometryTable": {
  ...                 "name": "fiber_photometry_table",
  ...                 "description": "Fiber photometry system metadata table.",
  ...                 "rows": [
  ...                     {
  ...                         "name": "0",
  ...                         "location": "DMS",
  ...                         "excitation_wavelength_in_nm": 465.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "dms_green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_calcium_signal",
  ...                         "photodetector": "photodetector",
  ...                         "dichroic_mirror": "dichroic_mirror"
  ...                     }
  ...                 ]
  ...             },
  ...             "FiberPhotometryResponseSeries": [
  ...                 {
  ...                     "name": "dms_calcium_signal",
  ...                     "description": "The fluorescence from the DMS calcium signal.",
  ...                     "stream_name": "Dv2A",
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [0],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DMS calcium signal."
  ...                 }
  ...             ]
  ...         }
  ...     }
  ... }


Convert TDT Fiber Photometry data to NWB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert TDT Fiber Photometry data to NWB using
:py:class:`~neuroconv.datainterfaces.ophys.tdt_fp.tdtfiberphotometrydatainterface.TDTFiberPhotometryInterface`.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import TDTFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"
    >>> LOCAL_PATH = Path(".") # Path to neuroconv

    >>> interface = TDTFiberPhotometryInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # t1 and t2 are optional arguments to specify the start and end times for the conversion
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, t1=0.0, t2=1.0)


Specifying Metadata
~~~~~~~~~~~~~~~~~~~

The example above shows how to convert TDT Fiber Photometry data without specifying all the metadata,
in which case the metadata will be automatically generated with default values.
To ensure that the NWB file is fully annotated, specify the metadata using the format described below.

.. code-block:: python

  >>> fiber_photometry_metadata = {
  ...     "Ophys": {
  ...         "FiberPhotometry": {
  ...             "OpticalFiberModels": [
  ...                 {
  ...                     "name": "optical_fiber_model",
  ...                     "description": "Fiber optic implant model specifications from Doric Lenses.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "Fiber Optic Implant",
  ...                     "numerical_aperture": 0.48,
  ...                     "core_diameter_in_um": 400.0
  ...                 }
  ...             ],
  ...             "OpticalFibers": [
  ...                 {
  ...                     "name": "optical_fiber",
  ...                     "description": "Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.",
  ...                     "model": "optical_fiber_model",
  ...                     "serial_number": "OF001",
  ...                     "fiber_insertion": {
  ...                         "depth_in_mm": 2.8,
  ...                         "insertion_position_ap_in_mm": 0.8,
  ...                         "insertion_position_ml_in_mm": 1.5,
  ...                         "insertion_position_dv_in_mm": 2.8,
  ...                         "position_reference": "bregma",
  ...                         "hemisphere": "right",
  ...                         "insertion_angle_pitch_in_deg": 0.0,
  ...                         "insertion_angle_yaw_in_deg": 0.0,
  ...                         "insertion_angle_roll_in_deg": 0.0
  ...                     }
  ...                 }
  ...             ],
  ...             "ExcitationSourceModels": [
  ...                 {
  ...                     "name": "excitation_source_model",
  ...                     "description": "Connectorized LED model specifications from Doric Lenses.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "Connectorized LED",
  ...                     "source_type": "LED",
  ...                     "excitation_mode": "one-photon",
  ...                     "wavelength_range_in_nm": [400.0, 470.0]
  ...                 }
  ...             ],
  ...             "ExcitationSources": [
  ...                 {
  ...                     "name": "excitation_source_calcium_signal",
  ...                     "description": "465nm LED modulated at different frequencies for DMS and DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
  ...                     "model": "excitation_source_model",
  ...                     "power_in_W": 0.001,
  ...                     "intensity_in_W_per_m2": 0.005,
  ...                     "exposure_time_in_s": 2.51e-13
  ...                 },
  ...                 {
  ...                     "name": "excitation_source_isosbestic_control",
  ...                     "description": "405nm LED modulated at different frequencies for DMS and DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
  ...                     "model": "excitation_source_model",
  ...                     "power_in_W": 0.001,
  ...                     "intensity_in_W_per_m2": 0.005,
  ...                     "exposure_time_in_s": 2.51e-13
  ...                 }
  ...             ],
  ...             "PhotodetectorModels": [
  ...                 {
  ...                     "name": "photodetector_model",
  ...                     "description": "Newport Visible Femtowatt Photoreceiver Module specifications.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "Newport Visible Femtowatt Photoreceiver Module",
  ...                     "detector_type": "photodiode",
  ...                     "wavelength_range_in_nm": [400.0, 700.0],
  ...                     "gain": 1.0e+10,
  ...                     "gain_unit": "V/W"
  ...                 }
  ...             ],
  ...             "Photodetectors": [
  ...                 {
  ...                     "name": "photodetector",
  ...                     "description": "This battery-operated photoreceiver has high gain and detects CW light signals in the sub-picowatt to nanowatt range. When used in conjunction with a modulated light source and a lock-in amplifier to reduce the measurement bandwidth, it achieves sensitivity levels in the femtowatt range. Doric offer this Newport product with add-on fiber optic adapter that improves coupling efficiency between the large core, high NA optical fibers used in Fiber Photometry and relatively small detector area. Its output analog voltage (0-5 V) can be monitored with an oscilloscope or with a DAQ board to record the data with a computer.",
  ...                     "model": "photodetector_model",
  ...                     "serial_number": "PD001"
  ...                 }
  ...             ],
  ...             "BandOpticalFilterModels": [
  ...                 {
  ...                     "name": "emission_filter_model",
  ...                     "description": "Emission bandpass filter model for GCaMP fluorescence detection.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "4 ports Fluorescence Mini Cube - GCaMP Emission Filter",
  ...                     "filter_type": "Bandpass",
  ...                     "center_wavelength_in_nm": 525.0,
  ...                     "bandwidth_in_nm": 50.0
  ...                 },
  ...                 {
  ...                     "name": "excitation_filter_model",
  ...                     "description": "Excitation bandpass filter model for 465nm light.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "4 ports Fluorescence Mini Cube - GCaMP Excitation Filter",
  ...                     "filter_type": "Bandpass",
  ...                     "center_wavelength_in_nm": 475.0,
  ...                     "bandwidth_in_nm": 30.0
  ...                 },
  ...                 {
  ...                     "name": "isosbestic_excitation_filter_model",
  ...                     "description": "Excitation bandpass filter model for 405nm light.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "4 ports Fluorescence Mini Cube - GCaMP Isosbestic Filter",
  ...                     "filter_type": "Bandpass",
  ...                     "center_wavelength_in_nm": 405.0,
  ...                     "bandwidth_in_nm": 10.0
  ...                 }
  ...             ],
  ...             "BandOpticalFilters": [
  ...                 {
  ...                     "name": "emission_filter",
  ...                     "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
  ...                     "model": "emission_filter_model"
  ...                 },
  ...                 {
  ...                     "name": "excitation_filter",
  ...                     "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
  ...                     "model": "excitation_filter_model"
  ...                 },
  ...                 {
  ...                     "name": "isosbestic_excitation_filter",
  ...                     "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
  ...                     "model": "isosbestic_excitation_filter_model"
  ...                 }
  ...             ],
  ...             "DichroicMirrorModels": [
  ...                 {
  ...                     "name": "dichroic_mirror_model",
  ...                     "description": "Dichroic mirror model specifications from Doric Lenses.",
  ...                     "manufacturer": "Doric Lenses",
  ...                     "model_number": "4 ports Fluorescence Mini Cube - GCaMP",
  ...                     "cut_on_wavelength_in_nm": 495.0,
  ...                     "reflection_band_in_nm": [400.0, 495.0],
  ...                     "transmission_band_in_nm": [505.0, 700.0],
  ...                     "angle_of_incidence_in_degrees": 45.0
  ...                 }
  ...             ],
  ...             "DichroicMirrors": [
  ...                 {
  ...                     "name": "dichroic_mirror",
  ...                     "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
  ...                     "model": "dichroic_mirror_model",
  ...                     "serial_number": "DM001"
  ...                 }
  ...             ],
  ...             "FiberPhotometryViruses": [
  ...                 {
  ...                     "name": "dms_virus",
  ...                     "description": "AAV5-CAG-FLEX-jGCaMP7b-WPRE viral vector used for DMS fiber photometry experiments.",
  ...                     "manufacturer": "Addgene",
  ...                     "construct_name": "AAV5-CAG-FLEX-jGCaMP7b-WPRE",
  ...                     "titer_in_vg_per_ml": 1.02e+13
  ...                 },
  ...                 {
  ...                     "name": "dls_virus",
  ...                     "description": "AAV5-CAG-FLEX-jGCaMP7b-WPRE viral vector used for DLS fiber photometry experiments.",
  ...                     "manufacturer": "Addgene",
  ...                     "construct_name": "AAV5-CAG-FLEX-jGCaMP7b-WPRE",
  ...                     "titer_in_vg_per_ml": 1.02e+13
  ...                 }
  ...             ],
  ...             "FiberPhotometryVirusInjections": [
  ...                 {
  ...                     "name": "dms_virus_injection",
  ...                     "description": "Viral injection into medial SNc for DMS fiber photometry experiments.",
  ...                     "viral_vector": "dms_virus",
  ...                     "location": "medial SNc",
  ...                     "hemisphere": "right",
  ...                     "reference": "bregma at the cortical surface",
  ...                     "ap_in_mm": -3.1,
  ...                     "ml_in_mm": 0.8,
  ...                     "dv_in_mm": -4.7,
  ...                     "volume_in_uL": 1.0
  ...                 },
  ...                 {
  ...                     "name": "dls_virus_injection",
  ...                     "description": "Viral injection into lateral SNc for DLS fiber photometry experiments.",
  ...                     "viral_vector": "dls_virus",
  ...                     "location": "lateral SNc",
  ...                     "hemisphere": "right",
  ...                     "reference": "bregma at the cortical surface",
  ...                     "ap_in_mm": -3.1,
  ...                     "ml_in_mm": 1.3,
  ...                     "dv_in_mm": -4.2,
  ...                     "volume_in_uL": 1.0
  ...                 }
  ...             ],
  ...             "FiberPhotometryIndicators": [
  ...                 {
  ...                     "name": "dms_green_fluorophore",
  ...                     "description": "GCaMP7b indicator for DMS fiber photometry experiments.",
  ...                     "manufacturer": "Addgene",
  ...                     "label": "GCaMP7b",
  ...                     "viral_vector_injection": "dms_virus_injection"
  ...                 },
  ...                 {
  ...                     "name": "dls_green_fluorophore",
  ...                     "description": "GCaMP7b indicator for DLS fiber photometry experiments.",
  ...                     "manufacturer": "Addgene",
  ...                     "label": "GCaMP7b",
  ...                     "viral_vector_injection": "dls_virus_injection"
  ...                 }
  ...             ],
  ...             "CommandedVoltageSeries": [
  ...                 {
  ...                     "name": "commanded_voltage_series_dms_calcium_signal",
  ...                     "description": "The commanded voltage for the DMS calcium signal.",
  ...                     "stream_name": "Fi1d",
  ...                     "index": 0,
  ...                     "unit": "volts",
  ...                     "frequency": 211.0
  ...                 },
  ...                 {
  ...                     "name": "commanded_voltage_series_dms_isosbestic_control",
  ...                     "description": "The commanded voltage for the DMS isosbestic control.",
  ...                     "stream_name": "Fi1d",
  ...                     "index": 1,
  ...                     "unit": "volts",
  ...                     "frequency": 330.0
  ...                 },
  ...                 {
  ...                     "name": "commanded_voltage_series_dls_calcium_signal",
  ...                     "description": "The commanded voltage for the DLS calcium signal.",
  ...                     "stream_name": "Fi1d",
  ...                     "index": 2,
  ...                     "unit": "volts",
  ...                     "frequency": 450.0
  ...                 },
  ...                 {
  ...                     "name": "commanded_voltage_series_dls_isosbestic_control",
  ...                     "description": "The commanded voltage for the DLS isosbestic control.",
  ...                     "stream_name": "Fi1d",
  ...                     "index": 3,
  ...                     "unit": "volts",
  ...                     "frequency": 270.0
  ...                 }
  ...             ],
  ...             "FiberPhotometryTable": {
  ...                 "name": "fiber_photometry_table",
  ...                 "description": "Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.",
  ...                 "rows": [
  ...                     {
  ...                         "name": "0",
  ...                         "location": "DMS",
  ...                         "excitation_wavelength_in_nm": 465.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "dms_green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_calcium_signal",
  ...                         "commanded_voltage_series": "commanded_voltage_series_dms_calcium_signal",
  ...                         "photodetector": "photodetector",
  ...                         "dichroic_mirror": "dichroic_mirror",
  ...                         "emission_filter": "emission_filter",
  ...                         "excitation_filter": "excitation_filter"
  ...                     },
  ...                     {
  ...                         "name": "1",
  ...                         "location": "DMS",
  ...                         "excitation_wavelength_in_nm": 405.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "dms_green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_isosbestic_control",
  ...                         "commanded_voltage_series": "commanded_voltage_series_dms_isosbestic_control",
  ...                         "photodetector": "photodetector",
  ...                         "dichroic_mirror": "dichroic_mirror",
  ...                         "emission_filter": "emission_filter",
  ...                         "excitation_filter": "isosbestic_excitation_filter"
  ...                     },
  ...                     {
  ...                         "name": "2",
  ...                         "location": "DLS",
  ...                         "excitation_wavelength_in_nm": 465.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "dls_green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_calcium_signal",
  ...                         "commanded_voltage_series": "commanded_voltage_series_dls_calcium_signal",
  ...                         "photodetector": "photodetector",
  ...                         "dichroic_mirror": "dichroic_mirror",
  ...                         "emission_filter": "emission_filter",
  ...                         "excitation_filter": "excitation_filter"
  ...                     },
  ...                     {
  ...                         "name": "3",
  ...                         "location": "DLS",
  ...                         "excitation_wavelength_in_nm": 405.0,
  ...                         "emission_wavelength_in_nm": 525.0,
  ...                         "indicator": "dls_green_fluorophore",
  ...                         "optical_fiber": "optical_fiber",
  ...                         "excitation_source": "excitation_source_isosbestic_control",
  ...                         "commanded_voltage_series": "commanded_voltage_series_dls_isosbestic_control",
  ...                         "photodetector": "photodetector",
  ...                         "dichroic_mirror": "dichroic_mirror",
  ...                         "emission_filter": "emission_filter",
  ...                         "excitation_filter": "isosbestic_excitation_filter"
  ...                     }
  ...                 ]
  ...             },
  ...             "FiberPhotometryResponseSeries": [
  ...                 {
  ...                     "name": "dms_calcium_signal",
  ...                     "description": "The fluorescence from the DMS calcium signal.",
  ...                     "stream_name": "Dv2A",
  ...                     "stream_indices": None,
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [0],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DMS calcium signal."
  ...                 },
  ...                 {
  ...                     "name": "dms_isosbestic_control",
  ...                     "description": "The fluorescence from the DMS isosbestic control.",
  ...                     "stream_name": "Dv1A",
  ...                     "stream_indices": None,
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [1],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DMS isosbestic control."
  ...                 },
  ...                 {
  ...                     "name": "dls_calcium_signal",
  ...                     "description": "The fluorescence from the DLS calcium signal.",
  ...                     "stream_name": "Dv4B",
  ...                     "stream_indices": None,
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [2],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DLS calcium signal."
  ...                 },
  ...                 {
  ...                     "name": "dls_isosbestic_control",
  ...                     "description": "The fluorescence from the DLS isosbestic control.",
  ...                     "stream_name": "Dv4B",
  ...                     "stream_indices": None,
  ...                     "unit": "a.u.",
  ...                     "fiber_photometry_table_region": [3],
  ...                     "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DLS isosbestic control."
  ...                 }
  ...             ]
  ...         }
  ...     }
  ... }

This metadata can then be easily incorporated into the conversion by updating the metadata dictionary as before.

.. code-block:: python

    >>> from datetime import datetime
    >>> from pathlib import Path
    >>> from zoneinfo import ZoneInfo

    >>> from neuroconv.datainterfaces import TDTFiberPhotometryInterface
    >>> from neuroconv.utils import dict_deep_update, load_dict_from_file

    >>> folder_path = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"
    >>> LOCAL_PATH = Path(".") # Path to neuroconv

    >>> interface = TDTFiberPhotometryInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> metadata = dict_deep_update(metadata, fiber_photometry_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # t1 and t2 are optional arguments to specify the start and end times for the conversion
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, t1=0.0, t2=1.0, overwrite=True)
