import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
from hdmf.testing import TestCase
from pynwb import NWBHDF5IO
from pytz import utc

from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.tools.testing.data_interface_mixins import (
    TDTFiberPhotometryInterfaceMixin,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OUTPUT_PATH

import pytest
from parameterized import parameterized


class TestTDTFiberPhotometryInterface(TestCase, TDTFiberPhotometryInterfaceMixin):
    data_interface_cls = TDTFiberPhotometryInterface
    interface_kwargs = dict(
        folder_path=str(OPHYS_DATA_PATH / "fiber_photometry_datasets" / "TDT" / "Photo_249_391-200721-120136_stubbed"),
    )
    conversion_options = dict(t2=1.0)
    save_directory = OUTPUT_PATH
    expected_session_start_time = datetime(2020, 7, 21, 17, 2, 24, 999999, tzinfo=utc).isoformat()
    expected_devices = [
        {
            "name": "optical_fiber",
            "description": "Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.",
            "serial_number": "OF001",
        },
        {
            "name": "excitation_source_calcium_signal",
            "description": "465nm LED modulated at different frequencies for DMS and DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
            "power_in_W": 0.001,
            "intensity_in_W_per_m2": 0.005,
            "exposure_time_in_s": 2.51e-13,
        },
        {
            "name": "excitation_source_isosbestic_control",
            "description": "405nm LED modulated at different frequencies for DMS and DLS probes. LED currents were adjusted in order to return a voltage between 150-200mV for each signal, were offset by 5 mA, were demodulated using a 4 Hz lowpass frequency filter.",
            "power_in_W": 0.001,
            "intensity_in_W_per_m2": 0.005,
            "exposure_time_in_s": 2.51e-13,
        },
        {
            "name": "photodetector",
            "description": "This battery-operated photoreceiver has high gain and detects CW light signals in the sub-picowatt to nanowatt range. When used in conjunction with a modulated light source and a lock-in amplifier to reduce the measurement bandwidth, it achieves sensitivity levels in the femtowatt range. Doric offer this Newport product with add-on fiber optic adapter that improves coupling efficiency between the large core, high NA optical fibers used in Fiber Photometry and relatively small detector area. Its output analog voltage (0-5 V) can be monitored with an oscilloscope or with a DAQ board to record the data with a computer.",
            "serial_number": "PD001",
        },
        {
            "name": "emission_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
        },
        {
            "name": "excitation_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
        },
        {
            "name": "isosbestic_excitation_filter",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
        },
        {
            "name": "dichroic_mirror",
            "description": "Dual excitation band fiber photometry measurements use a Fluorescence Mini Cube with 4 ports: one port for the functional fluorescence excitation light, one for the isosbestic excitation, one for the fluorescence detection, and one for the sample. The cube has dichroic mirrors to combine isosbestic and fluorescence excitations and separate the fluorescence emission and narrow bandpass filters limiting the excitation fluorescence spectrum.",
            "serial_number": "DM001",
        },
        # {
        #     "name": "dms_green_fluorophore",
        #     "description": "GCaMP7b indicator for DMS fiber photometry experiments.",
        #     "manufacturer": "Addgene",
        #     "label": "GCaMP7b",
        # },
        # {
        #     "name": "dls_green_fluorophore",
        #     "description": "GCaMP7b indicator for DLS fiber photometry experiments.",
        #     "manufacturer": "Addgene",
        #     "label": "GCaMP7b",
        # },
    ]
    expected_commanded_voltage_series = [
        {
            "name": "commanded_voltage_series_dms_calcium_signal",
            "description": "The commanded voltage for the DMS calcium signal.",
            "unit": "volts",
            "frequency": 211.0,
        },
        {
            "name": "commanded_voltage_series_dms_isosbestic_control",
            "description": "The commanded voltage for the DMS isosbestic control.",
            "unit": "volts",
            "frequency": 330.0,
        },
        {
            "name": "commanded_voltage_series_dls_calcium_signal",
            "description": "The commanded voltage for the DLS calcium signal.",
            "unit": "volts",
            "frequency": 450.0,
        },
        {
            "name": "commanded_voltage_series_dls_isosbestic_control",
            "description": "The commanded voltage for the DLS isosbestic control.",
            "unit": "volts",
            "frequency": 270.0,
        },
    ]
    expected_fiber_photometry_response_series = [
        {
            "name": "dms_calcium_signal",
            "description": "The fluorescence from the DMS calcium signal.",
            "unit": "a.u.",
            "fiber_photometry_table_region": [0],
            "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DMS calcium signal.",
        },
        {
            "name": "dms_isosbestic_control",
            "description": "The fluorescence from the DMS isosbestic control.",
            "unit": "a.u.",
            "fiber_photometry_table_region": [1],
            "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DMS isosbestic control.",
        },
        {
            "name": "dls_calcium_signal",
            "description": "The fluorescence from the DLS calcium signal.",
            "unit": "a.u.",
            "fiber_photometry_table_region": [2],
            "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DLS calcium signal.",
        },
        {
            "name": "dls_isosbestic_control",
            "description": "The fluorescence from the DLS isosbestic control.",
            "unit": "a.u.",
            "fiber_photometry_table_region": [3],
            "fiber_photometry_table_region_description": "The region of the FiberPhotometryTable corresponding to the DLS isosbestic control.",
        },
    ]
    expected_fiber_photometry_table = {
        "name": "fiber_photometry_table",
        "description": "Fiber optic implants (Doric Lenses; 400 um, 0.48 NA) were placed above DMS (AP 0.8, ML 1.5, DV 2.8) and DLS (AP 0.1, ML 2.8, DV 3.5). The DMS implant was placed in the hemisphere receiving a medial SNc viral injection, while the DLS implant was placed in the hemisphere receiving a lateral SNc viral injection. Calcium signals from dopamine terminals in DMS and DLS were recorded during RI30, on the first and last days of RI60/RR20 training as well as on both footshock probes for each mouse. All recordings were done using a fiber photometry rig with optical components from Doric lenses controlled by a real-time processor from Tucker Davis Technologies (TDT; RZ5P). TDT Synapse software was used for data acquisition.",
        "rows": [
            {
                "location": "DMS",
                "excitation_wavelength_in_nm": 465.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator": "dms_green_fluorophore",
                "optical_fiber": "optical_fiber",
                "excitation_source": "excitation_source_calcium_signal",
                "commanded_voltage_series": "commanded_voltage_series_dms_calcium_signal",
                "photodetector": "photodetector",
                "dichroic_mirror": "dichroic_mirror",
                "emission_filter": "emission_filter",
                "excitation_filter": "excitation_filter",
            },
            {
                "location": "DMS",
                "excitation_wavelength_in_nm": 405.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator": "dms_green_fluorophore",
                "optical_fiber": "optical_fiber",
                "excitation_source": "excitation_source_isosbestic_control",
                "commanded_voltage_series": "commanded_voltage_series_dms_isosbestic_control",
                "photodetector": "photodetector",
                "dichroic_mirror": "dichroic_mirror",
                "emission_filter": "emission_filter",
                "excitation_filter": "isosbestic_excitation_filter",
            },
            {
                "location": "DLS",
                "excitation_wavelength_in_nm": 465.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator": "dls_green_fluorophore",
                "optical_fiber": "optical_fiber",
                "excitation_source": "excitation_source_calcium_signal",
                "commanded_voltage_series": "commanded_voltage_series_dls_calcium_signal",
                "photodetector": "photodetector",
                "dichroic_mirror": "dichroic_mirror",
                "emission_filter": "emission_filter",
                "excitation_filter": "excitation_filter",
            },
            {
                "location": "DLS",
                "excitation_wavelength_in_nm": 405.0,
                "emission_wavelength_in_nm": 525.0,
                "indicator": "dls_green_fluorophore",
                "optical_fiber": "optical_fiber",
                "excitation_source": "excitation_source_isosbestic_control",
                "commanded_voltage_series": "commanded_voltage_series_dls_isosbestic_control",
                "photodetector": "photodetector",
                "dichroic_mirror": "dichroic_mirror",
                "emission_filter": "emission_filter",
                "excitation_filter": "isosbestic_excitation_filter",
            },
        ],
    }

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == self.expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):
        expected_devices = deepcopy(self.expected_devices)
        expected_commanded_voltage_series = deepcopy(self.expected_commanded_voltage_series)
        expected_fiber_photometry_response_series = deepcopy(self.expected_fiber_photometry_response_series)
        expected_fiber_photometry_table = deepcopy(self.expected_fiber_photometry_table)

        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            for device_dict in expected_devices:
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

            for cvs_dict in expected_commanded_voltage_series:
                expected_name = cvs_dict.pop("name")
                assert expected_name in nwbfile.acquisition
                cvs = nwbfile.acquisition[expected_name]
                for key, expected_value in cvs_dict.items():
                    assert (
                        getattr(cvs, key) == expected_value
                    ), f"CommandedVoltageSeries {expected_name} attribute {key} is {getattr(cvs, key)} but expected {expected_value}"

            for fp_dict in expected_fiber_photometry_response_series:
                expected_name = fp_dict.pop("name")
                assert expected_name in nwbfile.acquisition
                fp = nwbfile.acquisition[expected_name]
                assert (
                    fp.description == fp_dict["description"]
                ), f"FiberPhotometryResponseSeries {expected_name} description is {fp.description} but expected {fp_dict['description']}"
                assert (
                    fp.unit == fp_dict["unit"]
                ), f"FiberPhotometryResponseSeries {expected_name} unit is {fp.unit} but expected {fp_dict['unit']}"
                assert (
                    fp.fiber_photometry_table_region.data[:] == fp_dict["fiber_photometry_table_region"]
                ), f"FiberPhotometryResponseSeries {expected_name} region is {fp.fiber_photometry_table_region.data[:]} but expected {fp_dict['fiber_photometry_table_region']}"
                assert (
                    fp.fiber_photometry_table_region.description == fp_dict["fiber_photometry_table_region_description"]
                ), f"FiberPhotometryResponseSeries {expected_name} region description is {fp.fiber_photometry_table_region.description} but expected {fp_dict['fiber_photometry_table_region_description']}"

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert fiber_photometry_table.name == expected_fiber_photometry_table["name"]
            assert fiber_photometry_table.description == expected_fiber_photometry_table["description"]
            for i, row_dict in enumerate(expected_fiber_photometry_table["rows"]):
                expected_location = row_dict.pop("location")
                location_index = fiber_photometry_table.colnames.index("location")
                expected_excitation_wavelength = row_dict.pop("excitation_wavelength_in_nm")
                excitation_wavelength_index = fiber_photometry_table.colnames.index("excitation_wavelength_in_nm")
                expected_emission_wavelength = row_dict.pop("emission_wavelength_in_nm")
                emission_wavelength_index = fiber_photometry_table.colnames.index("emission_wavelength_in_nm")
                assert (
                    expected_location == fiber_photometry_table.columns[location_index][i]
                ), f"FiberPhotometryTable row {i} location is {fiber_photometry_table.columns['location'][i]} but expected {expected_location}"
                assert (
                    expected_excitation_wavelength == fiber_photometry_table.columns[excitation_wavelength_index][i]
                ), f"FiberPhotometryTable row {i} excitation_wavelength is {fiber_photometry_table.columns['excitation_wavelength_in_nm'][i]} but expected {expected_excitation_wavelength}"
                assert (
                    expected_emission_wavelength == fiber_photometry_table.columns[emission_wavelength_index][i]
                ), f"FiberPhotometryTable row {i} emission_wavelength is {fiber_photometry_table.columns['emission_wavelength_in_nm'][i]} but expected {expected_emission_wavelength}"
                for key, expected_value in row_dict.items():
                    key_index = fiber_photometry_table.colnames.index(key)
                    assert (
                        expected_value == fiber_photometry_table.columns[key_index].data[i].name
                    ), f"FiberPhotometryTable row {i} attribute {key} is {fiber_photometry_table.columns[key_index].data[i].name} but expected {expected_value}"

    @parameterized.expand(
        [
            ("timing_source_original", "original"),
            ("timing_source_timestamps", "aligned_timestamps"),
            ("timing_source_rate", "aligned_starting_time_and_rate"),
        ]
    )
    def test_all_conversion_checks(self, _, timing_source):
        metadata_file_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        editable_metadata = load_dict_from_file(metadata_file_path)
        metadata = self.data_interface_cls(**self.interface_kwargs).get_metadata()
        metadata = dict_deep_update(metadata, editable_metadata)

        self.conversion_options["timing_source"] = timing_source
        super().test_all_conversion_checks(metadata=metadata)

    def test_all_conversion_checks_stub_test(self):
        metadata_file_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        editable_metadata = load_dict_from_file(metadata_file_path)
        metadata = self.data_interface_cls(**self.interface_kwargs).get_metadata()
        metadata = dict_deep_update(metadata, editable_metadata)

        self.conversion_options["stub_test"] = True
        self.conversion_options["t2"] = 0.0
        super().test_all_conversion_checks(metadata=metadata)
        self.conversion_options["stub_test"] = False
        self.conversion_options["t2"] = 1.0

    def test_all_conversion_checks_stub_test_invalid(self):
        metadata_file_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        editable_metadata = load_dict_from_file(metadata_file_path)
        metadata = self.data_interface_cls(**self.interface_kwargs).get_metadata()
        metadata = dict_deep_update(metadata, editable_metadata)

        self.conversion_options["stub_test"] = True
        self.conversion_options["t2"] = 1.0
        error_message = re.escape(
            "stub_test cannot be used with a specified t2 (1.0). Use t2=0.0 for stub_test or set stub_test=False."
        )
        with pytest.raises(AssertionError, match=error_message):
            super().test_all_conversion_checks(metadata=metadata)
        self.conversion_options["stub_test"] = False
        self.conversion_options["t2"] = 1.0

    def test_get_original_starting_time_and_rate(self):
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        interface = self.data_interface_cls(**self.interface_kwargs)
        stream_name_to_starting_time_and_rate = interface.get_original_starting_time_and_rate(t1=t1, t2=t2)

        for stream_name, (starting_time, rate) in stream_name_to_starting_time_and_rate.items():
            assert starting_time == 0.0
            if stream_name in {"Dv1A", "Dv2A", "Dv3B", "Dv4B"}:
                assert rate == 1017.2526245117188
            else:
                assert rate == 6103.515625

    def test_set_aligned_starting_time_and_rate(self):
        t1 = self.conversion_options.get("t1", 0.0)
        t2 = self.conversion_options.get("t2", 0.0)
        interface = self.data_interface_cls(**self.interface_kwargs)
        unaligned_stream_name_to_starting_time_and_rate = interface.get_original_starting_time_and_rate(t1=t1, t2=t2)

        random_number_generator = np.random.default_rng(seed=0)
        aligned_stream_name_to_starting_time_and_rate = {}
        for stream_name, (starting_time, rate) in unaligned_stream_name_to_starting_time_and_rate.items():
            aligned_starting_time_and_rate = (starting_time + 1.23, rate + random_number_generator.random())
            aligned_stream_name_to_starting_time_and_rate[stream_name] = aligned_starting_time_and_rate
        interface.set_aligned_starting_time_and_rate(
            stream_name_to_aligned_starting_time_and_rate=aligned_stream_name_to_starting_time_and_rate
        )

        retrieved_aligned_stream_name_to_starting_time_and_rate = interface.get_starting_time_and_rate(t1=t1, t2=t2)
        for stream_name, (starting_time, rate) in aligned_stream_name_to_starting_time_and_rate.items():
            retrieved_starting_time, retrieved_rate = retrieved_aligned_stream_name_to_starting_time_and_rate[
                stream_name
            ]
            assert starting_time == retrieved_starting_time
            assert rate == retrieved_rate

    def test_get_events(self):
        interface = self.data_interface_cls(**self.interface_kwargs)
        stream_name_to_expected_len = {"PrtR": 49, "RNPS": 11, "LNRW": 50, "LNnR": 1457}

        events = interface.get_events()

        for stream_name, event in events.items():
            expected_len = stream_name_to_expected_len[stream_name]
            assert (
                len(event["onset"]) == expected_len
            ), f"Stream {stream_name} has onset length {len(event['onset'])} but expected {expected_len}"
            assert (
                len(event["offset"]) == expected_len
            ), f"Stream {stream_name} has offset length {len(event['offset'])} but expected {expected_len}"
            assert (
                len(event["data"]) == expected_len
            ), f"Stream {stream_name} has data length {len(event['data'])} but expected {expected_len}"

    @parameterized.expand(
        [
            ("t0", dict(t1=0.0)),
            ("t0.5", dict(t1=0.5)),
            ("evtype_epocs", dict(evtype=["epocs"])),
            ("evtype_streams", dict(evtype=["streams"])),
            ("evtype_snips", dict(evtype=["snips"])),
            ("evtype_scalars", dict(evtype=["scalars"])),
        ]
    )
    def test_load(self, _, kwargs):
        t2 = 1.0  # t2 must be <=1 for stubbed data
        interface = self.data_interface_cls(**self.interface_kwargs)
        tdt_photometry = interface.load(t2=t2, **kwargs)

        assert list(tdt_photometry.keys()) == ["epocs", "snips", "streams", "scalars", "info", "time_ranges"]
        evtype = kwargs.get("evtype", None)
        if evtype == ["epocs"]:
            assert list(tdt_photometry["epocs"].keys()) == ["LNnR", "PrtR", "RNPS", "LNRW"]
        elif evtype == ["streams"]:
            assert list(tdt_photometry["streams"].keys()) == ["Dv1A", "Dv2A", "Dv3B", "Dv4B", "Fi1d", "Fi1r"]
        elif evtype == ["snips"]:
            assert list(tdt_photometry["snips"].keys()) == []
        elif evtype == ["scalars"]:
            assert list(tdt_photometry["scalars"].keys()) == []
        t1 = kwargs.get("t1", None)
        if t1 == 0.0:
            assert tdt_photometry.streams["Dv1A"].data.shape[0] == 1018
        elif t1 == 0.5:
            assert tdt_photometry.streams["Dv1A"].data.shape[0] == 509

    def test_load_invalid_evtype(self):
        interface = self.data_interface_cls(**self.interface_kwargs)
        with self.assertRaises(AssertionError):
            interface.load(t2=1.0, evtype=["invalid"])
