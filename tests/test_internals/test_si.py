import unittest
from unittest.mock import Mock
from pathlib import Path
from datetime import datetime

import psutil
import numpy as np

from pynwb import NWBHDF5IO, NWBFile
import pynwb.ecephys
from spikeinterface.core.testing_tools import generate_recording, generate_sorting
from spikeinterface.extractors import NumpyRecording
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.testing import TestCase


from neuroconv.tools.spikeinterface import (
    get_nwb_metadata,
    write_recording,
    write_sorting,
    check_if_recording_traces_fit_into_memory,
    add_electrodes,
    add_electrical_series,
    add_units_table,
)
from neuroconv.tools.spikeinterface.spikeinterfacerecordingdatachunkiterator import (
    SpikeInterfaceRecordingDataChunkIterator,
)
from neuroconv.utils import FilePathType
from neuroconv.tools.nwb_helpers import get_module

testing_session_time = datetime.now().astimezone()


class TestAddElectricalSeriesWriting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.num_channels = 3
        cls.sampling_frequency = 1.0
        cls.durations = [3.0]  # 3 samples in the recorder
        cls.test_recording_extractor = generate_recording(
            sampling_frequency=cls.sampling_frequency, num_channels=cls.num_channels, durations=cls.durations
        )

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )

    def test_default_values(self):

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        assert "ElectricalSeries_raw" in acquisition_module
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        assert isinstance(electrical_series.data, H5DataIO)

        compression_parameters = electrical_series.data.get_io_params()
        assert compression_parameters["compression"] == "gzip"
        assert compression_parameters["compression_opts"] == 4

        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_as_lfp(self):
        write_as = "lfp"
        add_electrical_series(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
        )

        processing_module = self.nwbfile.processing
        assert "ecephys" in processing_module

        ecephys_module = processing_module["ecephys"]
        assert "LFP" in ecephys_module.data_interfaces

        lfp_container = ecephys_module.data_interfaces["LFP"]
        assert isinstance(lfp_container, pynwb.ecephys.LFP)
        assert "ElectricalSeries_lfp" in lfp_container.electrical_series

        electrical_series = lfp_container.electrical_series["ElectricalSeries_lfp"]
        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_as_processing(self):
        write_as = "processed"
        add_electrical_series(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
        )

        processing_module = self.nwbfile.processing
        assert "ecephys" in processing_module

        ecephys_module = processing_module["ecephys"]
        assert "Processed" in ecephys_module.data_interfaces

        filtered_ephys_container = ecephys_module.data_interfaces["Processed"]
        assert isinstance(filtered_ephys_container, pynwb.ecephys.FilteredEphys)
        assert "ElectricalSeries_processed" in filtered_ephys_container.electrical_series

        electrical_series = filtered_ephys_container.electrical_series["ElectricalSeries_processed"]
        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_as_assertion(self):

        write_as = "any_other_string_that_is_not_raw_lfp_or_processed"

        reg_expression = f"'write_as' should be 'raw', 'processed' or 'lfp', but instead received value {write_as}"

        with self.assertRaisesRegex(AssertionError, reg_expression):
            add_electrical_series(
                recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
            )

    def test_non_iterative_write(self):

        # Estimate num of frames required to exceed memory capabilities
        dtype = self.test_recording_extractor.get_dtype()
        element_size_in_bytes = dtype.itemsize
        num_channels = self.test_recording_extractor.get_num_channels()

        available_memory_in_bytes = psutil.virtual_memory().available

        excess = 1.5  # Of what is available in memory
        num_frames_to_overflow = (available_memory_in_bytes * excess) / (element_size_in_bytes * num_channels)

        # Mock recording extractor with as much frames as necessary to overflow memory
        mock_recorder = Mock()
        mock_recorder.get_dtype.return_value = dtype
        mock_recorder.get_num_channels.return_value = num_channels
        mock_recorder.get_num_frames.return_value = num_frames_to_overflow

        reg_expression = f"Memory error, full electrical series is (.*?) GB are available. Use iterator_type='V2'"

        with self.assertRaisesRegex(MemoryError, reg_expression):
            check_if_recording_traces_fit_into_memory(recording=mock_recorder)


