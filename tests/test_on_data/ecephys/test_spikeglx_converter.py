import datetime
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase

import numpy as np
import pytest
from pydantic import FilePath
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe, NWBConverter
from neuroconv.converters import SortedSpikeGLXConverter, SpikeGLXConverterPipe
from neuroconv.tools.testing.mock_interfaces import MockSortingInterface
from neuroconv.utils import load_dict_from_file

from ..setup_paths import ECEPHY_DATA_PATH

SPIKEGLX_PATH = ECEPHY_DATA_PATH / "spikeglx"


class TestSingleProbeSpikeGLXConverter(TestCase):
    maxDiff = None

    def setUp(self):
        self.tmpdir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.tmpdir)

    def assertNWBFileStructure(self, nwbfile_path: FilePath, expected_session_start_time: datetime):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.session_start_time.replace(tzinfo=None) == expected_session_start_time

            assert "ElectricalSeriesAP" in nwbfile.acquisition
            assert "ElectricalSeriesLF" in nwbfile.acquisition
            assert "TimeSeriesNIDQ" in nwbfile.acquisition

            assert len(nwbfile.acquisition) == 3

            assert "NeuropixelsImec0" in nwbfile.devices
            assert "NIDQBoard" in nwbfile.devices
            assert len(nwbfile.devices) == 2

            assert "NeuropixelsImec0" in nwbfile.electrode_groups
            assert len(nwbfile.electrode_groups) == 1

    def test_single_probe_spikeglx_converter(self):
        converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        metadata = converter.get_metadata()

        test_metadata = deepcopy(metadata)
        for exclude_field in ["session_start_time", "identifier"]:
            test_metadata["NWBFile"].pop(exclude_field)
        expected_metadata = load_dict_from_file(file_path=Path(__file__).parent / "spikeglx_single_probe_metadata.json")

        # Exclude watermarks from testing assertions
        del test_metadata["NWBFile"]["source_script"]
        del test_metadata["NWBFile"]["source_script_file_name"]

        expected_ecephys_metadata = expected_metadata["Ecephys"]
        test_ecephys_metadata = test_metadata["Ecephys"]
        assert test_ecephys_metadata == expected_ecephys_metadata

        device_metadata = test_ecephys_metadata.pop("Device")
        expected_device_metadata = expected_ecephys_metadata.pop("Device")

        assert device_metadata == expected_device_metadata

        nwbfile_path = self.tmpdir / "test_single_probe_spikeglx_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10)
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)

    def test_in_converter_pipe(self):
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        converter_pipe = ConverterPipe(data_interfaces=[spikeglx_converter])

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_converter_pipe.nwb"
        converter_pipe.run_conversion(nwbfile_path=nwbfile_path)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10)
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)

    def test_in_nwbconverter(self):
        class TestConverter(NWBConverter):
            data_interface_classes = dict(SpikeGLX=SpikeGLXConverterPipe)

        source_data = dict(SpikeGLX=dict(folder_path=str(SPIKEGLX_PATH / "Noise4Sam_g0")))
        converter = TestConverter(source_data=source_data)

        # Relevant to https://github.com/catalystneuro/neuroconv/issues/919
        conversion_options_schema = converter.get_conversion_options_schema()
        assert len(conversion_options_schema["properties"]["SpikeGLX"]["properties"]) != 0

        nwbfile_path = self.tmpdir / "test_spikeglx_converter_in_nwbconverter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path)

        expected_session_start_time = datetime(2020, 11, 3, 10, 35, 10)
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)


