TDT Fiber Photometry data conversion
------------------------------------

Install NeuroConv with the additional dependencies necessary for reading TDT Fiber Photometry data.

.. code-block:: bash

    pip install "neuroconv[tdt_fp]"

Specify the metadata for the conversion.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    # fiber_photometry_metadata.yaml
    Ophys:
    FiberPhotometry:
        OpticalFibers:
        - name: optical_fiber
            description: Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.
            manufacturer: Doric Lenses
            model: Fiber Optic Implant
            numerical_aperture: 0.48
            core_diameter_in_um: 400.0
        ExcitationSources:
        - name: excitation_source_calcium_signal
            description: 465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.
            manufacturer: Doric Lenses
            model: Connectorized LED
            illumination_type: LED
            excitation_wavelength_in_nm: 465.0
        - name: excitation_source_isosbestic_control
            description: 465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.
            manufacturer: Doric Lenses
            model: Connectorized LED
            illumination_type: LED
            excitation_wavelength_in_nm: 405.0
        Photodetectors:
        - name: photodetector
            description: This battery-operated photoreceiver has high gain and detects CW light signals in the sub-picowatt to nanowatt range. When used in conjunction with a modulated light source and a lock-in amplifier to reduce the measurement bandwidth, it achieves sensitivity levels in the femtowatt range. Doric offer this Newport product with add-on fiber optic adapter that improves coupling efficiency between the large core, high NA optical fibers used in Fiber Photometry and relatively small detector area. Its output analog voltage (0-5 V) can be monitored with an oscilloscope or with a DAQ board to record the data with a computer.
            manufacturer: Doric Lenses
            model: Newport Visible Femtowatt Photoreceiver Module
            detector_type: photodiode
            detected_wavelength_in_nm: 525.0
            gain: 1.0e+10
        BandOpticalFilters:
        - name: emission_filter
            description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
            manufacturer: Doric Lenses
            model: 4 ports Fluorescence Mini Cube - GCaMP
            center_wavelength_in_nm: 525.0
            bandwidth_in_nm: 50.0
            filter_type: Bandpass
        - name: excitation_filter
            description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
            manufacturer: Doric Lenses
            model: 4 ports Fluorescence Mini Cube - GCaMP
            center_wavelength_in_nm: 475.0
            bandwidth_in_nm: 30.0
            filter_type: Bandpass
        - name: isosbestic_excitation_filter
            description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
            manufacturer: Doric Lenses
            model: 4 ports Fluorescence Mini Cube - GCaMP
            center_wavelength_in_nm: 405.0
            bandwidth_in_nm: 10.0
            filter_type: Bandpass
        DichroicMirrors:
        - name: dichroic_mirror
            description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
            manufacturer: Doric Lenses
            model: 4 ports Fluorescence Mini Cube - GCaMP
        Indicators:
        - name: dms_green_fluorophore
            description: Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.
            manufacturer: Addgene
            label: GCaMP7b
            injection_location: medial SNc
            injection_coordinates_in_mm: [3.1, 0.8, 4.7]
        - name: dls_green_fluorophore
            description: Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.
            manufacturer: Addgene
            label: GCaMP7b
            injection_location: lateral SNc
            injection_coordinates_in_mm: [3.1, 1.3, 4.2]
        CommandedVoltageSeries:
        - name: commanded_voltage_series_dms_calcium_signal
            description: The commanded voltage for the DMS calcium signal.
            stream_name: "Fi1d"
            index: 0
            unit: volts
            frequency: 211.0
        - name: commanded_voltage_series_dms_isosbestic_control
            description: The commanded voltage for the DMS isosbestic control.
            stream_name: "Fi1d"
            index: 1
            unit: volts
            frequency: 330.0
        - name: commanded_voltage_series_dls_calcium_signal
            description: The commanded voltage for the DLS calcium signal.
            stream_name: "Fi1d"
            index: 2
            unit: volts
            frequency: 450.0
        - name: commanded_voltage_series_dls_isosbestic_control
            description: The commanded voltage for the DLS isosbestic control.
            stream_name: "Fi1d"
            index: 3
            unit: volts
            frequency: 270.0
        FiberPhotometryTable:
        name: fiber_photometry_table
        description: Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.
        rows:
            - name: 0
            location: DMS
            coordinates: [0.8, 1.5, 2.8]
            commanded_voltage_series: commanded_voltage_series_dms_calcium_signal
            indicator: dms_green_fluorophore
            optical_fiber: optical_fiber
            excitation_source: excitation_source_calcium_signal
            photodetector: photodetector
            excitation_filter: excitation_filter
            emission_filter: emission_filter
            dichroic_mirror: dichroic_mirror
            - name: 1
            location: DMS
            coordinates: [0.8, 1.5, 2.8]
            commanded_voltage_series: commanded_voltage_series_dms_isosbestic_control
            indicator: dms_green_fluorophore
            optical_fiber: optical_fiber
            excitation_source: excitation_source_isosbestic_control
            photodetector: photodetector
            excitation_filter: isosbestic_excitation_filter
            emission_filter: emission_filter
            dichroic_mirror: dichroic_mirror
            - name: 2
            location: DLS
            coordinates: [0.1, 2.8, 3.5]
            commanded_voltage_series: commanded_voltage_series_dls_calcium_signal
            indicator: dls_green_fluorophore
            optical_fiber: optical_fiber
            excitation_source: excitation_source_calcium_signal
            photodetector: photodetector
            excitation_filter: excitation_filter
            emission_filter: emission_filter
            dichroic_mirror: dichroic_mirror
            - name: 3
            location: DLS
            coordinates: [0.1, 2.8, 3.5]
            commanded_voltage_series: commanded_voltage_series_dls_isosbestic_control
            indicator: dls_green_fluorophore
            optical_fiber: optical_fiber
            excitation_source: excitation_source_isosbestic_control
            photodetector: photodetector
            excitation_filter: isosbestic_excitation_filter
            emission_filter: emission_filter
            dichroic_mirror: dichroic_mirror
        FiberPhotometryResponseSeries:
        - name: dms_calcium_signal
            description: The fluorescence from the DMS calcium signal.
            stream_name: Dv2A
            stream_indices: null
            unit: a.u.
            fiber_photometry_table_region: [0]
            fiber_photometry_table_region_description: The region of the FiberPhotometryTable corresponding to the DMS calcium signal.
        - name: dms_isosbestic_control
            description: The fluorescence from the DMS isosbestic control.
            stream_name: Dv1A
            stream_indices: null
            unit: a.u.
            fiber_photometry_table_region: [1]
            fiber_photometry_table_region_description: The region of the FiberPhotometryTable corresponding to the DMS isosbestic control.
        - name: dls_calcium_signal
            description: The fluorescence from the DLS calcium signal.
            stream_name: Dv4B
            stream_indices: null
            unit: a.u.
            fiber_photometry_table_region: [2]
            fiber_photometry_table_region_description: The region of the FiberPhotometryTable corresponding to the DLS calcium signal.
        - name: dls_isosbestic_control
            description: The fluorescence from the DLS isosbestic control.
            stream_name: Dv4B
            stream_indices: null
            unit: a.u.
            fiber_photometry_table_region: [3]
            fiber_photometry_table_region_description: The region of the FiberPhotometryTable corresponding to the DLS isosbestic control.



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
    >>> editable_metadata_path = LOCAL_PATH / "tests" / "test_on_data" / "ophys" / "fiber_photometry_metadata.yaml"

    >>> interface = TDTFiberPhotometryInterface(folder_path=folder_path, verbose=False)
    >>> metadata = interface.get_metadata()
    >>> metadata["NWBFile"]["session_start_time"] = datetime.now(tz=ZoneInfo("US/Pacific"))
    >>> editable_metadata = load_dict_from_file(editable_metadata_path)
    >>> metadata = dict_deep_update(metadata, editable_metadata)

    >>> # Choose a path for saving the nwb file and run the conversion
    >>> nwbfile_path =  f"{path_to_save_nwbfile}"
    >>> # t1 and t2 are optional arguments to specify the start and end times for the conversion
    >>> interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, t1=0.0, t2=1.0)