class TestAddElectricalSeriesSavingTimestampsvsRates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.num_channels = 3
        cls.sampling_frequency = 1.0
        cls.durations = [3.0]  # 3 samples in the recorder

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )
        self.test_recording_extractor = generate_recording(
            sampling_frequency=self.sampling_frequency, num_channels=self.num_channels, durations=self.durations
        )

    def test_uniform_timestamps(self):
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        expected_rate = self.sampling_frequency
        extracted_rate = electrical_series.rate

        assert extracted_rate == expected_rate

    def test_non_uniform_timestamps(self):
        expected_timestamps = np.array([0.0, 2.0, 10.0])
        self.test_recording_extractor.set_times(times=expected_timestamps, with_warning=False)
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        assert electrical_series.rate is None

        extracted_timestamps = electrical_series.timestamps.data
        np.testing.assert_array_almost_equal(extracted_timestamps, expected_timestamps)


class TestAddElectricalSeriesVoltsScaling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.sampling_frequency = 1.0
        cls.num_channels = 3
        cls.num_frames = 5
        cls.channel_ids = ["a", "b", "c"]
        cls.traces_list = [np.ones(shape=(cls.num_frames, cls.num_channels))]

        # Combinations of gains and default
        cls.gains_default = [1, 1, 1]
        cls.offset_defaults = [0, 0, 0]
        cls.gains_uniform = [2, 2, 2]
        cls.offsets_uniform = [3, 3, 3]
        cls.gains_variable = [1, 2, 3]
        cls.offsets_variable = [1, 2, 3]

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )

        # Flat traces [1, 1, 1] per channel
        self.test_recording_extractor = NumpyRecording(
            self.traces_list, self.sampling_frequency, channel_ids=self.channel_ids
        )

    def test_uniform_values(self):

        gains = self.gains_default
        offsets = self.offset_defaults
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == offsets[0] * 1e-6

        # Test channel conversion vector
        channel_conversion_vector = electrical_series.channel_conversion
        np.testing.assert_array_almost_equal(channel_conversion_vector, gains)

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * channel_conversion_vector * conversion_factor_scalar + offset_scalar
        traces_data_in_volts = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=True) * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_uniform_non_default(self):

        gains = self.gains_uniform
        offsets = self.offsets_uniform
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == offsets[0] * 1e-6

        # Test channel conversion vector
        channel_conversion_vector = electrical_series.channel_conversion
        np.testing.assert_array_almost_equal(channel_conversion_vector, gains)

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * channel_conversion_vector * conversion_factor_scalar + offset_scalar
        traces_data_in_volts = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=True) * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_variable_gains(self):

        gains = self.gains_variable
        offsets = self.offsets_uniform
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == offsets[0] * 1e-6

        # Test channel conversion vector
        channel_conversion_vector = electrical_series.channel_conversion
        np.testing.assert_array_almost_equal(channel_conversion_vector, gains)

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * channel_conversion_vector * conversion_factor_scalar + offset_scalar
        traces_data_in_volts = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=True) * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_null_offsets_in_recording_extractor(self):

        gains = self.gains_default
        self.test_recording_extractor.set_channel_gains(gains=gains)

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeries_raw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == 0

        # Test channel conversion vector
        channel_conversion_vector = electrical_series.channel_conversion
        np.testing.assert_array_almost_equal(channel_conversion_vector, gains)

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * channel_conversion_vector * conversion_factor_scalar + offset_scalar
        traces_data = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=False)
        gains = self.test_recording_extractor.get_channel_gains()
        traces_data_in_micro_volts = traces_data * gains
        traces_data_in_volts = traces_data_in_micro_volts * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_variable_offsets_assertion(self):

        gains = self.gains_default
        offsets = self.offsets_variable
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        reg_expression = f"Recording extractors with heterogeneous offsets are not supported"

        with self.assertRaisesRegex(ValueError, reg_expression):
            add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)


