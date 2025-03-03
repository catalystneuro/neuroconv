from platform import python_version as get_python_version

import jsonschema
import numpy as np
import pytest
from hdmf.testing import TestCase
from packaging.version import Version

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import Spike2RecordingInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.testing.mock_interfaces import (
    MockRecordingInterface,
    MockSortingInterface,
)

python_version = Version(get_python_version())

from neuroconv.tools.testing.data_interface_mixins import (
    RecordingExtractorInterfaceTestMixin,
    SortingExtractorInterfaceTestMixin,
)


class TestSortingInterface(SortingExtractorInterfaceTestMixin):

    data_interface_cls = MockSortingInterface
    interface_kwargs = dict(num_units=4, durations=[0.100])

    def test_propagate_conversion_options(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        nwbfile = interface.create_nwbfile(
            stub_test=True,
            metadata=metadata,
            write_as="processing",
            units_name="processed_units",
            units_description="The processed units.",
        )

        ecephys = get_module(nwbfile, "ecephys")

        assert nwbfile.units is None
        assert "processed_units" in ecephys.data_interfaces

    def test_stub(self):

        interface = MockSortingInterface(num_units=4, durations=[1.0])
        sorting_extractor = interface.sorting_extractor
        unit_ids = sorting_extractor.unit_ids
        first_unit_spike = {
            unit_id: sorting_extractor.get_unit_spike_train(unit_id=unit_id, return_times=True)[0]
            for unit_id in unit_ids
        }

        nwbfile = interface.create_nwbfile(stub_test=True)
        units_table = nwbfile.units.to_dataframe()

        for unit_id, first_spike_time in first_unit_spike.items():
            unit_row = units_table[units_table["unit_name"] == unit_id]
            unit_spike_times = unit_row["spike_times"].values[0]
            np.testing.assert_almost_equal(unit_spike_times[0], first_spike_time, decimal=6)

    def test_stub_with_recording(self):
        interface = MockSortingInterface(num_units=4, durations=[1.0])

        recording_interface = MockRecordingInterface(num_channels=4, durations=[2.0])
        interface.register_recording(recording_interface)

        sorting_extractor = interface.sorting_extractor
        unit_ids = sorting_extractor.unit_ids
        first_unit_spike = {
            unit_id: sorting_extractor.get_unit_spike_train(unit_id=unit_id, return_times=True)[0]
            for unit_id in unit_ids
        }

        nwbfile = interface.create_nwbfile(stub_test=True)
        units_table = nwbfile.units.to_dataframe()

        for unit_id, first_spike_time in first_unit_spike.items():
            unit_row = units_table[units_table["unit_name"] == unit_id]
            unit_spike_times = unit_row["spike_times"].values[0]
            np.testing.assert_almost_equal(unit_spike_times[0], first_spike_time, decimal=6)

    def test_electrode_indices(self, setup_interface):

        recording_interface = MockRecordingInterface(num_channels=4, durations=[0.100])
        recording_extractor = recording_interface.recording_extractor
        recording_extractor = recording_extractor.rename_channels(new_channel_ids=["a", "b", "c", "d"])
        recording_extractor.set_property(key="property", values=["A", "B", "C", "D"])
        recording_interface.recording_extractor = recording_extractor

        nwbfile = recording_interface.create_nwbfile()

        unit_electrode_indices = [[3], [0, 1], [1], [2]]
        expected_properties_matching = [["D"], ["A", "B"], ["B"], ["C"]]
        self.interface.add_to_nwbfile(nwbfile=nwbfile, unit_electrode_indices=unit_electrode_indices)

        unit_table = nwbfile.units

        for unit_row, electrode_indices, property in zip(
            unit_table.to_dataframe().itertuples(index=False),
            unit_electrode_indices,
            expected_properties_matching,
        ):
            electrode_table_region = unit_row.electrodes
            electrode_table_region_indices = electrode_table_region.index.to_list()
            assert electrode_table_region_indices == electrode_indices

            electrode_table_region_properties = electrode_table_region["property"].to_list()
            assert electrode_table_region_properties == property

    def test_electrode_indices_assertion_error_when_missing_table(self, setup_interface):
        with pytest.raises(
            ValueError,
            match="Electrodes table is required to map units to electrodes. Add an electrode table to the NWBFile first.",
        ):
            self.interface.create_nwbfile(unit_electrode_indices=[[0], [1], [2], [3]])


class TestRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = dict(num_channels=4, durations=[0.100])

    def test_stub(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_no_slash_in_name(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        metadata["Ecephys"]["ElectricalSeries"]["name"] = "test/slash"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            interface.validate_metadata(metadata)

    def test_stub_multi_segment(self):

        interface = MockRecordingInterface(durations=[0.100, 0.100])
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_always_write_timestamps(self, setup_interface):

        nwbfile = self.interface.create_nwbfile(always_write_timestamps=True)
        electrical_series = nwbfile.acquisition["ElectricalSeries"]
        expected_timestamps = self.interface.recording_extractor.get_times()
        np.testing.assert_array_equal(electrical_series.timestamps[:], expected_timestamps)

    def test_group_naming_not_adding_extra_devices(self, setup_interface):

        interface = self.interface
        recording_extractor = interface.recording_extractor
        recording_extractor.set_channel_groups(groups=[0, 1, 2, 3])
        recording_extractor.set_property(key="group_name", values=["group1", "group2", "group3", "group4"])

        nwbfile = interface.create_nwbfile()

        assert len(nwbfile.devices) == 1
        assert len(nwbfile.electrode_groups) == 4

    def test_error_for_append_with_in_memory_file(self, setup_interface, tmp_path):

        nwbfile_path = tmp_path / "test.nwb"
        self.interface.run_conversion(nwbfile_path=nwbfile_path)

        nwbfile = self.interface.create_nwbfile()

        expected_error_message = (
            "Cannot append to an existing file while also providing an in-memory NWBFile. "
            "Either set overwrite=True to replace the existing file, or remove the nwbfile parameter to append to the existing file on disk."
        )
        with pytest.raises(ValueError, match=expected_error_message):
            self.interface.run_conversion(nwbfile=nwbfile, nwbfile_path=nwbfile_path, overwrite=False)

        converter = ConverterPipe(data_interfaces=[self.interface])
        with pytest.raises(ValueError, match=expected_error_message):
            converter.run_conversion(nwbfile=nwbfile, nwbfile_path=nwbfile_path, overwrite=False)


class TestAssertions(TestCase):
    @pytest.mark.skipif(python_version.minor != 10, reason="Only testing with Python 3.10!")
    def test_spike2_import_assertions_3_10(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.10!",
        ):
            Spike2RecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")

    @pytest.mark.skipif(python_version.minor != 11, reason="Only testing with Python 3.11!")
    def test_spike2_import_assertions_3_11(self):
        with self.assertRaisesWith(
            exc_type=ModuleNotFoundError,
            exc_msg="\nThe package 'sonpy' is not available for Python version 3.11!",
        ):
            Spike2RecordingInterface.get_all_channels_info(file_path="does_not_matter.smrx")
