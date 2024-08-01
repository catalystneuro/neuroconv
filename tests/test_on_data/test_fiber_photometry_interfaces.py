from datetime import datetime
from pathlib import Path

import numpy as np
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    TDTFiberPhotometryInterfaceMixin,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file

try:
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OUTPUT_PATH

# metadata.yaml
# Ophys:
#   FiberPhotometry:
#     OpticalFibers:
#       - name: optical_fiber
#         description: Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.
#         manufacturer: Doric Lenses
#         model: Fiber Optic Implant
#         numerical_aperture: 0.48
#         core_diameter_in_um: 400.0
#     ExcitationSources:
#       - name: excitation_source_calcium_signal
#         description: 465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.
#         manufacturer: Doric Lenses
#         model: Connectorized LED
#         illumination_type: LED
#         excitation_wavelength_in_nm: 465.0
#       - name: excitation_source_isosbestic_control
#         description: 465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.
#         manufacturer: Doric Lenses
#         model: Connectorized LED
#         illumination_type: LED
#         excitation_wavelength_in_nm: 405.0
#     Photodetectors:
#       - name: photodetector
#         description: This battery-operated photoreceiver has high gain and detects CW light signals in the sub-picowatt to nanowatt range. When used in conjunction with a modulated light source and a lock-in amplifier to reduce the measurement bandwidth, it achieves sensitivity levels in the femtowatt range. Doric offer this Newport product with add-on fiber optic adapter that improves coupling efficiency between the large core, high NA optical fibers used in Fiber Photometry and relatively small detector area. Its output analog voltage (0-5 V) can be monitored with an oscilloscope or with a DAQ board to record the data with a computer.
#         manufacturer: Doric Lenses
#         model: Newport Visible Femtowatt Photoreceiver Module
#         detector_type: photodiode
#         detected_wavelength_in_nm: 525.0
#         gain: 1.0e+10
#     BandOpticalFilters:
#       - name: emission_filter
#         description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
#         manufacturer: Doric Lenses
#         model: 4 ports Fluorescence Mini Cube - GCaMP
#         center_wavelength_in_nm: 525.0
#         bandwidth_in_nm: 50.0
#         filter_type: Bandpass
#       - name: excitation_filter
#         description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
#         manufacturer: Doric Lenses
#         model: 4 ports Fluorescence Mini Cube - GCaMP
#         center_wavelength_in_nm: 475.0
#         bandwidth_in_nm: 30.0
#         filter_type: Bandpass
#       - name: isosbestic_excitation_filter
#         description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
#         manufacturer: Doric Lenses
#         model: 4 ports Fluorescence Mini Cube - GCaMP
#         center_wavelength_in_nm: 405.0
#         bandwidth_in_nm: 10.0
#         filter_type: Bandpass
#     DichroicMirrors:
#       - name: dichroic_mirror
#         description: "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum."
#         manufacturer: Doric Lenses
#         model: 4 ports Fluorescence Mini Cube - GCaMP
#     Indicators:
#       - name: dms_green_fluorophore
#         description: Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.
#         manufacturer: Addgene
#         label: GCaMP7b
#         injection_location: medial SNc
#         injection_coordinates_in_mm: [3.1, 0.8, 4.7]
#       - name: dls_green_fluorophore
#         description: Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.
#         manufacturer: Addgene
#         label: GCaMP7b
#         injection_location: lateral SNc
#         injection_coordinates_in_mm: [3.1, 1.3, 4.2]