class TestAddElectrodes(TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.num_channels = 4
        cls.base_recording = generate_recording(num_channels=cls.num_channels, durations=[3])

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )
        channel_ids = self.base_recording.get_channel_ids()
        self.recording_1 = self.base_recording.channel_slice(
            channel_ids=channel_ids, renamed_channel_ids=["a", "b", "c", "d"]
        )
        self.recording_2 = self.base_recording.channel_slice(
            channel_ids=channel_ids, renamed_channel_ids=["c", "d", "e", "f"]
        )

        self.device = self.nwbfile.create_device(name="extra_device")
        self.electrode_group = self.nwbfile.create_electrode_group(
            name="0", description="description", location="location", device=self.device
        )
        self.defaults = dict(
            x=np.nan,
            y=np.nan,
            z=np.nan,
            imp=-1.0,
            location="unknown",
            filtering="none",
            group_name="0",
        )
        self.defaults.update(group=self.electrode_group)

    def test_integer_channel_names(self):
        """Ensure channel names merge correctly after appending when channel names are integers."""
        channel_ids = self.base_recording.get_channel_ids()
        offest_channels_ids = channel_ids + 2
        recorder_with_offset_channels = self.base_recording.channel_slice(
            channel_ids=channel_ids, renamed_channel_ids=offest_channels_ids
        )

        add_electrodes(recording=self.base_recording, nwbfile=self.nwbfile)
        add_electrodes(recording=recorder_with_offset_channels, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = ["0", "1", "2", "3", "4", "5"]
        actual_channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(actual_channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_string_channel_names(self):
        """Ensure channel names merge correctly after appending when channel names are strings."""
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes(recording=self.recording_2, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = ["a", "b", "c", "d", "e", "f"]
        actual_channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(actual_channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_non_overwriting_channel_names_property(self):
        "add_electrodes function should not overwrite the recording object channel name property"
        channel_names = ["name a", "name b", "name c", "name d"]
        self.recording_1.set_property(key="channel_name", values=channel_names)
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = channel_names
        channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_common_property_extension(self):
        """Add a property for a first recording that is then extended by a second recording."""
        self.recording_1.set_property(key="common_property", values=["value_1"] * self.num_channels)
        self.recording_2.set_property(key="common_property", values=["value_2"] * self.num_channels)

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes(recording=self.recording_2, nwbfile=self.nwbfile)

        actual_properties_in_electrodes_table = list(self.nwbfile.electrodes["common_property"].data)
        expected_properties_in_electrodes_table = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(actual_properties_in_electrodes_table, expected_properties_in_electrodes_table)

    def test_new_property_addition(self):
        """Add a property only available in a second recording."""
        self.recording_2.set_property(key="added_property", values=["added_value"] * self.num_channels)

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes(recording=self.recording_2, nwbfile=self.nwbfile)

        actual_properties_in_electrodes_table = list(self.nwbfile.electrodes["added_property"].data)
        expected_properties_in_electrodes_table = ["", "", "added_value", "added_value", "added_value", "added_value"]
        self.assertListEqual(actual_properties_in_electrodes_table, expected_properties_in_electrodes_table)

    def test_manual_row_adition_before_add_electrodes_function(self):
        """Add some rows to the electrode tables before using the add_electrodes function"""
        values_dic = self.defaults

        values_dic.update(id=123)
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=124)
        self.nwbfile.add_electrode(**values_dic)

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

        expected_ids = [123, 124, 2, 3, 4, 5]
        expected_names = ["123", "124", "a", "b", "c", "d"]
        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)

    def test_manual_row_adition_after_add_electrodes_function(self):
        """Add some rows to the electrode table after using the add_electrodes function"""
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

        values_dic = self.defaults

        # Previous properties
        values_dic.update(rel_x=0.0, rel_y=0.0, id=123, channel_name=str(123))
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(rel_x=0.0, rel_y=0.0, id=124, channel_name=str(124))
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(rel_x=0.0, rel_y=0.0, id=None, channel_name="6")  # automatic ID set
        self.nwbfile.add_electrode(**values_dic)

        expected_ids = [0, 1, 2, 3, 123, 124, 6]
        expected_names = ["a", "b", "c", "d", "123", "124", "6"]
        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)

    def test_row_matching_by_channel_name_with_existing_property(self):
        """
        Adding new electrodes to an already existing electrode table should match
        properties and information by channel name.
        """
        values_dic = self.defaults
        self.nwbfile.add_electrode_column(name="channel_name", description="a string reference for the channel")
        self.nwbfile.add_electrode_column(name="property", description="exisiting property")

        values_dic.update(id=20, channel_name="c", property="value_c")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=21, channel_name="d", property="value_d")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=22, channel_name="f", property="value_f")
        self.nwbfile.add_electrode(**values_dic)

        property_values = ["value_a", "value_b", "x", "y"]
        self.recording_1.set_property(key="property", values=property_values)

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

        # Remaining ids are filled positionally.
        expected_ids = [20, 21, 22, 3, 4]
        # Properties are matched by channel name.
        expected_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "value_f", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)
        self.assertListEqual(list(self.nwbfile.electrodes["property"].data), expected_property_values)

    def test_row_matching_by_channel_name_with_new_property(self):
        """
        Adding new electrodes to an already existing electrode table should match
        properties and information by channel name.
        """
        values_dic = self.defaults
        self.nwbfile.add_electrode_column(name="channel_name", description="a string reference for the channel")

        values_dic.update(id=20, channel_name="c")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=21, channel_name="d")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=22, channel_name="f")
        self.nwbfile.add_electrode(**values_dic)

        property_values = ["value_a", "value_b", "value_c", "value_d"]
        self.recording_1.set_property(key="property", values=property_values)

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

        # Remaining ids are filled positionally.
        expected_ids = [20, 21, 22, 3, 4]
        # Properties are matched by channel name.
        expected_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)
        self.assertListEqual(list(self.nwbfile.electrodes["property"].data), expected_property_values)

    def test_assertion_for_id_collision(self):
        """
        Keep the old logic of not allowing integer channel_ids to match electrodes.table.ids
        """

        values_dic = self.defaults

        values_dic.update(id=0)
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=1)
        self.nwbfile.add_electrode(**values_dic)
        # The self.base_recording channel_ids are [0, 1, 2, 3]
        with self.assertRaisesWith(exc_type=ValueError, exc_msg="id 0 already in the table"):
            add_electrodes(recording=self.base_recording, nwbfile=self.nwbfile)


