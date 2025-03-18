import re
import unittest
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import numpy as np
import psutil
import pynwb.ecephys
import pytest
from hdmf.testing import TestCase
from pynwb import NWBFile
from pynwb.testing.mock.file import mock_NWBFile
from spikeinterface.core.generate import (
    generate_ground_truth_recording,
    generate_recording,
    generate_sorting,
)
from spikeinterface.extractors import NumpyRecording

from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.spikeinterface import (
    add_electrical_series_to_nwbfile,
    add_electrode_groups_to_nwbfile,
    add_electrodes_to_nwbfile,
    add_recording_to_nwbfile,
    add_sorting_to_nwbfile,
    add_units_table_to_nwbfile,
    check_if_recording_traces_fit_into_memory,
    write_recording_to_nwbfile,
    write_sorting_analyzer_to_nwbfile,
)
from neuroconv.tools.spikeinterface.spikeinterfacerecordingdatachunkiterator import (
    SpikeInterfaceRecordingDataChunkIterator,
)

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
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        assert "ElectricalSeriesRaw" in acquisition_module
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_as_lfp(self):
        write_as = "lfp"
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
        )

        processing_module = self.nwbfile.processing
        assert "ecephys" in processing_module

        ecephys_module = processing_module["ecephys"]
        assert "LFP" in ecephys_module.data_interfaces

        lfp_container = ecephys_module.data_interfaces["LFP"]
        assert isinstance(lfp_container, pynwb.ecephys.LFP)
        assert "ElectricalSeriesLFP" in lfp_container.electrical_series

        electrical_series = lfp_container.electrical_series["ElectricalSeriesLFP"]
        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_as_processing(self):
        write_as = "processed"
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
        )

        processing_module = self.nwbfile.processing
        assert "ecephys" in processing_module

        ecephys_module = processing_module["ecephys"]
        assert "Processed" in ecephys_module.data_interfaces

        filtered_ephys_container = ecephys_module.data_interfaces["Processed"]
        assert isinstance(filtered_ephys_container, pynwb.ecephys.FilteredEphys)
        assert "ElectricalSeriesProcessed" in filtered_ephys_container.electrical_series

        electrical_series = filtered_ephys_container.electrical_series["ElectricalSeriesProcessed"]
        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_multiple_electrical_series_from_same_electrode_group(self):
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="raw series"),
                ElectricalSeriesLFP=dict(name="ElectricalSeriesLFP", description="lfp series"),
            )
        )
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw",
            iterator_type=None,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)

        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesLFP",
            iterator_type=None,
        )
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesLFP", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))

    def test_write_multiple_electrical_series_with_different_electrode_groups(self):
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw1=dict(name="ElectricalSeriesRaw1", description="raw series"),
                ElectricalSeriesRaw2=dict(name="ElectricalSeriesRaw2", description="lfp series"),
            )
        )
        original_groups = self.test_recording_extractor.get_channel_groups()
        self.test_recording_extractor.set_channel_groups(["group0"] * len(self.test_recording_extractor.channel_ids))
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw1",
            iterator_type=None,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        # check channel names and group names
        electrodes = self.nwbfile.acquisition["ElectricalSeriesRaw1"].electrodes[:]
        np.testing.assert_equal(electrodes["channel_name"], self.test_recording_extractor.channel_ids.astype("str"))
        np.testing.assert_equal(
            electrodes["group_name"], self.test_recording_extractor.get_channel_groups().astype("str")
        )
        # set new channel groups to create a new  electrode_group
        self.test_recording_extractor.set_channel_groups(["group1"] * len(self.test_recording_extractor.channel_ids))
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw2",
            iterator_type=None,
        )
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesRaw2", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), 2 * len(self.test_recording_extractor.channel_ids))
        # check channel names and group names
        electrodes = self.nwbfile.acquisition["ElectricalSeriesRaw2"].electrodes[:]
        np.testing.assert_equal(electrodes["channel_name"], self.test_recording_extractor.channel_ids.astype("str"))
        np.testing.assert_equal(
            electrodes["group_name"], self.test_recording_extractor.get_channel_groups().astype("str")
        )

        self.test_recording_extractor.set_channel_groups(original_groups)

    def test_invalid_write_as_argument_assertion(self):
        write_as = "any_other_string_that_is_not_raw_lfp_or_processed"

        reg_expression = f"'write_as' should be 'raw', 'processed' or 'lfp', but instead received value {write_as}"

        with self.assertRaisesRegex(AssertionError, reg_expression):
            add_electrical_series_to_nwbfile(
                recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
            )


class TestAddElectricalSeriesSavingTimestampsVsRates(unittest.TestCase):
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
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        expected_rate = self.sampling_frequency
        extracted_rate = electrical_series.rate

        assert extracted_rate == expected_rate

    def test_non_uniform_timestamps(self):
        expected_timestamps = np.array([0.0, 2.0, 10.0])
        self.test_recording_extractor.set_times(times=expected_timestamps, with_warning=False)
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

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

        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == offsets[0] * 1e-6

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * conversion_factor_scalar + offset_scalar
        traces_data_in_volts = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=True) * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_uniform_non_default(self):
        gains = self.gains_uniform
        offsets = self.offsets_uniform
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 2e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == offsets[0] * 1e-6

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * conversion_factor_scalar + offset_scalar
        traces_data_in_volts = self.test_recording_extractor.get_traces(segment_index=0, return_scaled=True) * 1e-6
        np.testing.assert_array_almost_equal(data_in_volts, traces_data_in_volts)

    def test_variable_gains(self):
        gains = self.gains_variable
        offsets = self.offsets_uniform
        self.test_recording_extractor.set_channel_gains(gains=gains)
        self.test_recording_extractor.set_channel_offsets(offsets=offsets)

        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

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

        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        # Test conversion factor
        conversion_factor_scalar = electrical_series.conversion
        assert conversion_factor_scalar == 1e-6

        # Test offset scalar
        offset_scalar = electrical_series.offset
        assert offset_scalar == 0

        # Test equality of data in Volts. Data in spikeextractors is in microvolts when scaled
        extracted_data = electrical_series.data[:]
        data_in_volts = extracted_data * conversion_factor_scalar + offset_scalar
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

        reg_expression = "Recording extractors with heterogeneous offsets are not supported"

        with self.assertRaisesRegex(ValueError, reg_expression):
            add_electrical_series_to_nwbfile(
                recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
            )


def test_error_with_multiple_offset():
    # Generate a mock recording with 5 channels and 1 second duration
    recording = generate_recording(num_channels=5, durations=[1.0])
    # Rename channels to specific identifiers for clarity in error messages
    recording = recording.rename_channels(new_channel_ids=["a", "b", "c", "d", "e"])
    # Set different offsets for the channels
    recording.set_channel_offsets(offsets=[0, 0, 1, 1, 2])

    # Create a mock NWBFile object
    nwbfile = mock_NWBFile()

    # Expected error message
    expected_message_lines = [
        "Recording extractors with heterogeneous offsets are not supported.",
        "Multiple offsets were found per channel IDs:",
        "  Offset 0: Channel IDs ['a', 'b']",
        "  Offset 1: Channel IDs ['c', 'd']",
        "  Offset 2: Channel IDs ['e']",
    ]
    expected_message = "\n".join(expected_message_lines)

    # Use re.escape to escape any special regex characters in the expected message
    expected_message_regex = re.escape(expected_message)

    # Attempt to add electrical series to the NWB file
    # Expecting a ValueError due to multiple offsets, matching the expected message
    with pytest.raises(ValueError, match=expected_message_regex):
        add_electrical_series_to_nwbfile(recording=recording, nwbfile=nwbfile)


