import re
import warnings
from platform import python_version as get_python_version

import jsonschema
import numpy as np
import pytest
from hdmf.testing import TestCase
from packaging.version import Version
from probeinterface import Probe, ProbeGroup

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

    def test_rename_unit_ids(self):
        interface = MockSortingInterface(num_units=3)

        # Rename all units
        unit_ids_map = {"0": "neuron_1", "1": "neuron_2", "2": "neuron_3"}
        interface.rename_unit_ids(unit_ids_map)

        new_unit_ids = interface.units_ids
        expected_unit_ids = ["neuron_1", "neuron_2", "neuron_3"]
        assert new_unit_ids.tolist() == expected_unit_ids

    def test_rename_unit_ids_partial(self):
        interface = MockSortingInterface(num_units=3)

        # Rename only some units
        unit_ids_map = {"0": "neuron_1", "2": "neuron_3"}
        interface.rename_unit_ids(unit_ids_map)

        new_unit_ids = interface.units_ids
        expected_unit_ids = ["neuron_1", "1", "neuron_3"]  # Unit "1" remains unchanged
        assert new_unit_ids.tolist() == expected_unit_ids

    def test_rename_unit_ids_invalid_input_type(self):
        interface = MockSortingInterface(num_units=3)

        with pytest.raises(TypeError, match="unit_ids_map must be a dictionary"):
            interface.rename_unit_ids("not_a_dict")

        with pytest.raises(TypeError, match="unit_ids_map must be a dictionary"):
            interface.rename_unit_ids(["0", "1"])

    def test_rename_unit_ids_nonexistent_unit(self):
        interface = MockSortingInterface(num_units=3)

        unit_ids_map = {"0": "unit_a", "nonexistent": "unit_b"}

        with pytest.raises(ValueError, match="Unit IDs \\['nonexistent'\\] not found in sorting extractor"):
            interface.rename_unit_ids(unit_ids_map)

    def test_waveform_data_dict_propagation(self, setup_interface):
        """Test that waveform_data_dict is properly passed through add_to_nwbfile."""
        interface = self.interface
        nwbfile = interface.create_nwbfile(metadata=interface.get_metadata())

        # Get number of units from the interface
        num_units = len(interface.sorting_extractor.get_unit_ids())
        waveform_means = np.random.randn(num_units, 82, 32).astype(np.float32)
        waveform_sds = np.random.randn(num_units, 82, 32).astype(np.float32)

        # Create a fresh nwbfile to test with waveform_data_dict
        from datetime import datetime

        from pynwb import NWBFile

        nwbfile = NWBFile(
            session_description="test session",
            identifier="test_identifier",
            session_start_time=datetime.now(),
        )

        interface.add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=interface.get_metadata(),
            waveform_data_dict={
                "means": waveform_means,
                "sds": waveform_sds,
                "sampling_rate": 30000.0,
                "unit": "microvolts",
            },
        )

        # Verify waveform metadata is set on units table
        assert nwbfile.units.waveform_rate == 30000.0
        assert nwbfile.units.waveform_unit == "microvolts"
        assert "waveform_mean" in nwbfile.units.colnames
        assert "waveform_sd" in nwbfile.units.colnames

        # Verify waveform data
        np.testing.assert_array_equal(nwbfile.units["waveform_mean"][0], waveform_means[0])
        np.testing.assert_array_equal(nwbfile.units["waveform_sd"][0], waveform_sds[0])