class TestMultiProbeSpikeGLXConverter(TestCase):
    maxDiff = None

    def setUp(self):
        self.tmpdir = Path(mkdtemp())

    def tearDown(self):
        rmtree(self.tmpdir)

    def assertNWBFileStructure(self, nwbfile_path: FilePath, expected_session_start_time: datetime):
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

        # Do the comparison without timezone information to avoid CI timezone issues
        # The timezone is set by pynbw automatically
        assert nwbfile.session_start_time.replace(tzinfo=None) == expected_session_start_time

        # TODO: improve name of segments using 'Segment{index}' for clarity
        assert "ElectricalSeriesAPImec00" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec01" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec10" in nwbfile.acquisition
        assert "ElectricalSeriesAPImec11" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec00" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec01" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec10" in nwbfile.acquisition
        assert "ElectricalSeriesLFImec11" in nwbfile.acquisition
        assert len(nwbfile.acquisition) == 16

        assert "NeuropixelsImec0" in nwbfile.devices
        assert "NeuropixelsImec1" in nwbfile.devices
        assert len(nwbfile.devices) == 2

        assert "NeuropixelsImec0" in nwbfile.electrode_groups
        assert "NeuropixelsImec1" in nwbfile.electrode_groups
        assert len(nwbfile.electrode_groups) == 2

    def test_multi_probe_spikeglx_converter(self):
        converter = SpikeGLXConverterPipe(
            folder_path=SPIKEGLX_PATH / "multi_trigger_multi_gate" / "SpikeGLX" / "5-19-2022-CI0"
        )
        metadata = converter.get_metadata()

        test_metadata = deepcopy(metadata)
        for exclude_field in ["session_start_time", "identifier"]:
            test_metadata["NWBFile"].pop(exclude_field)
        expected_metadata = load_dict_from_file(file_path=Path(__file__).parent / "spikeglx_multi_probe_metadata.json")

        # Exclude watermarks from testing assertions
        del test_metadata["NWBFile"]["source_script"]
        del test_metadata["NWBFile"]["source_script_file_name"]

        expected_ecephys_metadata = expected_metadata["Ecephys"]
        test_ecephys_metadata = test_metadata["Ecephys"]

        device_metadata = test_ecephys_metadata.pop("Device")
        expected_device_metadata = expected_ecephys_metadata.pop("Device")
        assert device_metadata == expected_device_metadata

        assert test_ecephys_metadata["ElectrodeGroup"] == expected_ecephys_metadata["ElectrodeGroup"]
        assert test_ecephys_metadata["Electrodes"] == expected_ecephys_metadata["Electrodes"]
        assert test_ecephys_metadata["ElectricalSeriesAPImec0"] == expected_ecephys_metadata["ElectricalSeriesAPImec0"]
        assert test_ecephys_metadata["ElectricalSeriesAPImec1"] == expected_ecephys_metadata["ElectricalSeriesAPImec1"]
        assert test_ecephys_metadata["ElectricalSeriesLFImec0"] == expected_ecephys_metadata["ElectricalSeriesLFImec0"]
        assert test_ecephys_metadata["ElectricalSeriesLFImec1"] == expected_ecephys_metadata["ElectricalSeriesLFImec1"]

        # Test all the dictionary
        assert test_ecephys_metadata == expected_ecephys_metadata

        nwbfile_path = self.tmpdir / "test_multi_probe_spikeglx_converter.nwb"
        converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        expected_session_start_time = datetime(2022, 5, 19, 17, 37, 47)
        self.assertNWBFileStructure(nwbfile_path=nwbfile_path, expected_session_start_time=expected_session_start_time)


def test_electrode_table_writing(tmp_path):
    from spikeinterface.extractors.nwbextractors import NwbRecordingExtractor

    converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
    metadata = converter.get_metadata()

    nwbfile = mock_NWBFile()
    converter.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    electrodes_table = nwbfile.electrodes

    # Test AP
    electrical_series = nwbfile.acquisition["ElectricalSeriesAP"]
    ap_electrodes_table_region = electrical_series.electrodes
    region_indices = ap_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["imec0.ap"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_ap = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_ap)

    # Test LF
    electrical_series = nwbfile.acquisition["ElectricalSeriesLF"]
    lf_electrodes_table_region = electrical_series.electrodes
    region_indices = lf_electrodes_table_region.data
    recording_extractor = converter.data_interface_objects["imec0.lf"].recording_extractor

    saved_channel_names = electrodes_table[region_indices]["channel_name"]
    expected_channel_names_lf = recording_extractor.get_property("channel_name")
    np.testing.assert_array_equal(saved_channel_names, expected_channel_names_lf)

    # Write to file and read back in
    temporary_folder = tmp_path / "test_folder"
    temporary_folder.mkdir()
    nwbfile_path = temporary_folder / "test_spikeglx_converter_electrode_table.nwb"
    with NWBHDF5IO(path=nwbfile_path, mode="w") as io:
        io.write(nwbfile)

    # Test round trip with spikeinterface
    recording_extractor_ap = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_path="acquisition/ElectricalSeriesAP",
    )

    channel_ids = recording_extractor_ap.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_ap)

    recording_extractor_lf = NwbRecordingExtractor(
        file_path=nwbfile_path,
        electrical_series_path="acquisition/ElectricalSeriesLF",
    )

    channel_ids = recording_extractor_lf.get_channel_ids()
    np.testing.assert_array_equal(channel_ids, expected_channel_names_lf)