class TestAddElectricalSeriesChunking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.sampling_frequency = 1.0
        cls.num_channels = 3
        cls.num_frames = 20
        cls.channel_ids = ["a", "b", "c"]
        cls.traces_list = [np.ones(shape=(cls.num_frames, cls.num_channels))]
        # Flat traces [1, 1, 1] per channel
        cls.test_recording_extractor = NumpyRecording(
            cls.traces_list, cls.sampling_frequency, channel_ids=cls.channel_ids
        )

        # Combinations of gains and default
        cls.gains_default = [2, 2, 2]
        cls.offset_default = [1, 1, 1]

        cls.test_recording_extractor.set_channel_gains(gains=cls.gains_default)
        cls.test_recording_extractor.set_channel_offsets(offsets=cls.offset_default)

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""

        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )

    def test_default_iterative_writer(self):
        add_electrical_series_to_nwbfile(recording=self.test_recording_extractor, nwbfile=self.nwbfile)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        electrical_series_data_iterator = electrical_series.data

        assert isinstance(electrical_series_data_iterator, SpikeInterfaceRecordingDataChunkIterator)

        extracted_data = np.concatenate([data_chunk.data for data_chunk in electrical_series_data_iterator])
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_iterator_opts_propagation(self):
        iterator_opts = dict(chunk_shape=(10, 3))
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_opts=iterator_opts
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        electrical_series_data_iterator = electrical_series.data

        assert electrical_series_data_iterator.chunk_shape == iterator_opts["chunk_shape"]

    def test_non_iterative_write(self):
        add_electrical_series_to_nwbfile(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        isinstance(electrical_series.data, np.ndarray)

    def test_non_iterative_write_assertion(self):
        # Estimate num of frames required to exceed memory capabilities
        dtype = self.test_recording_extractor.get_dtype()
        element_size_in_bytes = dtype.itemsize
        num_channels = self.test_recording_extractor.get_num_channels()

        available_memory_in_bytes = psutil.virtual_memory().available

        excess = 1.5  # Of what is available in memory
        num_frames_to_overflow = (available_memory_in_bytes * excess) / (element_size_in_bytes * num_channels)

        # Mock recording extractor with as many frames as necessary to overflow memory
        mock_recorder = Mock()
        mock_recorder.get_dtype.return_value = dtype
        mock_recorder.get_num_channels.return_value = num_channels
        mock_recorder.get_num_frames.return_value = num_frames_to_overflow

        reg_expression = "Memory error, full electrical series is (.*?) GiB are available. Use iterator_type='V2'"

        with self.assertRaisesRegex(MemoryError, reg_expression):
            check_if_recording_traces_fit_into_memory(recording=mock_recorder)

    def test_invalid_iterator_type_assertion(self):
        iterator_type = "invalid_iterator_type"

        reg_expression = "iterator_type (.*?)"
        with self.assertRaisesRegex(ValueError, reg_expression):
            add_electrical_series_to_nwbfile(
                recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=iterator_type
            )


class TestWriteRecording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 3 samples in each segment
        cls.num_channels = 3
        cls.sampling_frequency = 1.0
        cls.single_segment_recording_extractor = generate_recording(
            sampling_frequency=cls.sampling_frequency, num_channels=cls.num_channels, durations=[3.0]
        )
        cls.multiple_segment_recording_extractor = generate_recording(
            sampling_frequency=cls.sampling_frequency, num_channels=cls.num_channels, durations=[3.0, 3.0]
        )

        # Add gains and offsets
        cls.gains_default = [1, 1, 1]
        cls.offset_default = [0, 0, 0]

        cls.single_segment_recording_extractor.set_channel_gains(cls.gains_default)
        cls.single_segment_recording_extractor.set_channel_offsets(cls.offset_default)

        cls.multiple_segment_recording_extractor.set_channel_gains(cls.gains_default)
        cls.multiple_segment_recording_extractor.set_channel_offsets(cls.offset_default)

    def setUp(self):
        """Start with a fresh NWBFile, ElectrodeTable, and remapped BaseRecordings each time."""

        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )

    def test_default_values_single_segment(self):
        """This test that the names are written appropriately for the single segment case (numbers not added)"""
        write_recording_to_nwbfile(
            recording=self.single_segment_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        assert "ElectricalSeriesRaw" in acquisition_module
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        extracted_data = electrical_series.data[:]
        expected_data = self.single_segment_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_multiple_segments(self):
        write_recording_to_nwbfile(
            recording=self.multiple_segment_recording_extractor, nwbfile=self.nwbfile, iterator_type=None
        )

        acquisition_module = self.nwbfile.acquisition
        assert len(acquisition_module) == 2

        assert "ElectricalSeriesRaw0" in acquisition_module
        assert "ElectricalSeriesRaw1" in acquisition_module

        electrical_series0 = acquisition_module["ElectricalSeriesRaw0"]
        extracted_data = electrical_series0.data[:]
        expected_data = self.multiple_segment_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

        electrical_series1 = acquisition_module["ElectricalSeriesRaw1"]
        extracted_data = electrical_series1.data[:]
        expected_data = self.multiple_segment_recording_extractor.get_traces(segment_index=1)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_bool_properties(self):
        """ """
        bool_property = np.array([False] * len(self.single_segment_recording_extractor.channel_ids))
        bool_property[::2] = True
        self.single_segment_recording_extractor.set_property("test_bool", bool_property)
        add_electrodes_to_nwbfile(
            recording=self.single_segment_recording_extractor,
            nwbfile=self.nwbfile,
        )
        self.assertIn("test_bool", self.nwbfile.electrodes.colnames)
        assert all(tb in [False, True] for tb in self.nwbfile.electrodes["test_bool"][:])


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
        self.recording_1 = self.base_recording.rename_channels(new_channel_ids=["a", "b", "c", "d"])
        self.recording_2 = self.base_recording.rename_channels(new_channel_ids=["c", "d", "e", "f"])

        self.device = self.nwbfile.create_device(name="extra_device")
        self.electrode_group = self.nwbfile.create_electrode_group(
            name="0", description="description", location="location", device=self.device
        )
        self.defaults = dict(
            group=self.electrode_group,
            group_name="0",
            location="unknown",
        )

    def test_default_electrode_column_names(self):
        add_electrodes_to_nwbfile(recording=self.base_recording, nwbfile=self.nwbfile)

        expected_electrode_column_names = ["location", "group", "group_name", "channel_name", "rel_x", "rel_y"]
        actual_electrode_column_names = list(self.nwbfile.electrodes.colnames)
        self.assertCountEqual(actual_electrode_column_names, expected_electrode_column_names)

    def test_integer_channel_names(self):
        """Ensure channel names merge correctly after appending when channel names are integers."""
        channel_ids = self.base_recording.get_channel_ids()
        channel_ids_with_offset = [int(channel_id) + 2 for channel_id in channel_ids]
        recorder_with_offset_channels = self.base_recording.rename_channels(new_channel_ids=channel_ids_with_offset)

        add_electrodes_to_nwbfile(recording=self.base_recording, nwbfile=self.nwbfile)
        add_electrodes_to_nwbfile(recording=recorder_with_offset_channels, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = ["0", "1", "2", "3", "4", "5"]
        actual_channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(actual_channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_string_channel_names(self):
        """Ensure channel names merge correctly after appending when channel names are strings."""
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = ["a", "b", "c", "d", "e", "f"]
        actual_channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(actual_channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_non_overwriting_channel_names_property(self):
        "add_electrodes_to_nwbfile function should not overwrite the recording object channel name property"
        channel_names = ["name a", "name b", "name c", "name d"]
        self.recording_1.set_property(key="channel_name", values=channel_names)
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        expected_channel_names_in_electrodes_table = channel_names
        channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)

    def test_channel_group_names_table(self):
        "add_electrodes_to_nwbfile function should add new rows if same channel names, but different group_names"
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        original_groups = self.recording_1.get_channel_groups()
        self.recording_1.set_channel_groups(["1"] * len(self.recording_1.channel_ids))
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        # reset channel_groups
        self.recording_1.set_channel_groups(original_groups)
        assert len(self.nwbfile.electrodes) == 2 * len(self.recording_1.channel_ids)
        expected_channel_names_in_electrodes_table = list(self.recording_1.channel_ids) + list(
            self.recording_1.channel_ids
        )
        channel_names_in_electrodes_table = list(self.nwbfile.electrodes["channel_name"].data)
        self.assertListEqual(channel_names_in_electrodes_table, expected_channel_names_in_electrodes_table)
        group_names_in_electrodes_table = list(self.nwbfile.electrodes["group_name"].data)
        self.assertEqual(len(np.unique(group_names_in_electrodes_table)), 2)

    def test_common_property_extension(self):
        """Add a property for a first recording that is then extended by a second recording."""
        self.recording_1.set_property(key="common_property", values=["value_1"] * self.num_channels)
        self.recording_2.set_property(key="common_property", values=["value_2"] * self.num_channels)

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        actual_properties_in_electrodes_table = list(self.nwbfile.electrodes["common_property"].data)
        expected_properties_in_electrodes_table = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(actual_properties_in_electrodes_table, expected_properties_in_electrodes_table)

    def test_add_electrodes_addition_to_nwbfile(self):
        """
        Keep the old logic of not allowing integer channel_ids to match electrodes.table.ids
        """
        self.nwbfile.add_electrode_column("channel_name", description="channel_name")
        values_dic = self.defaults

        values_dic.update(id=0, channel_name="0")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=1, channel_name="1")
        self.nwbfile.add_electrode(**values_dic)
        # The self.base_recording channel_ids are [0, 1, 2, 3], so only '3' and '4' should be added
        add_electrodes_to_nwbfile(recording=self.base_recording, nwbfile=self.nwbfile)
        self.assertEqual(len(self.nwbfile.electrodes), len(self.base_recording.channel_ids))

    def test_new_property_addition(self):
        """Add a property only available in a second recording."""
        self.recording_2.set_property(key="added_property", values=["added_value"] * self.num_channels)

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        actual_properties_in_electrodes_table = list(self.nwbfile.electrodes["added_property"].data)
        expected_properties_in_electrodes_table = ["", "", "added_value", "added_value", "added_value", "added_value"]
        self.assertListEqual(actual_properties_in_electrodes_table, expected_properties_in_electrodes_table)

    def test_manual_row_adition_before_add_electrodes_function_to_nwbfile(self):
        """Add some rows to the electrode tables before using the add_electrodes_to_nwbfile function"""
        values_dic = self.defaults

        values_dic.update(id=123)
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=124)
        self.nwbfile.add_electrode(**values_dic)

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        expected_ids = [123, 124, 2, 3, 4, 5]
        expected_names = ["123", "124", "a", "b", "c", "d"]
        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)

    def test_manual_row_adition_after_add_electrodes_function_to_nwbfile(self):
        """Add some rows to the electrode table after using the add_electrodes_to_nwbfile function"""
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

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

    def test_manual_row_adition_before_add_electrodes_function_optional_columns_to_nwbfile(self):
        """Add some rows including optional columns to the electrode tables before using the add_electrodes_to_nwbfile function."""
        values_dic = self.defaults

        values_dic.update(id=123)
        self.nwbfile.add_electrode(**values_dic, x=0.0, y=1.0, z=2.0)

        values_dic.update(id=124)
        self.nwbfile.add_electrode(**values_dic, x=1.0, y=2.0, z=3.0)

        # recording_1 does not have x, y, z positions
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        expected_ids = [123, 124, 2, 3, 4, 5]
        expected_x = [0, 1, np.nan, np.nan, np.nan, np.nan]
        expected_y = [1, 2, np.nan, np.nan, np.nan, np.nan]
        expected_z = [2, 3, np.nan, np.nan, np.nan, np.nan]
        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["x"].data), expected_x)
        self.assertListEqual(list(self.nwbfile.electrodes["y"].data), expected_y)
        self.assertListEqual(list(self.nwbfile.electrodes["z"].data), expected_z)

    def test_row_matching_by_channel_name_with_existing_property(self):
        """
        Adding new electrodes to an already existing electrode table should match
        properties and information by channel name.
        """
        values_dic = self.defaults
        self.nwbfile.add_electrode_column(name="channel_name", description="a string reference for the channel")
        self.nwbfile.add_electrode_column(name="property", description="existing property")

        values_dic.update(id=20, channel_name="c", property="value_c")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=21, channel_name="d", property="value_d")
        self.nwbfile.add_electrode(**values_dic)

        values_dic.update(id=22, channel_name="f", property="value_f")
        self.nwbfile.add_electrode(**values_dic)

        property_values = ["value_a", "value_b", "x", "y"]
        self.recording_1.set_property(key="property", values=property_values)

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        # Remaining ids are filled positionally.
        expected_ids = [20, 21, 22, 3, 4]
        # Properties are matched by channel name.
        expected_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "value_f", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)
        self.assertListEqual(list(self.nwbfile.electrodes["property"].data), expected_property_values)

    def test_adding_new_property_with_identifical_channels_but_different_groups(self):

        recording1 = generate_recording(num_channels=3)
        recording1 = recording1.rename_channels(new_channel_ids=["a", "b", "c"])
        recording1.set_property(key="group_name", values=["group1"] * 3)
        recording2 = generate_recording(num_channels=3)
        recording2 = recording2.rename_channels(new_channel_ids=["a", "b", "c"])
        recording2.set_property(key="group_name", values=["group2"] * 3)

        recording2.set_property(key="added_property", values=["value"] * 3)

        add_electrodes_to_nwbfile(recording=recording1, nwbfile=self.nwbfile)
        add_electrodes_to_nwbfile(recording=recording2, nwbfile=self.nwbfile)

        expected_property = ["", "", "", "value", "value", "value"]
        property = self.nwbfile.electrodes["added_property"].data

        assert np.array_equal(property, expected_property)

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

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        # Remaining ids are filled positionally.
        expected_ids = [20, 21, 22, 3, 4]
        # Properties are matched by channel name.
        expected_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.electrodes.id.data), expected_ids)
        self.assertListEqual(list(self.nwbfile.electrodes["channel_name"].data), expected_names)
        self.assertListEqual(list(self.nwbfile.electrodes["property"].data), expected_property_values)

    def test_adding_ragged_array_properties(self):

        ragged_array_values1 = [[1, 2], [3, 4], [5, 6], [7, 8]]
        self.recording_1.set_property(key="ragged_property", values=ragged_array_values1)
        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)

        written_values = self.nwbfile.electrodes.to_dataframe()["ragged_property"].to_list()
        np.testing.assert_array_equal(written_values, ragged_array_values1)

        # Add a new recording that contains more properties for the ragged array
        ragged_array_values2 = [[5, 6], [7, 8], [9, 10], [11, 12]]
        self.recording_2.set_property(key="ragged_property", values=ragged_array_values2)
        second_ragged_array_values = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"], ["j", "k", "l"]]
        self.recording_2.set_property(key="ragged_property2", values=second_ragged_array_values)

        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        written_values = self.nwbfile.electrodes.to_dataframe()["ragged_property"].to_list()
        expected_values = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]]
        np.testing.assert_array_equal(written_values, expected_values)

        written_values = self.nwbfile.electrodes.to_dataframe()["ragged_property2"].to_list()
        values_appended_to_table = [[], []]
        expected_values = values_appended_to_table + second_ragged_array_values

        # We need a for loop because this is a non-homogenous ragged array
        for i, value in enumerate(written_values):
            np.testing.assert_array_equal(value, expected_values[i])

    def test_adding_doubled_ragged_arrays(self):

        # Simple test for a double ragged array
        doubled_nested_array1 = [
            [[1, 2], [3, 4]],
            [[5, 6], [7, 8]],
            [[9, 10], [11, 12]],
            [[13, 14], [15, 16]],
        ]
        self.recording_1.set_property(key="double_ragged_property", values=doubled_nested_array1)

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile)
        written_values = self.nwbfile.electrodes.to_dataframe()["double_ragged_property"].to_list()
        np.testing.assert_array_equal(written_values, doubled_nested_array1)

        # Add a new recording that contains a continuation of the previous double ragged array
        # There is overlapping in the channel names
        doubled_nested_array2 = [
            [[9, 10], [11, 12]],
            [[13, 14], [15, 16]],
            [[17, 18], [19, 20]],
            [[21, 22], [23, 24]],
        ]
        self.recording_2.set_property(key="double_ragged_property", values=doubled_nested_array2)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        written_values = self.nwbfile.electrodes.to_dataframe()["double_ragged_property"].to_list()

        # Note this adds a combination of both arrays
        expected_values = [
            [[1, 2], [3, 4]],
            [[5, 6], [7, 8]],
            [[9, 10], [11, 12]],
            [[13, 14], [15, 16]],
            [[17, 18], [19, 20]],
            [[21, 22], [23, 24]],
        ]

        np.testing.assert_array_equal(written_values, expected_values)

        second_doubled_nested_array = [
            [["a", "b", "c"], ["d", "e", "f"]],
            [["g", "h", "i"], ["j", "k", "l"]],
            [["m", "n", "o"], ["p", "q", "r"]],
            [["s", "t", "u"], ["v", "w", "x"]],
        ]

        # We add another property to recording 2 which is not in recording 1
        self.recording_2.set_property(key="double_ragged_property2", values=second_doubled_nested_array)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile)

        written_values = self.nwbfile.electrodes.to_dataframe()["double_ragged_property2"].to_list()

        values_appended_to_table = [
            [],
            [],
        ]

        expected_values = values_appended_to_table + second_doubled_nested_array
        # We need a for loop because this is a non-homogenous ragged array
        for i, value in enumerate(written_values):
            np.testing.assert_array_equal(value, expected_values[i])

    def test_property_metadata_mismatch(self):
        """
        Adding recordings that do not contain all properties described in
        metadata should not error.
        """
        self.recording_1.set_property(key="common_property", values=["value_1"] * self.num_channels)
        self.recording_2.set_property(key="common_property", values=["value_2"] * self.num_channels)
        self.recording_1.set_property(key="property_1", values=[f"value_{n+1}" for n in range(self.num_channels)])
        self.recording_2.set_property(key="property_2", values=[f"value_{n+1}" for n in range(self.num_channels)])

        metadata = dict(
            Ecephys=dict(
                Electrodes=[
                    dict(name="common_property", description="no description."),
                    dict(name="property_1", description="no description."),
                    dict(name="property_2", description="no description."),
                ]
            )
        )

        add_electrodes_to_nwbfile(recording=self.recording_1, nwbfile=self.nwbfile, metadata=metadata)
        add_electrodes_to_nwbfile(recording=self.recording_2, nwbfile=self.nwbfile, metadata=metadata)

        actual_common_property_values = list(self.nwbfile.electrodes["common_property"].data)
        expected_common_property_values = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(actual_common_property_values, expected_common_property_values)

        actual_property_1_values = list(self.nwbfile.electrodes["property_1"].data)
        expected_property_1_values = ["value_1", "value_2", "value_3", "value_4", "", ""]
        self.assertListEqual(actual_property_1_values, expected_property_1_values)

        actual_property_2_values = list(self.nwbfile.electrodes["property_2"].data)
        expected_property_2_values = ["", "", "value_1", "value_2", "value_3", "value_4"]
        self.assertListEqual(actual_property_2_values, expected_property_2_values)

    def test_missing_int_values(self):

        recording1 = generate_recording(num_channels=2, durations=[1.0])
        recording1 = recording1.rename_channels(new_channel_ids=["a", "b"])
        recording1.set_property(key="complete_int_property", values=[1, 2])
        add_electrodes_to_nwbfile(recording=recording1, nwbfile=self.nwbfile)

        expected_property = np.asarray([1, 2])
        extracted_property = self.nwbfile.electrodes["complete_int_property"].data
        assert np.array_equal(extracted_property, expected_property)

        recording2 = generate_recording(num_channels=2, durations=[1.0])
        recording2 = recording2.rename_channels(new_channel_ids=["c", "d"])

        recording2.set_property(key="incomplete_int_property", values=[10, 11])
        with self.assertRaises(ValueError):
            add_electrodes_to_nwbfile(recording=recording2, nwbfile=self.nwbfile)

        null_values_for_properties = {"complete_int_property": -1, "incomplete_int_property": -3}
        add_electrodes_to_nwbfile(
            recording=recording2, nwbfile=self.nwbfile, null_values_for_properties=null_values_for_properties
        )

        expected_complete_property = np.asarray([1, 2, -1, -1])
        expected_incomplete_property = np.asarray([-3, -3, 10, 11])

        extracted_complete_property = self.nwbfile.electrodes["complete_int_property"].data
        extracted_incomplete_property = self.nwbfile.electrodes["incomplete_int_property"].data

        assert np.array_equal(extracted_complete_property, expected_complete_property)
        assert np.array_equal(extracted_incomplete_property, expected_incomplete_property)

    def test_missing_bool_values(self):
        recording1 = generate_recording(num_channels=2)
        recording1 = recording1.rename_channels(new_channel_ids=["a", "b"])
        recording1.set_property(key="complete_bool_property", values=[True, False])
        add_electrodes_to_nwbfile(recording=recording1, nwbfile=self.nwbfile)

        expected_property = np.asarray([True, False])
        extracted_property = self.nwbfile.electrodes["complete_bool_property"].data.astype(bool)
        assert np.array_equal(extracted_property, expected_property)

        recording2 = generate_recording(num_channels=2)
        recording2 = recording2.rename_channels(new_channel_ids=["c", "d"])

        recording2.set_property(key="incomplete_bool_property", values=[True, False])
        with self.assertRaises(ValueError):
            add_electrodes_to_nwbfile(recording=recording2, nwbfile=self.nwbfile)

        null_values_for_properties = {"complete_bool_property": False, "incomplete_bool_property": False}
        add_electrodes_to_nwbfile(
            recording=recording2, nwbfile=self.nwbfile, null_values_for_properties=null_values_for_properties
        )

        expected_complete_property = np.asarray([True, False, False, False])
        expected_incomplete_property = np.asarray([False, False, True, False])

        extracted_complete_property = self.nwbfile.electrodes["complete_bool_property"].data.astype(bool)
        extracted_incomplete_property = self.nwbfile.electrodes["incomplete_bool_property"].data.astype(bool)

        assert np.array_equal(extracted_complete_property, expected_complete_property)
        assert np.array_equal(extracted_incomplete_property, expected_incomplete_property)