class TestAddUnitsTable(TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.num_units = 4
        cls.base_sorting = generate_sorting(num_units=cls.num_units, durations=[3])
        # Base sorting unit ids are [0, 1, 2, 3]

    def setUp(self):
        """Start with a fresh NWBFile, and remapped sorters each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )
        unit_ids = self.base_sorting.get_unit_ids()
        self.sorting_1 = self.base_sorting.select_units(unit_ids=unit_ids, renamed_unit_ids=["a", "b", "c", "d"])
        self.sorting_2 = self.base_sorting.select_units(unit_ids=unit_ids, renamed_unit_ids=["c", "d", "e", "f"])

        self.defaults = dict(spike_times=[1, 1, 1])

    def test_integer_unit_names(self):
        """Ensure add units_table gets the right units name for integer units ids."""
        add_units_table(sorting=self.base_sorting, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["0", "1", "2", "3"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_string_unit_names(self):
        """Ensure add_units_table gets the right units name for string units ids"""
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["a", "b", "c", "d"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_non_overwriting_unit_names_sorting_property(self):
        "add_units_table function should not ovewrtie the sorting object unit_name property"
        unit_names = ["name a", "name b", "name c", "name d"]
        self.sorting_1.set_property(key="unit_name", values=unit_names)
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = unit_names
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_integer_unit_names_overwrite(self):
        """Ensure unit names merge correctly after appending when unit names are integers."""
        unit_ids = self.base_sorting.get_unit_ids()
        offest_units_ids = unit_ids + 2
        sorting_with_offset_unit_ids = self.base_sorting.select_units(
            unit_ids=unit_ids, renamed_unit_ids=offest_units_ids
        )

        add_units_table(sorting=self.base_sorting, nwbfile=self.nwbfile)
        add_units_table(sorting=sorting_with_offset_unit_ids, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["0", "1", "2", "3", "4", "5"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_string_unit_names_overwrite(self):
        """Ensure unit names merge correctly after appending when channel names are strings."""
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table(sorting=self.sorting_2, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["a", "b", "c", "d", "e", "f"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_non_overwriting_unit_names_sorting_property(self):
        "add_units_table function should not ovewrtie the sorting object unit_name property"
        unit_names = ["name a", "name b", "name c", "name d"]
        self.sorting_1.set_property(key="unit_name", values=unit_names)
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = unit_names
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_common_property_extension(self):
        """Add a property for a first sorting that is then extended by a second sorting."""
        self.sorting_1.set_property(key="common_property", values=["value_1"] * self.num_units)
        self.sorting_2.set_property(key="common_property", values=["value_2"] * self.num_units)

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table(sorting=self.sorting_2, nwbfile=self.nwbfile)

        properties_in_units_table = list(self.nwbfile.units["common_property"].data)
        expected_properties_in_units_table = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(properties_in_units_table, expected_properties_in_units_table)

    def test_property_addition(self):
        """Add a property only available in a second sorting."""
        self.sorting_2.set_property(key="added_property", values=["added_value"] * self.num_units)

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table(sorting=self.sorting_2, nwbfile=self.nwbfile)

        properties_in_units_table = list(self.nwbfile.units["added_property"].data)
        expected_properties_in_units_table = ["", "", "added_value", "added_value", "added_value", "added_value"]
        self.assertListEqual(properties_in_units_table, expected_properties_in_units_table)

    def test_units_table_extension_after_manual_unit_addition(self):
        """Add some rows to the units tables before using the add_units_table function"""
        values_dic = self.defaults

        values_dic.update(id=123, spike_times=[0, 1, 2])
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=124, spike_times=[2, 3, 4])
        self.nwbfile.add_unit(**values_dic)

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_units_ids = [123, 124, 2, 3, 4, 5]
        expected_unit_names = ["123", "124", "a", "b", "c", "d"]
        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)

    def test_manual_extension_after_add_units_table(self):
        """Add some units to the units table after using the add_units_table function"""

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        values_dic = self.defaults

        # Previous properties
        values_dic.update(id=123, unit_name=str(123))
        self.nwbfile.units.add_unit(**values_dic)

        values_dic.update(id=124, unit_name=str(124))
        self.nwbfile.units.add_unit(**values_dic)

        values_dic.update(id=None, unit_name="6")  # automatic ID set
        self.nwbfile.units.add_unit(**values_dic)

        expected_unit_ids = [0, 1, 2, 3, 123, 124, 6]
        expected_unit_names = ["a", "b", "c", "d", "123", "124", "6"]
        self.assertListEqual(list(self.nwbfile.units.id.data), expected_unit_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)

    def test_property_matching_by_unit_name_with_existing_property(self):
        """
        Add some units to the units tables before using the add_units_table function.
        Previous properties that are also available in the sorting are matched with unit_name
        """

        values_dic = self.defaults

        self.nwbfile.add_unit_column(name="unit_name", description="a string reference for the unit")
        self.nwbfile.add_unit_column(name="property", description="property_added_before")

        values_dic.update(id=20, unit_name="c", property="value_c")
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=21, unit_name="d", property="value_d")
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=22, unit_name="f", property="value_f")
        self.nwbfile.add_unit(**values_dic)

        property_values = ["value_a", "value_b", "x", "y"]
        self.sorting_1.set_property(key="property", values=property_values)

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        # Properties correspond with unit names, ids are filled positionally
        expected_units_ids = [20, 21, 22, 3, 4]
        expected_unit_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "value_f", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)
        self.assertListEqual(list(self.nwbfile.units["property"].data), expected_property_values)

    def test_property_matching_by_unit_name_with_new_property(self):
        """
        Add some units to the units tables before using the add_units_table function.
        New properties in the sorter are matched by unit name
        """

        values_dic = self.defaults

        self.nwbfile.add_unit_column(name="unit_name", description="a string reference for the unit")

        values_dic.update(id=20, unit_name="c")
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=21, unit_name="d")
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=22, unit_name="f")
        self.nwbfile.add_unit(**values_dic)

        property_values = ["value_a", "value_b", "value_c", "value_d"]
        self.sorting_1.set_property(key="property", values=property_values)

        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)

        # Properties correspond with unit names, ids are filled positionally
        expected_units_ids = [20, 21, 22, 3, 4]
        expected_unit_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)
        self.assertListEqual(list(self.nwbfile.units["property"].data), expected_property_values)

    def test_id_collision_assertion(self):
        """
        Add some units to the units table before using the add_units_table function.
        In this case there is are some common ids between the manually added units and the sorting ids which causes
        collisions. That is, if the units ids in the sorter integer it is required for them to be different from the
        ids already in the table.
        """

        values_dic = self.defaults

        values_dic.update(id=0)
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=1)
        self.nwbfile.add_unit(**values_dic)
        # The self.base_sorting unit_ids are [0, 1, 2, 3]
        with self.assertRaisesWith(exc_type=ValueError, exc_msg="id 0 already in the table"):
            add_units_table(sorting=self.base_sorting, nwbfile=self.nwbfile)

    def test_write_units_table_in_processing_module(self):
        """ """

        units_table_name = "testing_processing"
        unit_table_description = "testing_description"
        add_units_table(
            sorting=self.base_sorting,
            nwbfile=self.nwbfile,
            units_table_name=units_table_name,
            unit_table_description=unit_table_description,
            write_in_processing_module=True,
        )

        ecephys_mod = get_module(
            nwbfile=self.nwbfile,
            name="ecephys",
            description="Intermediate data from extracellular electrophysiology recordings, e.g., LFP.",
        )
        self.assertIn(units_table_name, ecephys_mod.data_interfaces)
        units_table = ecephys_mod[units_table_name]
        self.assertEqual(units_table.name, units_table_name)
        self.assertEqual(units_table.description, unit_table_description)


if __name__ == "__main__":
    unittest.main()