class TestSortedSpikeGLXConverter:
    """Test suite for SortedSpikeGLXConverter functionality based on notebook examples."""

    def test_multi_trigger_multi_gate_example(self, tmp_path):
        """Test based on notebook_example1.py - multi_trigger_multi_gate dataset."""
        # Initialize base SpikeGLX converter (notebook example 1)
        spikeglx_converter = SpikeGLXConverterPipe(
            folder_path=SPIKEGLX_PATH / "multi_trigger_multi_gate" / "SpikeGLX" / "5-19-2022-CI0"
        )

        # Get AP streams for sorting (like in notebook example)
        ap_streams = [s for s in spikeglx_converter._stream_ids if s.endswith(".ap") and not s.endswith("-SYNC")]

        # Create sorting configuration with specific electrode mappings
        sorting_configuration = []

        for stream_id in ap_streams:

            # Create mock sorting with specific unit count and rename units for clarity
            num_units = 3
            sorting_interface = MockSortingInterface(num_units=num_units)
            sorting_extractor = sorting_interface.sorting_extractor
            sorting_extractor = sorting_extractor.rename_units(new_unit_ids=["unit_x", "unit_y", "unit_z"])
            sorting_interface.sorting_extractor = sorting_extractor

            # Create specific unit-to-channel mappings using hardcoded channel names
            # Note: These are specific to each stream (imec0.ap, imec1.ap, etc.)
            unit_ids_to_channel_ids = {
                "unit_x": [f"{stream_id}#AP0", f"{stream_id}#AP1"],  # First 2 channels
                "unit_y": [f"{stream_id}#AP2"],  # 3rd channel
                "unit_z": [f"{stream_id}#AP3", f"{stream_id}#AP4", f"{stream_id}#AP5"],  # Channels 3-5
            }

            sorting_configuration.append(
                {
                    "stream_id": stream_id,
                    "sorting_interface": sorting_interface,
                    "unit_ids_to_channel_ids": unit_ids_to_channel_ids,
                }
            )

        # Create sorted converter
        sorted_converter = SortedSpikeGLXConverter(
            spikeglx_converter=spikeglx_converter, sorting_configuration=sorting_configuration
        )

        # Run conversion
        nwbfile_path = tmp_path / "test_multi_trigger_multi_gate.nwb"
        sorted_converter.run_conversion(nwbfile_path=nwbfile_path)

        # Verify electrode mappings are correct
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            # Verify units table exists
            assert nwbfile.units is not None
            assert len(nwbfile.units) == len(ap_streams) * 3  # 3 units per stream

            # Verify electrode mappings match expectations
            units_df = nwbfile.units.to_dataframe()

            # Define expected channel patterns for each unit type
            unit_channel_patterns = {"unit_x": ["AP0", "AP1"], "unit_y": ["AP2"], "unit_z": ["AP3", "AP4", "AP5"]}

            for _, unit_row in units_df.iterrows():
                unit_name = unit_row["unit_name"]  # NeuroConv stores unit_ids as unit_names
                unit_electrode_table_region = unit_row.electrodes

                # Get the electrode indices from the region
                electrode_indices = list(unit_electrode_table_region.index)

                # Get the actual channel names for these electrode indices
                unit_electrodes = nwbfile.electrodes[electrode_indices]
                actual_channel_names = list(unit_electrodes["channel_name"])

                # Verify that the electrode table indices correspond to the correct channels
                assert len(actual_channel_names) > 0, f"Unit {unit_name} has no channel mappings"

                # Extract the electrode names (without stream prefix)
                actual_electrode_names = [ch.split("#")[-1] for ch in actual_channel_names]
                expected_electrode_names = unit_channel_patterns[unit_name]

                # Verify the electrode names match the expected pattern
                assert (
                    actual_electrode_names == expected_electrode_names
                ), f"Unit {unit_name} has electrodes {actual_electrode_names}, expected {expected_electrode_names}"

    def test_noise4sam_single_probe_example(self, tmp_path):
        """Test with Noise4Sam single probe dataset using specific electrode mappings."""
        # Initialize converter
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")

        # Create mock sorting with specific mappings and rename units for clarity
        num_units = 4
        sorting_interface = MockSortingInterface(num_units=num_units)
        sorting_extractor = sorting_interface.sorting_extractor
        sorting_extractor = sorting_extractor.rename_units(new_unit_ids=["unit_a", "unit_b", "unit_c", "unit_d"])
        sorting_interface.sorting_extractor = sorting_extractor

        # Create specific unit-to-channel mappings using hardcoded channel names
        unit_ids_to_channel_ids = {
            "unit_a": ["imec0.ap#AP0", "imec0.ap#AP1", "imec0.ap#AP2"],  # First 3 channels
            "unit_b": ["imec0.ap#AP10", "imec0.ap#AP11"],  # Channels 10-11
            "unit_c": ["imec0.ap#AP20"],  # Channel 20
            "unit_d": ["imec0.ap#AP30", "imec0.ap#AP31"],  # Channels 30-31
        }

        sorting_configuration = [
            {
                "stream_id": "imec0.ap",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": unit_ids_to_channel_ids,
            }
        ]

        # Create sorted converter
        sorted_converter = SortedSpikeGLXConverter(
            spikeglx_converter=spikeglx_converter, sorting_configuration=sorting_configuration
        )

        # Run conversion
        nwbfile_path = tmp_path / "test_noise4sam_single_probe.nwb"
        sorted_converter.run_conversion(nwbfile_path=nwbfile_path)

        # Verify electrode mappings are correct
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.units is not None
            assert len(nwbfile.units) == num_units

            # Hardcode the expected electrode indices based on the channel mappings
            # The electrode table contains AP, LF, and NIDQ streams
            # AP electrodes start at index 384 in the combined table
            expected_unit_electrode_indices = {
                "unit_a": [384, 385, 386],  # AP0, AP1, AP2 → electrodes 384, 385, 386
                "unit_b": [394, 395],  # AP10, AP11 → electrodes 394, 395
                "unit_c": [404],  # AP20 → electrode 404
                "unit_d": [414, 415],  # AP30, AP31 → electrodes 414, 415
            }

            # Define expected electrode names for each unit
            expected_unit_electrode_names = {
                "unit_a": ["AP0", "AP1", "AP2"],  # First 3 channels
                "unit_b": ["AP10", "AP11"],  # Channels 10-11
                "unit_c": ["AP20"],  # Channel 20
                "unit_d": ["AP30", "AP31"],  # Channels 30-31
            }

            # Test that the region in the units table points to the correct electrodes
            unit_table = nwbfile.units
            for unit_row in unit_table.to_dataframe().itertuples(index=False):
                # NeuroConv writes unit_ids as unit_names
                unit_id = unit_row.unit_name

                unit_electrode_table_region = unit_row.electrodes
                expected_indices = expected_unit_electrode_indices[unit_id]

                # Convert electrode table region indices to list for comparison
                actual_indices = list(unit_electrode_table_region.index)
                assert actual_indices == expected_indices

                # Also verify the channel names match what we specified
                unit_electrodes = nwbfile.electrodes[actual_indices]
                actual_channel_names = list(unit_electrodes["channel_name"])
                expected_channel_names = expected_unit_electrode_names[unit_id]

                assert (
                    actual_channel_names == expected_channel_names
                ), f"Unit {unit_id} has channel names {actual_channel_names}, expected {expected_channel_names}"

    def test_multi_probe_with_sorting(self, tmp_path):
        """Test SortedSpikeGLXConverter with multiple probes using hard-coded electrode mappings."""
        # Initialize base SpikeGLX converter with multi-probe data
        spikeglx_converter = SpikeGLXConverterPipe(
            folder_path=SPIKEGLX_PATH / "multi_trigger_multi_gate" / "SpikeGLX" / "5-19-2022-CI0"
        )

        # Create mock sorting for imec0.ap stream
        num_units_imec0 = 2
        sorting_interface_imec0 = MockSortingInterface(num_units=num_units_imec0)
        sorting_extractor_imec0 = sorting_interface_imec0.sorting_extractor
        sorting_extractor_imec0 = sorting_extractor_imec0.rename_units(new_unit_ids=["unit_alpha", "unit_beta"])
        sorting_interface_imec0.sorting_extractor = sorting_extractor_imec0

        # Create mock sorting for imec1.ap stream
        num_units_imec1 = 2
        sorting_interface_imec1 = MockSortingInterface(num_units=num_units_imec1)
        sorting_extractor_imec1 = sorting_interface_imec1.sorting_extractor
        sorting_extractor_imec1 = sorting_extractor_imec1.rename_units(new_unit_ids=["unit_gamma", "unit_delta"])
        sorting_interface_imec1.sorting_extractor = sorting_extractor_imec1

        # Create explicit sorting configuration
        sorting_configuration = [
            {
                "stream_id": "imec0.ap",
                "sorting_interface": sorting_interface_imec0,
                "unit_ids_to_channel_ids": {
                    "unit_alpha": ["imec0.ap#AP0", "imec0.ap#AP1"],  # First 2 channels of imec0
                    "unit_beta": ["imec0.ap#AP5", "imec0.ap#AP6"],  # Channels 5-6 of imec0
                },
            },
            {
                "stream_id": "imec1.ap",
                "sorting_interface": sorting_interface_imec1,
                "unit_ids_to_channel_ids": {
                    "unit_gamma": ["imec1.ap#AP0", "imec1.ap#AP1"],  # First 2 channels of imec1
                    "unit_delta": ["imec1.ap#AP10", "imec1.ap#AP11"],  # Channels 10-11 of imec1
                },
            },
        ]

        # Create sorted converter
        sorted_converter = SortedSpikeGLXConverter(
            spikeglx_converter=spikeglx_converter, sorting_configuration=sorting_configuration
        )

        # Run conversion
        nwbfile_path = tmp_path / "test_multi_probe_sorted.nwb"
        sorted_converter.run_conversion(nwbfile_path=nwbfile_path)

        # Verify electrode mappings are correct
        with NWBHDF5IO(path=nwbfile_path) as io:
            nwbfile = io.read()

            assert nwbfile.units is not None
            assert len(nwbfile.units) == 4  # 2 units per stream, 2 streams

            # Hardcode the expected electrode indices based on the channel mappings
            # Multi-probe electrode table with deterministic interface ordering
            expected_unit_electrode_indices = {
                "unit_alpha": [768, 769],  # imec0.ap AP0, AP1 → electrodes 768, 769
                "unit_beta": [773, 774],  # imec0.ap AP5, AP6 → electrodes 773, 774
                "unit_gamma": [1152, 1153],  # imec1.ap AP0, AP1 → electrodes 1152, 1153
                "unit_delta": [1162, 1163],  # imec1.ap AP10, AP11 → electrodes 1162, 1163
            }

            # Define expected electrode names for each unit
            expected_unit_electrode_names = {
                "unit_alpha": ["AP0", "AP1"],
                "unit_beta": ["AP5", "AP6"],
                "unit_gamma": ["AP0", "AP1"],
                "unit_delta": ["AP10", "AP11"],
            }

            # Test that the region in the units table points to the correct electrodes
            unit_table = nwbfile.units
            for unit_row in unit_table.to_dataframe().itertuples(index=False):
                # NeuroConv writes unit_ids as unit_names
                unit_id = unit_row.unit_name

                unit_electrode_table_region = unit_row.electrodes
                expected_indices = expected_unit_electrode_indices[unit_id]

                # Convert electrode table region indices to list for comparison
                actual_indices = list(unit_electrode_table_region.index)
                assert actual_indices == expected_indices

                # Also verify the channel names match what we specified
                unit_electrodes = nwbfile.electrodes[actual_indices]
                actual_channel_names = list(unit_electrodes["channel_name"])
                expected_channel_names = expected_unit_electrode_names[unit_id]

                assert (
                    actual_channel_names == expected_channel_names
                ), f"Unit {unit_id} has channel names {actual_channel_names}, expected {expected_channel_names}"

    def test_invalid_stream_id(self):
        """Test that invalid stream IDs raise appropriate errors."""
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        sorting_interface = MockSortingInterface(num_units=2)

        # Test with non-existent stream ID
        invalid_config = [
            {
                "stream_id": "nonexistent_stream",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {"0": ["imec0.ap#AP0"], "1": ["imec0.ap#AP1"]},
            }
        ]

        with pytest.raises(ValueError, match="Stream 'nonexistent_stream' not found in SpikeGLXConverterPipe"):
            SortedSpikeGLXConverter(spikeglx_converter=spikeglx_converter, sorting_configuration=invalid_config)

    def test_non_ap_stream_error(self):
        """Test that non-AP streams cannot have sorting data."""
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        sorting_interface = MockSortingInterface(num_units=2)

        # Test with LF stream (should fail)
        lf_config = [
            {
                "stream_id": "imec0.lf",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {"0": ["imec0.lf#LF0"], "1": ["imec0.lf#LF1"]},
            }
        ]

        with pytest.raises(
            ValueError, match="Stream 'imec0.lf' is not an AP stream. Only AP streams can have sorting data"
        ):
            SortedSpikeGLXConverter(spikeglx_converter=spikeglx_converter, sorting_configuration=lf_config)

    def test_invalid_channel_mapping(self):
        """Test that invalid channel mappings are caught by underlying SortedRecordingConverter."""
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        sorting_interface = MockSortingInterface(num_units=2)

        # Test with invalid channel IDs
        invalid_config = [
            {
                "stream_id": "imec0.ap",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {"0": ["invalid_channel_id"], "1": ["another_invalid_channel"]},
            }
        ]

        with pytest.raises(ValueError, match="Inexistent channel IDs"):
            SortedSpikeGLXConverter(spikeglx_converter=spikeglx_converter, sorting_configuration=invalid_config)

    def test_incomplete_unit_mapping(self):
        """Test that incomplete unit mappings are caught."""
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")
        sorting_interface = MockSortingInterface(num_units=3)
        ap_interface = spikeglx_converter.data_interface_objects["imec0.ap"]
        channel_ids = ap_interface.channel_ids

        # Test with missing unit mapping (only map 2 out of 3 units)
        incomplete_config = [
            {
                "stream_id": "imec0.ap",
                "sorting_interface": sorting_interface,
                "unit_ids_to_channel_ids": {
                    "0": [channel_ids[0]],
                    "1": [channel_ids[1]],
                    # Unit "2" is missing
                },
            }
        ]

        with pytest.raises(ValueError, match="Units {'2'} from sorting interface have no channel mapping"):
            SortedSpikeGLXConverter(spikeglx_converter=spikeglx_converter, sorting_configuration=incomplete_config)

    def test_empty_sorting_configuration_raises_error(self):
        """Test that empty sorting configuration raises appropriate error."""
        spikeglx_converter = SpikeGLXConverterPipe(folder_path=SPIKEGLX_PATH / "Noise4Sam_g0")

        # Empty sorting configuration should raise error
        with pytest.raises(ValueError, match="SortedSpikeGLXConverter requires at least one sorting configuration"):
            SortedSpikeGLXConverter(spikeglx_converter=spikeglx_converter, sorting_configuration=[])