class TestRecordingInterface(RecordingExtractorInterfaceTestMixin):
    data_interface_cls = MockRecordingInterface
    interface_kwargs = dict(num_channels=4, durations=[0.100])

    def test_stub(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        interface.create_nwbfile(stub_test=True, metadata=metadata)

    def test_stub_with_starting_time(self, setup_interface):

        interface = MockRecordingInterface(durations=[1.0])

        recording = interface.recording_extractor
        # TODO Remove the following line once Spikeinterface 0.102.4 or higher is released
        # See https://github.com/SpikeInterface/spikeinterface/pull/3940
        recording._recording_segments[0].t_start = 0.0
        recording.shift_times(2.0)

        interface.create_nwbfile(stub_test=True)

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
            self.interface.run_conversion(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                overwrite=True,
                append_on_disk_nwbfile=True,
            )

        converter = ConverterPipe(data_interfaces=[self.interface])
        with pytest.raises(ValueError, match=expected_error_message):
            converter.run_conversion(
                nwbfile=nwbfile,
                nwbfile_path=nwbfile_path,
                overwrite=True,
                append_on_disk_nwbfile=True,
            )

    def test_no_slash_in_name(self, setup_interface):
        interface = self.interface
        metadata = interface.get_metadata()
        metadata["Ecephys"]["ElectricalSeries"]["name"] = "test/slash"
        with pytest.raises(jsonschema.exceptions.ValidationError):
            interface.validate_metadata(metadata)

    def test_set_probe(self, setup_interface):
        """Test setting probe with by_probe group mode."""
        # Create a simple probe
        probe = Probe(ndim=2, si_units="um")
        positions = np.array([[0, 0], [0, 20], [0, 40], [0, 60]])
        probe.set_contacts(positions=positions, shapes="circle", shape_params={"radius": 5})

        # Set device channel indices to match our recording
        probe.set_device_channel_indices(np.arange(4))

        self.interface.set_probe(probe, group_mode="by_probe")

        # Check that probe is now set
        assert self.interface.has_probe()

        # With by_probe mode, all channels should be in the same group (group 0)
        recording = self.interface.recording_extractor
        groups = recording.get_property("group")
        expected_groups = np.array([0, 0, 0, 0])
        np.testing.assert_array_equal(groups, expected_groups)

        # Check that group_name property was set
        group_names = recording.get_property("group_name")
        expected_group_names = np.array(["0", "0", "0", "0"])
        np.testing.assert_array_equal(group_names, expected_group_names)

        # Check NWB file structure
        nwbfile = self.interface.create_nwbfile()

        # Should have 1 electrode group (all channels in one probe)
        assert len(nwbfile.electrode_groups) == 1
        assert "0" in nwbfile.electrode_groups

        # Check electrodes table
        electrodes_df = nwbfile.electrodes.to_dataframe()
        electrode_group_names = electrodes_df["group_name"].values
        expected_electrode_groups = ["0", "0", "0", "0"]
        np.testing.assert_array_equal(electrode_group_names, expected_electrode_groups)

    def test_set_probe_group(self, setup_interface):
        """Test setting a ProbeGroup with multiple probes."""
        # Create first probe (2 channels)
        probe1 = Probe(ndim=2, si_units="um")
        positions1 = np.array([[0, 0], [0, 20]])
        probe1.set_contacts(positions=positions1, shapes="circle", shape_params={"radius": 5})
        probe1.set_device_channel_indices([0, 1])

        # Create second probe (2 channels)
        probe2 = Probe(ndim=2, si_units="um")
        positions2 = np.array([[100, 0], [100, 20]])
        probe2.set_contacts(positions=positions2, shapes="circle", shape_params={"radius": 5})
        probe2.set_device_channel_indices([2, 3])

        # Create ProbeGroup
        probe_group = ProbeGroup()
        probe_group.add_probe(probe1)
        probe_group.add_probe(probe2)

        # Set the ProbeGroup using the interface's set_probe method
        self.interface.set_probe(probe_group, group_mode="by_probe")

        # Check that probe is now set
        assert self.interface.has_probe()

        # Check that group property was set correctly - each probe should have its own group
        recording = self.interface.recording_extractor
        groups = recording.get_property("group")
        expected_groups = np.array([0, 0, 1, 1])  # First 2 channels in group 0, next 2 in group 1
        np.testing.assert_array_equal(groups, expected_groups)

        # Check that group_name property was set
        group_names = recording.get_property("group_name")
        expected_group_names = np.array(["0", "0", "1", "1"])
        np.testing.assert_array_equal(group_names, expected_group_names)

        # Check NWB file structure
        nwbfile = self.interface.create_nwbfile()

        # Should have 2 electrode groups (one per probe)
        assert len(nwbfile.electrode_groups) == 2
        assert "0" in nwbfile.electrode_groups
        assert "1" in nwbfile.electrode_groups

        # Check electrodes table
        electrodes_df = nwbfile.electrodes.to_dataframe()
        electrode_group_names = electrodes_df["group_name"].values
        expected_electrode_groups = ["0", "0", "1", "1"]
        np.testing.assert_array_equal(electrode_group_names, expected_electrode_groups)

    def test_set_probe_by_shank(self, setup_interface):
        """Test setting probe with by_shank group mode."""
        # Create a probe with multiple shanks (6 channels for this test)
        interface = MockRecordingInterface(num_channels=6, durations=[0.100])

        probe = Probe(ndim=2, si_units="um")
        positions = np.array([[0, 0], [0, 20], [50, 0], [50, 20], [100, 0], [100, 20]])  # shank 0  # shank 1  # shank 2
        probe.set_contacts(positions=positions, shapes="circle", shape_params={"radius": 5})

        # Set shank IDs - two channels per shank
        shank_ids = [0, 0, 1, 1, 2, 2]
        probe.set_shank_ids(shank_ids)

        # Set device channel indices
        probe.set_device_channel_indices(np.arange(6))

        interface.set_probe(probe, group_mode="by_shank")

        # Check that probe is now set
        assert interface.has_probe()

        # With by_shank mode, each shank should be a separate group
        recording = interface.recording_extractor
        groups = recording.get_property("group")
        expected_groups = np.array([0, 0, 1, 1, 2, 2])  # Each pair of channels in different group
        np.testing.assert_array_equal(groups, expected_groups)

        # Check that group_name property was set
        group_names = recording.get_property("group_name")
        expected_group_names = np.array(["0", "0", "1", "1", "2", "2"])
        np.testing.assert_array_equal(group_names, expected_group_names)

        # Check NWB file structure
        nwbfile = interface.create_nwbfile()

        # Should have 3 electrode groups (one per shank)
        assert len(nwbfile.electrode_groups) == 3
        assert "0" in nwbfile.electrode_groups
        assert "1" in nwbfile.electrode_groups
        assert "2" in nwbfile.electrode_groups

        # Check electrodes table
        electrodes_df = nwbfile.electrodes.to_dataframe()
        electrode_group_names = electrodes_df["group_name"].values
        expected_electrode_groups = ["0", "0", "1", "1", "2", "2"]
        np.testing.assert_array_equal(electrode_group_names, expected_electrode_groups)

    def test_set_probe_group_by_shank(self):
        """Test setting a ProbeGroup with multiple probes using by_shank group mode."""
        # Create interface with 6 channels to accommodate two probes with 3 channels each
        interface = MockRecordingInterface(num_channels=6, durations=[0.100])

        # Create first probe with 2 shanks (3 channels total)
        probe1 = Probe(ndim=2, si_units="um")
        positions1 = np.array([[0, 0], [0, 20], [50, 0]])  # 2 channels on shank 0, 1 channel on shank 1
        probe1.set_contacts(positions=positions1, shapes="circle", shape_params={"radius": 5})
        probe1.set_device_channel_indices([0, 1, 2])
        probe1.set_shank_ids([0, 0, 1])  # First 2 channels on shank 0, last channel on shank 1

        # Create second probe with 2 shanks (3 channels total)
        probe2 = Probe(ndim=2, si_units="um")
        positions2 = np.array([[100, 0], [150, 0], [150, 20]])  # 1 channel on shank 0, 2 channels on shank 1
        probe2.set_contacts(positions=positions2, shapes="circle", shape_params={"radius": 5})
        probe2.set_device_channel_indices([3, 4, 5])
        probe2.set_shank_ids([0, 1, 1])  # First channel on shank 0, last 2 channels on shank 1
        # Note that in probe interface, shanks are local to the project and those will still be defined
        # as separate groups when added to the interface.

        # Create ProbeGroup
        probe_group = ProbeGroup()
        probe_group.add_probe(probe1)
        probe_group.add_probe(probe2)

        # Set the ProbeGroup using by_shank mode
        interface.set_probe(probe_group, group_mode="by_shank")

        # Check that probe is now set
        assert interface.has_probe()

        # With by_shank mode, each shank from each probe should be a separate group
        # Expected groups: probe1_shank0=0, probe1_shank1=1, probe2_shank0=2, probe2_shank1=3
        recording = interface.recording_extractor
        groups = recording.get_property("group")
        expected_groups = np.array(
            [0, 0, 1, 2, 3, 3]
        )  # [probe1_shank0, probe1_shank0, probe1_shank1, probe2_shank0, probe2_shank1, probe2_shank1]
        np.testing.assert_array_equal(groups, expected_groups)

        # Check that group_name property was set
        group_names = recording.get_property("group_name")
        expected_group_names = np.array(["0", "0", "1", "2", "3", "3"])
        np.testing.assert_array_equal(group_names, expected_group_names)

        # Check NWB file structure
        nwbfile = interface.create_nwbfile()

        # Should have 4 electrode groups (2 shanks from each probe)
        assert len(nwbfile.electrode_groups) == 4
        for group_id in ["0", "1", "2", "3"]:
            assert group_id in nwbfile.electrode_groups

        # Check electrodes table
        electrodes_df = nwbfile.electrodes.to_dataframe()
        electrode_group_names = electrodes_df["group_name"].values
        expected_electrode_groups = ["0", "0", "1", "2", "3", "3"]
        np.testing.assert_array_equal(electrode_group_names, expected_electrode_groups)

    def test_electrode_name_column_added_with_probe(self):
        """Test that electrode_name column is added when probe is attached."""
        # Create interface with probe attached
        interface = MockRecordingInterface(num_channels=4, durations=[0.100], set_probe=True)

        # Verify probe is attached
        assert interface.has_probe()

        # Create NWB file
        nwbfile = interface.create_nwbfile()

        # Check that electrode_name column exists
        assert "electrode_name" in nwbfile.electrodes.colnames, "electrode_name column should be present with probe"

        # Check that electrode names match expected format (e0, e1, e2, e3)
        electrode_names = nwbfile.electrodes["electrode_name"][:]
        expected_electrode_names = ["e0", "e1", "e2", "e3"]
        np.testing.assert_array_equal(electrode_names, expected_electrode_names)

        # Verify electrode names match probe contact IDs
        probe = interface.recording_extractor.get_probe()
        expected_contact_ids = probe.contact_ids
        np.testing.assert_array_equal(electrode_names, expected_contact_ids)


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


# This is a temporary test class to show that the migration path to kwargs only works as intended.
# TODO: Remove this test class in June 2026 or after when positional arguments are no longer supported.
class TestMockRecordingInterfaceArgsDeprecation:
    """Test the *args deprecation pattern in MockRecordingInterface.__init__."""

    # Tests for __init__ deprecation
    def test_init_positional_args_trigger_future_warning(self):
        """Test that passing positional arguments to __init__ triggers a FutureWarning."""
        expected_warning = re.escape(
            "Passing arguments positionally to MockRecordingInterface.__init__() is deprecated "
            "and will be removed in June 2026 or after. "
            "The following arguments were passed positionally: ['num_channels']. "
            "Please use keyword arguments instead."
        )
        with pytest.warns(FutureWarning, match=expected_warning):
            MockRecordingInterface(2)  # num_channels as positional

    def test_init_keyword_args_no_future_warning(self):
        """Test that passing keyword arguments to __init__ does not trigger FutureWarning."""
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            MockRecordingInterface(num_channels=2, durations=(0.1,))

        future_warnings = [w for w in caught_warnings if issubclass(w.category, FutureWarning)]
        assert len(future_warnings) == 0

    def test_init_too_many_positional_args_raises_error(self):
        """Test that passing too many positional arguments to __init__ raises TypeError.

        Since *args allows an arbitrary number of positional arguments, we must explicitly
        check and raise TypeError when too many are passed.
        """
        expected_msg = re.escape(
            "MockRecordingInterface.__init__() takes at most 8 positional arguments but 9 were given. "
            "Note: Positional arguments are deprecated and will be removed in June 2026 or after. Please use keyword arguments."
        )
        with pytest.raises(TypeError, match=expected_msg):
            MockRecordingInterface(4, 30_000.0, (1.0,), 0, False, "ElectricalSeries", False, "extra")