class TestAddElectrodeGroups:
    def test_group_naming_not_matching_group_number(self):
        recording = generate_recording(num_channels=4)
        recording.set_channel_groups(groups=[0, 1, 2, 3])
        recording.set_property(key="group_name", values=["A", "A", "A", "A"])

        nwbfile = mock_NWBFile()
        with pytest.raises(ValueError, match="The number of group names must match the number of groups"):
            add_electrode_groups_to_nwbfile(nwbfile=nwbfile, recording=recording)

    def test_inconsistent_group_name_mapping(self):
        recording = generate_recording(num_channels=3)
        # Set up groups where the same group name is used for different group numbers
        recording.set_channel_groups(groups=[0, 1, 0])
        recording.set_property(
            key="group_name", values=["A", "B", "B"]  # Inconsistent: group 0 maps to names "A" and "B"
        )

        nwbfile = mock_NWBFile()
        with pytest.raises(ValueError, match="Inconsistent mapping between group numbers and group names"):
            add_electrode_groups_to_nwbfile(nwbfile=nwbfile, recording=recording)


class TestAddUnitsTable(TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        cls.num_units = 4
        cls.single_segment_sorting = generate_sorting(num_units=cls.num_units, durations=[3])
        cls.multiple_segment_sorting = generate_sorting(num_units=cls.num_units, durations=[3, 4])
        cls.base_sorting = cls.single_segment_sorting
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
        add_units_table_to_nwbfile(sorting=self.base_sorting, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["0", "1", "2", "3"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_string_unit_names(self):
        """Ensure add_units_table_to_nwbfile gets the right units name for string units ids"""
        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["a", "b", "c", "d"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_non_overwriting_unit_names_sorting_property(self):
        "add_units_table_to_nwbfile function should not overwrite the sorting object unit_name property"
        unit_names = ["name a", "name b", "name c", "name d"]
        self.sorting_1.set_property(key="unit_name", values=unit_names)
        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = unit_names
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_integer_unit_names_overwrite(self):
        """Ensure unit names merge correctly after appending when unit names are integers."""
        unit_ids = self.base_sorting.get_unit_ids()
        offset_unit_ids = [int(unit_id) + 2 for unit_id in unit_ids]
        sorting_with_offset_unit_ids = self.base_sorting.rename_units(new_unit_ids=offset_unit_ids)

        add_units_table_to_nwbfile(sorting=self.base_sorting, nwbfile=self.nwbfile)
        add_units_table_to_nwbfile(sorting=sorting_with_offset_unit_ids, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["0", "1", "2", "3", "4", "5"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_string_unit_names_overwrite(self):
        """Ensure unit names merge correctly after appending when channel names are strings."""
        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table_to_nwbfile(sorting=self.sorting_2, nwbfile=self.nwbfile)

        expected_unit_names_in_units_table = ["a", "b", "c", "d", "e", "f"]
        unit_names_in_units_table = list(self.nwbfile.units["unit_name"].data)
        self.assertListEqual(unit_names_in_units_table, expected_unit_names_in_units_table)

    def test_common_property_extension(self):
        """Add a property for a first sorting that is then extended by a second sorting."""
        self.sorting_1.set_property(key="common_property", values=["value_1"] * self.num_units)
        self.sorting_2.set_property(key="common_property", values=["value_2"] * self.num_units)

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table_to_nwbfile(sorting=self.sorting_2, nwbfile=self.nwbfile)

        properties_in_units_table = list(self.nwbfile.units["common_property"].data)
        expected_properties_in_units_table = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(properties_in_units_table, expected_properties_in_units_table)

    def test_property_addition(self):
        """Add a property only available in a second sorting."""
        self.sorting_2.set_property(key="added_property", values=["added_value"] * self.num_units)

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table_to_nwbfile(sorting=self.sorting_2, nwbfile=self.nwbfile)

        properties_in_units_table = list(self.nwbfile.units["added_property"].data)
        expected_properties_in_units_table = ["", "", "added_value", "added_value", "added_value", "added_value"]
        self.assertListEqual(properties_in_units_table, expected_properties_in_units_table)

    def test_units_table_extension_after_manual_unit_addition(self):
        """Add some rows to the units tables before using the add_units_table_to_nwbfile function"""
        values_dic = self.defaults

        values_dic.update(id=123, spike_times=[0, 1, 2])
        self.nwbfile.add_unit(**values_dic)

        values_dic.update(id=124, spike_times=[2, 3, 4])
        self.nwbfile.add_unit(**values_dic)

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

        expected_units_ids = [123, 124, 2, 3, 4, 5]
        expected_unit_names = ["123", "124", "a", "b", "c", "d"]
        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)

    def test_manual_extension_after_add_units_table_to_nwbfile(self):
        """Add some units to the units table after using the add_units_table_to_nwbfile function"""

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

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
        Add some units to the units tables before using the add_units_table_to_nwbfile function.
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

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

        # Properties correspond with unit names, ids are filled positionally
        expected_units_ids = [20, 21, 22, 3, 4]
        expected_unit_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "value_f", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)
        self.assertListEqual(list(self.nwbfile.units["property"].data), expected_property_values)

    def test_add_existing_units(self):
        # test that additional units are not added if already in the nwbfile.units table
        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)
        self.assertEqual(len(self.nwbfile.units), len(self.sorting_1.unit_ids))

    def test_property_matching_by_unit_name_with_new_property(self):
        """
        Add some units to the units tables before using the add_units_table_to_nwbfile function.
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

        add_units_table_to_nwbfile(sorting=self.sorting_1, nwbfile=self.nwbfile)

        # Properties correspond with unit names, ids are filled positionally
        expected_units_ids = [20, 21, 22, 3, 4]
        expected_unit_names = ["c", "d", "f", "a", "b"]
        expected_property_values = ["value_c", "value_d", "", "value_a", "value_b"]

        self.assertListEqual(list(self.nwbfile.units.id.data), expected_units_ids)
        self.assertListEqual(list(self.nwbfile.units["unit_name"].data), expected_unit_names)
        self.assertListEqual(list(self.nwbfile.units["property"].data), expected_property_values)

    def test_write_units_table_in_processing_module(self):
        """ """

        units_table_name = "testing_processing"
        unit_table_description = "testing_description"
        add_units_table_to_nwbfile(
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

    def test_write_subset_units(self):
        """ """
        subset_unit_ids = self.base_sorting.unit_ids[::2]
        add_units_table_to_nwbfile(
            sorting=self.base_sorting,
            nwbfile=self.nwbfile,
            unit_ids=subset_unit_ids,
        )

        self.assertEqual(len(self.nwbfile.units), len(subset_unit_ids))
        self.assertTrue(all(str(unit_id) in self.nwbfile.units["unit_name"][:] for unit_id in subset_unit_ids))

    def test_write_bool_properties(self):
        """ """
        bool_property = np.array([False] * len(self.base_sorting.unit_ids))
        bool_property[::2] = True
        self.base_sorting.set_property("test_bool", bool_property)
        add_units_table_to_nwbfile(
            sorting=self.base_sorting,
            nwbfile=self.nwbfile,
        )
        self.assertIn("test_bool", self.nwbfile.units.colnames)
        assert all(tb in [False, True] for tb in self.nwbfile.units["test_bool"][:])

    def test_adding_ragged_array_properties(self):

        sorting1 = generate_sorting(num_units=4)
        sorting1 = sorting1.rename_units(new_unit_ids=["a", "b", "c", "d"])
        sorting2 = generate_sorting(num_units=4)
        sorting2 = sorting2.rename_units(new_unit_ids=["e", "f", "g", "h"])

        ragged_array_values1 = [[1, 2], [3, 4], [5, 6], [7, 8]]
        sorting1.set_property(key="ragged_property", values=ragged_array_values1)
        add_units_table_to_nwbfile(sorting=sorting1, nwbfile=self.nwbfile)

        written_values = self.nwbfile.units.to_dataframe()["ragged_property"].to_list()
        np.testing.assert_array_equal(written_values, ragged_array_values1)

        # Add a new recording that contains more properties for the ragged array
        ragged_array_values2 = [[9, 10], [11, 12], [13, 14], [15, 16]]
        sorting2.set_property(key="ragged_property", values=ragged_array_values2)
        second_ragged_array_values = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"], ["j", "k", "l"]]
        sorting2.set_property(key="ragged_property2", values=second_ragged_array_values)
        add_units_table_to_nwbfile(sorting=sorting2, nwbfile=self.nwbfile)

        written_values = self.nwbfile.units.to_dataframe()["ragged_property"].to_list()
        expected_values = ragged_array_values1 + ragged_array_values2
        np.testing.assert_array_equal(written_values, expected_values)

        written_values = self.nwbfile.units.to_dataframe()["ragged_property2"].to_list()
        number_of_rows_added_before = sorting1.get_num_units()
        values_appended_to_table = [[] for _ in range(number_of_rows_added_before)]
        expected_values = values_appended_to_table + second_ragged_array_values

        # We need a for loop because this is a non-homogenous ragged array
        for i, value in enumerate(written_values):
            np.testing.assert_array_equal(value, expected_values[i])

    def test_adding_doubled_ragged_arrays(self):

        sorting1 = generate_sorting(num_units=4)
        sorting1 = sorting1.rename_units(new_unit_ids=["a", "b", "c", "d"])
        sorting2 = generate_sorting(num_units=4)
        sorting2 = sorting2.rename_units(new_unit_ids=["e", "f", "g", "h"])

        doubled_nested_array = [[[1, 2], [3, 4]], [[5, 6], [7, 8]], [[9, 10], [11, 12]], [[13, 14], [15, 16]]]
        sorting1.set_property(key="double_ragged_property", values=doubled_nested_array)
        add_units_table_to_nwbfile(sorting=sorting1, nwbfile=self.nwbfile)

        written_values = self.nwbfile.units.to_dataframe()["double_ragged_property"].to_list()
        np.testing.assert_array_equal(written_values, doubled_nested_array)

        # Add a new recording that contains more properties for the ragged array
        doubled_nested_array2 = [[[17, 18], [19, 20]], [[21, 22], [23, 24]], [[25, 26], [27, 28]], [[29, 30], [31, 32]]]
        sorting2.set_property(key="double_ragged_property", values=doubled_nested_array2)
        second_doubled_nested_array = [
            [["a", "b", "c"], ["d", "e", "f"]],
            [["g", "h", "i"], ["j", "k", "l"]],
            [["m", "n", "o"], ["p", "q", "r"]],
            [["s", "t", "u"], ["v", "w", "x"]],
        ]
        sorting2.set_property(key="double_ragged_property2", values=second_doubled_nested_array)
        add_units_table_to_nwbfile(sorting=sorting2, nwbfile=self.nwbfile)

        written_values = self.nwbfile.units.to_dataframe()["double_ragged_property"].to_list()
        expected_values = doubled_nested_array + doubled_nested_array2
        np.testing.assert_array_equal(written_values, expected_values)

        written_values = self.nwbfile.units.to_dataframe()["double_ragged_property2"].to_list()
        number_of_rows_added_before = sorting1.get_num_units()
        values_appended_to_table = [[] for _ in range(number_of_rows_added_before)]
        expected_values = values_appended_to_table + second_doubled_nested_array

        # We need a for loop because this is a non-homogenous ragged array
        for i, value in enumerate(written_values):
            np.testing.assert_array_equal(value, expected_values[i])

    def test_missing_int_values(self):

        sorting1 = generate_sorting(num_units=2, durations=[1.0])
        sorting1 = sorting1.rename_units(new_unit_ids=["a", "b"])
        sorting1.set_property(key="complete_int_property", values=[1, 2])
        add_units_table_to_nwbfile(sorting=sorting1, nwbfile=self.nwbfile)

        expected_property = np.asarray([1, 2])
        extracted_property = self.nwbfile.units["complete_int_property"].data
        assert np.array_equal(extracted_property, expected_property)

        sorting2 = generate_sorting(num_units=2, durations=[1.0])
        sorting2 = sorting2.rename_units(new_unit_ids=["c", "d"])

        sorting2.set_property(key="incomplete_int_property", values=[10, 11])
        with self.assertRaises(ValueError):
            add_units_table_to_nwbfile(sorting=sorting2, nwbfile=self.nwbfile)

        null_values_for_properties = {"complete_int_property": -1, "incomplete_int_property": -3}
        add_units_table_to_nwbfile(
            sorting=sorting2, nwbfile=self.nwbfile, null_values_for_properties=null_values_for_properties
        )

        expected_complete_property = np.asarray([1, 2, -1, -1])
        expected_incomplete_property = np.asarray([-3, -3, 10, 11])

        extracted_complete_property = self.nwbfile.units["complete_int_property"].data
        extracted_incomplete_property = self.nwbfile.units["incomplete_int_property"].data

        assert np.array_equal(extracted_complete_property, expected_complete_property)
        assert np.array_equal(extracted_incomplete_property, expected_incomplete_property)

    def test_missing_bool_values(self):
        sorting1 = generate_sorting(num_units=2, durations=[1.0])
        sorting1 = sorting1.rename_units(new_unit_ids=["a", "b"])
        sorting1.set_property(key="complete_bool_property", values=[True, False])
        add_units_table_to_nwbfile(sorting=sorting1, nwbfile=self.nwbfile)

        expected_property = np.asarray([True, False])
        extracted_property = self.nwbfile.units["complete_bool_property"].data.astype(bool)
        assert np.array_equal(extracted_property, expected_property)

        sorting2 = generate_sorting(num_units=2, durations=[1.0])
        sorting2 = sorting2.rename_units(new_unit_ids=["c", "d"])

        sorting2.set_property(key="incomplete_bool_property", values=[True, False])
        with self.assertRaises(ValueError):
            add_units_table_to_nwbfile(sorting=sorting2, nwbfile=self.nwbfile)

        null_values_for_properties = {"complete_bool_property": False, "incomplete_bool_property": False}
        add_units_table_to_nwbfile(
            sorting=sorting2, nwbfile=self.nwbfile, null_values_for_properties=null_values_for_properties
        )

        expected_complete_property = np.asarray([True, False, False, False])
        expected_incomplete_property = np.asarray([False, False, True, False])

        extracted_complete_property = self.nwbfile.units["complete_bool_property"].data.astype(bool)
        extracted_incomplete_property = self.nwbfile.units["incomplete_bool_property"].data.astype(bool)

        assert np.array_equal(extracted_complete_property, expected_complete_property)
        assert np.array_equal(extracted_incomplete_property, expected_incomplete_property)

    def test_add_electrodes(self):

        sorting = generate_sorting(num_units=4)
        sorting = sorting.rename_units(new_unit_ids=["a", "b", "c", "d"])

        unit_electrode_indices = [[0], [1], [2], [0, 1, 2]]

        recording = generate_recording(num_channels=4, durations=[1.0])
        recording = recording.rename_channels(new_channel_ids=["A", "B", "C", "D"])

        add_recording_to_nwbfile(recording=recording, nwbfile=self.nwbfile)

        assert self.nwbfile.electrodes is not None

        # add units table
        add_sorting_to_nwbfile(
            sorting=sorting,
            nwbfile=self.nwbfile,
            unit_electrode_indices=unit_electrode_indices,
        )

        units_table = self.nwbfile.units
        assert "electrodes" in units_table.colnames

        electrode_table = self.nwbfile.electrodes
        assert units_table["electrodes"].target.table == electrode_table

        assert units_table["electrodes"][0]["channel_name"].item() == "A"
        assert units_table["electrodes"][1]["channel_name"].item() == "B"
        assert units_table["electrodes"][2]["channel_name"].item() == "C"
        assert units_table["electrodes"][3]["channel_name"].values.tolist() == ["A", "B", "C"]


from neuroconv.tools import get_package_version

spike_interface_version = get_package_version("spikeinterface")


class TestWriteSortingAnalyzer(TestCase):
    @classmethod
    def setUpClass(cls):
        # import submodules to unlock extensions
        from spikeinterface import create_sorting_analyzer

        cls.num_units = 4
        cls.num_channels = 4
        duration_1 = 6
        duration_2 = 7
        single_segment_rec, single_segment_sort = generate_ground_truth_recording(
            num_channels=cls.num_channels, durations=[duration_1]
        )
        multi_segment_rec, multi_segment_sort = generate_ground_truth_recording(
            num_channels=cls.num_channels, durations=[duration_1, duration_2]
        )
        single_segment_rec.annotate(is_filtered=True)
        multi_segment_rec.annotate(is_filtered=True)
        single_segment_sort.delete_property("gt_unit_locations")
        multi_segment_sort.delete_property("gt_unit_locations")

        cls.single_segment_analyzer = create_sorting_analyzer(single_segment_sort, single_segment_rec, sparse=False)
        cls.single_segment_analyzer_sparse = create_sorting_analyzer(
            single_segment_sort, single_segment_rec, sparse=True
        )
        cls.multi_segment_analyzer = create_sorting_analyzer(multi_segment_sort, multi_segment_rec, sparse=False)
        cls.multi_segment_analyzer_sparse = create_sorting_analyzer(multi_segment_sort, multi_segment_rec, sparse=True)

        # add quality/template metrics to test property propagation
        extension_list = ["random_spikes", "noise_levels", "templates", "template_metrics", "quality_metrics"]
        cls.single_segment_analyzer.compute(extension_list)
        cls.single_segment_analyzer_sparse.compute(extension_list)
        cls.multi_segment_analyzer.compute(extension_list)
        cls.multi_segment_analyzer_sparse.compute(extension_list)

        # slice sorting
        cls.analyzer_slice = cls.single_segment_analyzer.select_units(
            unit_ids=cls.single_segment_analyzer.unit_ids[::2]
        )

        # recordingless
        cls.tmpdir = Path(mkdtemp())
        # create analyzer without recording
        cls.analyzer_recless = cls.single_segment_analyzer.copy()
        cls.analyzer_recless._recording = None
        cls.analyzer_recless_recording = single_segment_rec

        cls.nwbfile_path = cls.tmpdir / "test.nwb"
        if cls.nwbfile_path.exists():
            cls.nwbfile_path.unlink()

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        """Start with a fresh NWBFile, and remapped sorters each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )

    def _test_analyzer_write(self, analyzer, nwbfile, test_properties=True):
        # test unit columns
        self.assertIn("waveform_mean", nwbfile.units.colnames)
        self.assertIn("waveform_sd", nwbfile.units.colnames)
        if test_properties:
            self.assertIn("peak_to_valley", nwbfile.units.colnames)
            self.assertIn("amplitude_cutoff", nwbfile.units.colnames)

        # test that electrode table has been saved
        assert nwbfile.electrodes is not None
        assert len(analyzer.unit_ids) == len(nwbfile.units)
        # test that waveforms and stds are the same
        unit_ids = analyzer.unit_ids
        template_extension = analyzer.get_extension("templates")
        for unit_index, _ in enumerate(nwbfile.units.id):
            wf_mean_si = template_extension.get_templates(unit_ids=[unit_ids[unit_index]])[0]
            wf_mean_nwb = nwbfile.units[unit_index]["waveform_mean"].values[0]
            np.testing.assert_array_almost_equal(wf_mean_si, wf_mean_nwb)
            wf_sd_si = template_extension.get_templates(unit_ids=[unit_ids[unit_index]], operator="std")[0]
            wf_sd_nwb = nwbfile.units[unit_index]["waveform_sd"].values[0]
            np.testing.assert_array_almost_equal(wf_sd_si, wf_sd_nwb)

    def test_analyzer_single_segment(self):
        """This tests that the analyzer is written appropriately for the single segment case"""
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer, nwbfile=self.nwbfile, write_electrical_series=True
        )
        self._test_analyzer_write(self.single_segment_analyzer, self.nwbfile)
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)

    def test_analyzer_single_segment_sparse(self):
        """This tests that the analyzer is written appropriately for the single segment case"""
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer_sparse, nwbfile=self.nwbfile, write_electrical_series=True
        )
        self._test_analyzer_write(self.single_segment_analyzer_sparse, self.nwbfile)
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)

    def test_analyzer_multiple_segments(self):
        """This tests that the analyzer is written appropriately for the multi segment case"""
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.multi_segment_analyzer, nwbfile=self.nwbfile, write_electrical_series=False
        )
        self._test_analyzer_write(self.multi_segment_analyzer, self.nwbfile)

    def test_analyzer_multiple_segments_sparse(self):
        """This tests that the analyzer is written appropriately for the multi segment case"""
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.multi_segment_analyzer_sparse, nwbfile=self.nwbfile, write_electrical_series=False
        )
        self._test_analyzer_write(self.multi_segment_analyzer_sparse, self.nwbfile)

    def test_write_subset_units(self):
        """This tests that the analyzer is sliced properly based on unit_ids"""
        subset_unit_ids = self.single_segment_analyzer.unit_ids[::2]
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer, nwbfile=self.nwbfile, unit_ids=subset_unit_ids
        )
        self._test_analyzer_write(self.analyzer_slice, self.nwbfile, test_properties=False)

        self.assertEqual(len(self.nwbfile.units), len(subset_unit_ids))
        self.assertTrue(all(str(unit_id) in self.nwbfile.units["unit_name"][:] for unit_id in subset_unit_ids))

    def test_write_recordingless_to_write_recording_to_nwbfile(self):
        """This tests that the analyzer is written properly in recordingless mode"""
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.analyzer_recless,
            nwbfile=self.nwbfile,
            recording=self.analyzer_recless_recording,
            write_electrical_series=True,
        )
        self._test_analyzer_write(self.analyzer_recless, self.nwbfile, test_properties=False)

        # check that not passing the recording raises and Exception
        with self.assertRaises(Exception) as context:
            write_sorting_analyzer_to_nwbfile(
                sorting_analyzer=self.analyzer_recless,
                nwbfile=self.nwbfile,
                recording=self.analyzer_recless_recording,
                write_electrical_series=True,
            )

    # def test_write_sorting_analyzer_to_file_to_write_sorting_analyzer_to_nwbfile(self):
    #     """This tests that the analyzer is written to file"""
    #     metadata = get_default_nwbfile_metadata()
    #     metadata["NWBFile"]["session_start_time"] = datetime.now()

    #     write_sorting_analyzer_to_nwbfile(
    #         sorting_analyzer=self.single_segment_analyzer,
    #         nwbfile_path=self.nwbfile_path,
    #         write_electrical_series=True,
    #         metadata=metadata,
    #     )

    #     with NWBHDF5IO(self.nwbfile_path, "r") as io:
    #         nwbfile = io.read()
    #         self._test_analyzer_write(self.single_segment_analyzer, nwbfile)
    #         self.assertIn("ElectricalSeriesRaw", nwbfile.acquisition)

    def test_write_multiple_probes_without_electrical_series(self):
        """This test that the analyzer is written to different electrode groups"""
        # we write the first set of waveforms as belonging to group 0
        original_channel_groups = self.analyzer_recless_recording.get_channel_groups()
        self.analyzer_recless_recording.set_channel_groups([0] * len(self.analyzer_recless_recording.channel_ids))
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.analyzer_recless,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            recording=self.analyzer_recless_recording,
        )
        # now we set new channel groups to mimic a different probe and call the function again
        self.analyzer_recless_recording.set_channel_groups([1] * len(self.analyzer_recless_recording.channel_ids))
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.analyzer_recless,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            recording=self.analyzer_recless_recording,
        )
        # check that we have 2 groups
        self.assertEqual(len(self.nwbfile.electrode_groups), 2)
        self.assertEqual(len(np.unique(self.nwbfile.electrodes["group_name"])), 2)
        # check that we have correct number of units
        self.assertEqual(len(self.nwbfile.units), 2 * len(self.analyzer_recless.unit_ids))
        # check electrode regions of units
        for row in self.nwbfile.units.id:
            if row < len(self.analyzer_recless.unit_ids):
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [0, 1, 2, 3])
            else:
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [4, 5, 6, 7])

        # reset original channel groups
        self.analyzer_recless_recording.set_channel_groups(original_channel_groups)

    def test_write_multiple_probes_with_electrical_series(self):
        """This test that the analyzer is written to different electrode groups"""
        # we write the first set of waveforms as belonging to group 0
        recording = self.single_segment_analyzer.recording
        original_channel_groups = recording.get_channel_groups()
        self.single_segment_analyzer.recording.set_channel_groups([0] * len(recording.channel_ids))
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw1=dict(name="ElectricalSeriesRaw1", description="raw series"),
                ElectricalSeriesRaw2=dict(name="ElectricalSeriesRaw2", description="lfp series"),
            )
        )
        add_electrical_series_kwargs1b = dict(es_key="ElectricalSeriesRaw1")
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs1b,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(recording.channel_ids))
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)

        # now we set new channel groups to mimic a different probe and call the function again
        self.single_segment_analyzer.recording.set_channel_groups([1] * len(recording.channel_ids))
        add_electrical_series_kwargs2_to_add_electrical_series_to_nwbfile = dict(es_key="ElectricalSeriesRaw2")
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs2_to_add_electrical_series_to_nwbfile,
        )
        # check that we have 2 groups
        self.assertEqual(len(self.nwbfile.electrode_groups), 2)
        self.assertEqual(len(np.unique(self.nwbfile.electrodes["group_name"])), 2)
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesRaw2", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), 2 * len(recording.channel_ids))

        # check that we have correct number of units
        self.assertEqual(len(self.nwbfile.units), 2 * len(self.analyzer_recless.unit_ids))
        # check electrode regions of units
        for row in self.nwbfile.units.id:
            if row < len(self.analyzer_recless.unit_ids):
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [0, 1, 2, 3])
            else:
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [4, 5, 6, 7])

        # reset original channel groups
        self.single_segment_analyzer.recording.set_channel_groups(original_channel_groups)

    def test_missing_electrode_group(self):
        """This tests that analyzer is correctly written even if the 'group' property is not available"""
        groups = self.single_segment_analyzer.recording.get_channel_groups()
        self.single_segment_analyzer.recording.delete_property("group")
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer,
            nwbfile=self.nwbfile,
        )
        self.single_segment_analyzer.recording.set_channel_groups(groups)

    def test_group_name_property(self):
        """This tests that the 'group_name' property is correctly used to instantiate electrode groups"""
        num_channels = len(self.single_segment_analyzer.recording.channel_ids)
        self.single_segment_analyzer.recording.set_property("group_name", ["my-fancy-group"] * num_channels)
        write_sorting_analyzer_to_nwbfile(
            sorting_analyzer=self.single_segment_analyzer,
            nwbfile=self.nwbfile,
        )
        self.assertIn("my-fancy-group", self.nwbfile.electrode_groups)
        self.assertEqual(len(self.nwbfile.electrode_groups), 1)
        self.single_segment_analyzer.recording.delete_property("group_name")

    def test_units_table_name(self):
        """This tests the units naming exception"""
        with self.assertRaises(Exception) as context:
            write_sorting_analyzer_to_nwbfile(
                sorting_analyzer=self.single_segment_analyzer,
                nwbfile=self.nwbfile,
                write_as="units",
                units_name="units1",
            )


if __name__ == "__main__":
    unittest.main()