class TestTDTFiberPhotometryInterface(TestCase, TDTFiberPhotometryInterfaceMixin):
    data_interface_cls = TDTFiberPhotometryInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "fiber_photometry_datasets" / "Photo_249_391-200721-120136_stubbed"),
    )
    conversion_options = dict(t2=1.0)
    save_directory = OUTPUT_PATH
    expected_session_start_time = datetime(2020, 7, 21, 10, 2, 24, 999999).isoformat()
    expected_devices = [
        {
            "name": "optical_fiber",
            "description": "Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.",
            "manufacturer": "Doric Lenses",
            "model": "Fiber Optic Implant",
            "numerical_aperture": 0.48,
            "core_diameter_in_um": 400.0,
        },
        {
            "name": "excitation_source_calcium_signal",
            "description": "465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
            "manufacturer": "Doric Lenses",
            "model": "Connectorized LED",
            "illumination_type": "LED",
            "excitation_wavelength_in_nm": 465.0,
        },
        {
            "name": "excitation_source_isosbestic_control",
            "description": "465nm and 405nm LEDs were modulated at 211 Hz and 330 Hz, respectively, for DMS probes. 465nm and 405nm LEDs were modulated at 450 Hz and 270 Hz, respectively for DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
            "manufacturer": "Doric Lenses",
            "model": "Connectorized LED",
            "illumination_type": "LED",
            "excitation_wavelength_in_nm": 405.0,
        },
        {
            "name": "photodetector",
            "description": "This battery-operated photoreceiver has high gain and detects CW light signals in the sub-picowatt to nanowatt range. When used in conjunction with a modulated light source and a lock-in amplifier to reduce the measurement bandwidth, it achieves sensitivity levels in the femtowatt range. Doric offer this Newport product with add-on fiber optic adapter that improves coupling efficiency between the large core, high NA optical fibers used in Fiber Photometry and relatively small detector area. Its output analog voltage (0-5 V) can be monitored with an oscilloscope or with a DAQ board to record the data with a computer.",
            "manufacturer": "Doric Lenses",
            "model": "Newport Visible Femtowatt Photoreceiver Module",
            "detector_type": "photodiode",
            "detected_wavelength_in_nm": 525.0,
            "gain": 1.0e10,
        },
        {
            "name": "emission_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
            "manufacturer": "Doric Lenses",
            "model": "4 ports Fluorescence Mini Cube - GCaMP",
            "center_wavelength_in_nm": 525.0,
            "bandwidth_in_nm": 50.0,
            "filter_type": "Bandpass",
        },
        {
            "name": "excitation_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
            "manufacturer": "Doric Lenses",
            "model": "4 ports Fluorescence Mini Cube - GCaMP",
            "center_wavelength_in_nm": 475.0,
            "bandwidth_in_nm": 30.0,
            "filter_type": "Bandpass",
        },
        {
            "name": "isosbestic_excitation_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
            "manufacturer": "Doric Lenses",
            "model": "4 ports Fluorescence Mini Cube - GCaMP",
            "center_wavelength_in_nm": 405.0,
            "bandwidth_in_nm": 10.0,
            "filter_type": "Bandpass",
        },
        {
            "name": "dichroic_mirror",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
            "manufacturer": "Doric Lenses",
            "model": "4 ports Fluorescence Mini Cube - GCaMP",
        },
        {
            "name": "dms_green_fluorophore",
            "description": "Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.",
            "manufacturer": "Addgene",
            "label": "GCaMP7b",
            "injection_location": "medial SNc",
            "injection_coordinates_in_mm": [3.1, 0.8, 4.7],
        },
        {
            "name": "dls_green_fluorophore",
            "description": "Mice for fiber photometry experiments received infusions of 1ml of AAV5-CAG-FLEX-jGCaMP7b-WPRE (1.02e13 vg/mL, Addgene, lot 18-429) into lateral SNc (AP 3.1, ML 1.3, DV 4.2) in one hemisphere and medial SNc (AP 3.1, ML 0.8, DV 4.7) in the other. Hemispheres were counterbalanced between mice.",
            "manufacturer": "Addgene",
            "label": "GCaMP7b",
            "injection_location": "lateral SNc",
            "injection_coordinates_in_mm": [3.1, 1.3, 4.2],
        },
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            for device_dict in self.expected_devices:
                expected_name = device_dict.pop("name")
                assert expected_name in nwbfile.devices
                device = nwbfile.devices[expected_name]
                for key, expected_value in device_dict.items():
                    if isinstance(expected_value, list):
                        np.testing.assert_equal(
                            getattr(device, key), expected_value
                        ), f"Device {expected_name} attribute {key} is {getattr(device, key)} but expected {expected_value}"
                    else:
                        assert (
                            getattr(device, key) == expected_value
                        ), f"Device {expected_name} attribute {key} is {getattr(device, key)} but expected {expected_value}"
            # for event_dict in self.expected_events:
            #     expected_name = event_dict["name"]
            #     expected_description = event_dict["description"]
            #     assert expected_name in nwbfile.processing["behavior"].data_interfaces
            #     event = nwbfile.processing["behavior"].data_interfaces[expected_name]
            #     assert event.description == expected_description

            # for interval_dict in self.expected_interval_series:
            #     expected_name = interval_dict["name"]
            #     expected_description = interval_dict["description"]
            #     assert expected_name in nwbfile.processing["behavior"]["behavioral_epochs"].interval_series
            #     interval_series = nwbfile.processing["behavior"]["behavioral_epochs"].interval_series[expected_name]
            #     assert interval_series.description == expected_description

    def test_all_conversion_checks(self):
        metadata_file_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        editable_metadata = load_dict_from_file(metadata_file_path)
        metadata = self.data_interface_cls(**self.interface_kwargs).get_metadata()
        metadata = dict_deep_update(metadata, editable_metadata)

        super().test_all_conversion_checks(metadata=metadata)
