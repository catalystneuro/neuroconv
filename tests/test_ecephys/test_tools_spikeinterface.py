import unittest
from datetime import datetime
from pathlib import Path
from platform import python_version
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import numpy as np
import psutil
import pynwb.ecephys
from hdmf.backends.hdf5.h5_utils import H5DataIO
from hdmf.data_utils import DataChunkIterator
from hdmf.testing import TestCase
from packaging import version
from pynwb import NWBHDF5IO, NWBFile
from spikeinterface import WaveformExtractor, compute_sparsity, extract_waveforms
from spikeinterface.core.testing_tools import generate_recording, generate_sorting
from spikeinterface.extractors import NumpyRecording

from neuroconv.tools.nwb_helpers import get_module
from neuroconv.tools.spikeinterface import (
    add_electrical_series,
    add_electrodes,
    add_units_table,
    check_if_recording_traces_fit_into_memory,
    get_nwb_metadata,
    write_recording,
    write_sorting,
    write_waveforms,
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
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        assert "ElectricalSeriesRaw" in acquisition_module
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        assert isinstance(electrical_series.data, H5DataIO)

        compression_parameters = electrical_series.data.get_io_params()
        assert compression_parameters["compression"] == "gzip"

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
        assert "ElectricalSeriesLFP" in lfp_container.electrical_series

        electrical_series = lfp_container.electrical_series["ElectricalSeriesLFP"]
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
        assert "ElectricalSeriesProcessed" in filtered_ephys_container.electrical_series

        electrical_series = filtered_ephys_container.electrical_series["ElectricalSeriesProcessed"]
        extracted_data = electrical_series.data[:]
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_multiple_electrical_series_from_same_group(self):
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="raw series"),
                ElectricalSeriesLFP=dict(name="ElectricalSeriesLFP", description="lfp series"),
            )
        )
        add_electrical_series(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw",
            iterator_type=None,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)

        add_electrical_series(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesLFP",
            iterator_type=None,
        )
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesLFP", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))

    def test_write_multiple_electrical_series_from_different_groups(self):
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw1=dict(name="ElectricalSeriesRaw1", description="raw series"),
                ElectricalSeriesRaw2=dict(name="ElectricalSeriesRaw2", description="lfp series"),
            )
        )
        original_groups = self.test_recording_extractor.get_channel_groups()
        self.test_recording_extractor.set_channel_groups(["group0"] * len(self.test_recording_extractor.channel_ids))
        add_electrical_series(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw1",
            iterator_type=None,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(self.test_recording_extractor.channel_ids))
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        # set new channel groups to create a new  electrode_group
        self.test_recording_extractor.set_channel_groups(["group1"] * len(self.test_recording_extractor.channel_ids))
        add_electrical_series(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            metadata=metadata,
            es_key="ElectricalSeriesRaw2",
            iterator_type=None,
        )
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesRaw2", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), 2 * len(self.test_recording_extractor.channel_ids))

        self.test_recording_extractor.set_channel_groups(original_groups)

    def test_invalid_write_as_argument_assertion(self):
        write_as = "any_other_string_that_is_not_raw_lfp_or_processed"

        reg_expression = f"'write_as' should be 'raw', 'processed' or 'lfp', but instead received value {write_as}"

        with self.assertRaisesRegex(AssertionError, reg_expression):
            add_electrical_series(
                recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, write_as=write_as
            )

    def test_write_with_higher_gzip_level(self):
        compression = "gzip"
        compression_opts = 8
        add_electrical_series(
            recording=self.test_recording_extractor,
            nwbfile=self.nwbfile,
            iterator_type=None,
            compression=compression,
            compression_opts=compression_opts,
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        compression_parameters = electrical_series.data.get_io_params()
        assert compression_parameters["compression"] == compression
        assert compression_parameters["compression_opts"] == compression_opts

    def test_write_with_lzf_compression(self):
        compression = "lzf"
        add_electrical_series(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None, compression=compression
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        compression_parameters = electrical_series.data.get_io_params()
        assert compression_parameters["compression"] == compression
        assert "compression_opts" not in compression_parameters


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
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        expected_rate = self.sampling_frequency
        extracted_rate = electrical_series.rate

        assert extracted_rate == expected_rate

    def test_non_uniform_timestamps(self):
        expected_timestamps = np.array([0.0, 2.0, 10.0])
        self.test_recording_extractor.set_times(times=expected_timestamps, with_warning=False)
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        reg_expression = f"Recording extractors with heterogeneous offsets are not supported"

        with self.assertRaisesRegex(ValueError, reg_expression):
            add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)


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

    def test_default_chunking(self):
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile)

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        h5dataiowrapped_electrical_series = electrical_series.data
        electrical_series_data_iterator = h5dataiowrapped_electrical_series.data

        assert isinstance(electrical_series_data_iterator, SpikeInterfaceRecordingDataChunkIterator)

        extracted_data = np.concatenate([data_chunk.data for data_chunk in electrical_series_data_iterator])
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_iterator_opts_propagation(self):
        iterator_opts = dict(chunk_shape=(10, 3))
        add_electrical_series(
            recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_opts=iterator_opts
        )

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        h5dataiowrapped_electrical_series = electrical_series.data
        electrical_series_data_iterator = h5dataiowrapped_electrical_series.data

        assert electrical_series_data_iterator.chunk_shape == iterator_opts["chunk_shape"]

    def test_hdfm_iterator(self):
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type="v1")

        acquisition_module = self.nwbfile.acquisition
        electrical_series = acquisition_module["ElectricalSeriesRaw"]
        h5dataiowrapped_electrical_series = electrical_series.data
        electrical_series_data_iterator = h5dataiowrapped_electrical_series.data

        assert isinstance(electrical_series_data_iterator, DataChunkIterator)

        extracted_data = np.concatenate([data_chunk.data for data_chunk in electrical_series_data_iterator])
        expected_data = self.test_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_non_iterative_write(self):
        add_electrical_series(recording=self.test_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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

        # Mock recording extractor with as much frames as necessary to overflow memory
        mock_recorder = Mock()
        mock_recorder.get_dtype.return_value = dtype
        mock_recorder.get_num_channels.return_value = num_channels
        mock_recorder.get_num_frames.return_value = num_frames_to_overflow

        reg_expression = f"Memory error, full electrical series is (.*?) GB are available. Use iterator_type='V2'"

        with self.assertRaisesRegex(MemoryError, reg_expression):
            check_if_recording_traces_fit_into_memory(recording=mock_recorder)

    def test_invalid_iterator_type_assertion(self):
        iterator_type = "invalid_iterator_type"

        reg_expression = "iterator_type (.*?)"
        with self.assertRaisesRegex(ValueError, reg_expression):
            add_electrical_series(
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
        write_recording(recording=self.single_segment_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

        acquisition_module = self.nwbfile.acquisition
        assert "ElectricalSeriesRaw" in acquisition_module
        electrical_series = acquisition_module["ElectricalSeriesRaw"]

        assert isinstance(electrical_series.data, H5DataIO)

        compression_parameters = electrical_series.data.get_io_params()
        assert compression_parameters["compression"] == "gzip"

        extracted_data = electrical_series.data[:]
        expected_data = self.single_segment_recording_extractor.get_traces(segment_index=0)
        np.testing.assert_array_almost_equal(expected_data, extracted_data)

    def test_write_multiple_segments(self):
        write_recording(recording=self.multiple_segment_recording_extractor, nwbfile=self.nwbfile, iterator_type=None)

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
        add_electrodes(
            recording=self.single_segment_recording_extractor,
            nwbfile=self.nwbfile,
        )
        self.assertIn("test_bool", self.nwbfile.electrodes.colnames)
        assert all(tb in ["False", "True"] for tb in self.nwbfile.electrodes["test_bool"][:])


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
            group=self.electrode_group,
            group_name="0",
            location="unknown",
        )

    def test_default_electrode_column_names(self):
        add_electrodes(recording=self.base_recording, nwbfile=self.nwbfile)

        expected_electrode_column_names = ["location", "group", "group_name", "channel_name", "rel_x", "rel_y"]
        actual_electrode_column_names = list(self.nwbfile.electrodes.colnames)
        self.assertCountEqual(actual_electrode_column_names, expected_electrode_column_names)

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

    def test_channel_group_names_table(self):
        "add_electrodes function should add new rows if same channel names, but different group_names"
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
        original_groups = self.recording_1.get_channel_groups()
        self.recording_1.set_channel_groups(["1"] * len(self.recording_1.channel_ids))
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
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

        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)
        add_electrodes(recording=self.recording_2, nwbfile=self.nwbfile)

        actual_properties_in_electrodes_table = list(self.nwbfile.electrodes["common_property"].data)
        expected_properties_in_electrodes_table = ["value_1", "value_1", "value_1", "value_1", "value_2", "value_2"]
        self.assertListEqual(actual_properties_in_electrodes_table, expected_properties_in_electrodes_table)

    def test_add_electrodes_addition(self):
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
        add_electrodes(recording=self.base_recording, nwbfile=self.nwbfile)
        self.assertEqual(len(self.nwbfile.electrodes), len(self.base_recording.channel_ids))

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

    def test_manual_row_adition_before_add_electrodes_function_optional_columns(self):
        """Add some rows including optional columns to the electrode tables before using the add_electrodes function."""
        values_dic = self.defaults

        values_dic.update(id=123)
        self.nwbfile.add_electrode(**values_dic, x=0.0, y=1.0, z=2.0)

        values_dic.update(id=124)
        self.nwbfile.add_electrode(**values_dic, x=1.0, y=2.0, z=3.0)

        # recording_1 does not have x, y, z positions
        add_electrodes(recording=self.recording_1, nwbfile=self.nwbfile)

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

    def test_add_existing_units(self):
        # test that additional units are not added if already in the nwbfile.units table
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)
        add_units_table(sorting=self.sorting_1, nwbfile=self.nwbfile)
        self.assertEqual(len(self.nwbfile.units), len(self.sorting_1.unit_ids))

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

    def test_write_subset_units(self):
        """ """
        subset_unit_ids = self.base_sorting.unit_ids[::2]
        add_units_table(
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
        add_units_table(
            sorting=self.base_sorting,
            nwbfile=self.nwbfile,
        )
        self.assertIn("test_bool", self.nwbfile.units.colnames)
        assert all(tb in ["False", "True"] for tb in self.nwbfile.units["test_bool"][:])


@unittest.skipIf(
    version.parse(python_version()) < version.parse("3.8"), "SpikeInterface.extract_waveforms() requires Python>=3.8"
)
class TestWriteWaveforms(TestCase):
    @classmethod
    def setUpClass(cls):
        """Use common recording objects and values."""
        from spikeinterface.postprocessing import compute_template_metrics
        from spikeinterface.qualitymetrics import compute_quality_metrics

        cls.num_units = 4
        cls.num_channels = 4
        single_segment_rec = generate_recording(num_channels=cls.num_channels, durations=[3])
        single_segment_sort = generate_sorting(num_units=cls.num_units, durations=[3])
        multi_segment_rec = generate_recording(num_channels=cls.num_channels, durations=[3, 4])
        multi_segment_sort = generate_sorting(num_units=cls.num_units, durations=[3, 4])
        single_segment_rec.annotate(is_filtered=True)
        multi_segment_rec.annotate(is_filtered=True)
        single_segment_rec = single_segment_rec.save()
        multi_segment_rec = multi_segment_rec.save()
        single_segment_sort = single_segment_sort.save()
        multi_segment_sort = multi_segment_sort.save()

        cls.single_segment_we = extract_waveforms(single_segment_rec, single_segment_sort, folder=None, mode="memory")
        cls.multi_segment_we = extract_waveforms(multi_segment_rec, multi_segment_sort, folder=None, mode="memory")

        # add quality/template metrics to test property propagation
        compute_template_metrics(cls.single_segment_we)
        compute_template_metrics(cls.multi_segment_we)
        compute_quality_metrics(cls.single_segment_we)
        compute_quality_metrics(cls.multi_segment_we)

        # slice sorting
        slice_sorting = single_segment_sort.select_units(single_segment_sort.unit_ids[::2])
        cls.we_slice = extract_waveforms(single_segment_rec, slice_sorting, folder=None, mode="memory")

        cls.tmpdir = Path(mkdtemp())
        cls.waveform_recording3_path = cls.tmpdir / "waveforms_less_channels"
        single_segment_rec_3channels = single_segment_rec.remove_channels([single_segment_rec.channel_ids[0]])

        we3 = extract_waveforms(single_segment_rec_3channels, single_segment_sort, folder=cls.waveform_recording3_path)
        # reload without recording
        cls.we_rec3chan = we3
        cls.we_rec3chan_recording = single_segment_rec_3channels

        # recordingless
        cls.waveform_recordingless_path = cls.tmpdir / "waveforms_recordingless"
        we = extract_waveforms(single_segment_rec, single_segment_sort, folder=cls.waveform_recordingless_path)
        # reload without recording
        cls.we_recless = WaveformExtractor.load_from_folder(cls.waveform_recordingless_path, with_recording=False)
        cls.we_recless_recording = single_segment_rec

        # sparse
        cls.waveform_sparse_path = cls.tmpdir / "waveforms_sparse"
        sparsity = compute_sparsity(cls.single_segment_we, method="radius", radius_um=30)
        cls.we_sparse = cls.single_segment_we.save(folder=cls.waveform_sparse_path, sparsity=sparsity)

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        """Start with a fresh NWBFile, and remapped sorters each time."""
        self.nwbfile = NWBFile(
            session_description="session_description1", identifier="file_id1", session_start_time=testing_session_time
        )
        self.h5file = self.tmpdir / "waveforms.h5"

    def _test_waveform_write(self, we, nwbfile, test_properties=True, test_waveforms=False):
        # test unit columns
        self.assertIn("waveform_mean", nwbfile.units.colnames)
        self.assertIn("waveform_sd", nwbfile.units.colnames)
        if test_properties:
            self.assertIn("peak_to_valley", nwbfile.units.colnames)
            self.assertIn("amplitude_cutoff", nwbfile.units.colnames)

        # test that electrode table has been saved
        assert nwbfile.electrodes is not None
        assert len(we.unit_ids) == len(nwbfile.units)

        if test_waveforms:
            # test that waveforms and stds are the same
            all_templates = we.get_all_templates()
            all_stds = we.get_all_templates(mode="std")
            for unit_index, _ in enumerate(nwbfile.units.id):
                wf_mean_si = all_templates[unit_index]
                wf_mean_nwb = nwbfile.units[unit_index]["waveform_mean"].values[0]
                np.testing.assert_array_almost_equal(wf_mean_si, wf_mean_nwb)
                wf_sd_si = all_stds[unit_index]
                wf_sd_nwb = nwbfile.units[unit_index]["waveform_sd"].values[0]
                np.testing.assert_array_almost_equal(wf_sd_si, wf_sd_nwb)

    def test_write_single_segment(self):
        """This tests that the waveforms are written appropriately for the single segment case"""
        write_waveforms(waveform_extractor=self.single_segment_we, nwbfile=self.nwbfile, write_electrical_series=True)
        self._test_waveform_write(self.single_segment_we, self.nwbfile)
        self.assertIn("ElectricalSeriesRaw", self.nwbfile.acquisition)

    def test_write_multiple_segments(self):
        """This tests that the waveforms are written appropriately for the multi segment case"""
        write_waveforms(waveform_extractor=self.multi_segment_we, nwbfile=self.nwbfile, write_electrical_series=False)
        self._test_waveform_write(self.multi_segment_we, self.nwbfile)

    def test_write_subset_units(self):
        """This tests that the waveforms are sliced properly based on unit_ids"""
        subset_unit_ids = self.single_segment_we.unit_ids[::2]
        write_waveforms(waveform_extractor=self.single_segment_we, nwbfile=self.nwbfile, unit_ids=subset_unit_ids)
        self._test_waveform_write(self.we_slice, self.nwbfile, test_properties=False)

        self.assertEqual(len(self.nwbfile.units), len(subset_unit_ids))
        self.assertTrue(all(str(unit_id) in self.nwbfile.units["unit_name"][:] for unit_id in subset_unit_ids))

    def test_write_recordingless(self):
        """This tests that the waveforms are sliced properly based on unit_ids"""
        write_waveforms(
            waveform_extractor=self.we_recless,
            nwbfile=self.nwbfile,
            recording=self.we_recless_recording,
            write_electrical_series=True,
        )
        self._test_waveform_write(self.we_recless, self.nwbfile, test_properties=False)

        # check that not passing the recording raises and Exception
        with self.assertRaises(Exception) as context:
            write_waveforms(
                waveform_extractor=self.we_recless,
                nwbfile=self.nwbfile,
                recording=self.we_recless_recording,
                write_electrical_series=True,
            )

    def test_write_multiple_probes_without_electrical_series(self):
        """This test that the waveforms are written to different electrode groups"""
        # we write the first set of waveforms as belonging to group 0
        original_channel_groups = self.we_recless_recording.get_channel_groups()
        self.we_recless_recording.set_channel_groups([0] * len(self.we_recless_recording.channel_ids))
        write_waveforms(
            waveform_extractor=self.we_recless,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            recording=self.we_recless_recording,
        )
        # now we set new channel groups to mimic a different probe and call the function again
        self.we_recless_recording.set_channel_groups([1] * len(self.we_recless_recording.channel_ids))
        write_waveforms(
            waveform_extractor=self.we_recless,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            recording=self.we_recless_recording,
        )
        # check that we have 2 groups
        self.assertEqual(len(self.nwbfile.electrode_groups), 2)
        self.assertEqual(len(np.unique(self.nwbfile.electrodes["group_name"])), 2)
        # check that we have correct number of units
        self.assertEqual(len(self.nwbfile.units), 2 * len(self.we_recless.unit_ids))
        # check electrode regions of units
        for row in self.nwbfile.units.id:
            if row < len(self.we_recless.unit_ids):
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [0, 1, 2, 3])
            else:
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [4, 5, 6, 7])

        # reset original channel groups
        self.we_recless_recording.set_channel_groups(original_channel_groups)

    def test_write_multiple_probes_with_electrical_series(self):
        """This test that the waveforms are written to different electrode groups"""
        # we write the first set of waveforms as belonging to group 0
        recording = self.single_segment_we.recording
        original_channel_groups = recording.get_channel_groups()
        self.single_segment_we.recording.set_channel_groups([0] * len(recording.channel_ids))
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw1=dict(name="ElectricalSeriesRaw1", description="raw series"),
                ElectricalSeriesRaw2=dict(name="ElectricalSeriesRaw2", description="lfp series"),
            )
        )
        add_electrical_series_kwargs1 = dict(es_key="ElectricalSeriesRaw1")
        write_waveforms(
            waveform_extractor=self.single_segment_we,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs1,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(recording.channel_ids))
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)

        # now we set new channel groups to mimic a different probe and call the function again
        self.single_segment_we.recording.set_channel_groups([1] * len(recording.channel_ids))
        add_electrical_series_kwargs2 = dict(es_key="ElectricalSeriesRaw2")
        write_waveforms(
            waveform_extractor=self.single_segment_we,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs2,
        )
        # check that we have 2 groups
        self.assertEqual(len(self.nwbfile.electrode_groups), 2)
        self.assertEqual(len(np.unique(self.nwbfile.electrodes["group_name"])), 2)
        self.assertIn("ElectricalSeriesRaw1", self.nwbfile.acquisition)
        self.assertIn("ElectricalSeriesRaw2", self.nwbfile.acquisition)
        self.assertEqual(len(self.nwbfile.electrodes), 2 * len(recording.channel_ids))

        # check that we have correct number of units
        self.assertEqual(len(self.nwbfile.units), 2 * len(self.we_recless.unit_ids))
        # check electrode regions of units
        for row in self.nwbfile.units.id:
            if row < len(self.we_recless.unit_ids):
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [0, 1, 2, 3])
            else:
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [4, 5, 6, 7])

        # reset original channel groups
        self.single_segment_we.recording.set_channel_groups(original_channel_groups)

    def test_write_multiple_probes_with_different_channels(self):
        """This test that the waveforms are written to different electrode groups"""
        # we write the first set of waveforms as belonging to group 0
        recording = self.single_segment_we.recording
        original_channel_groups = recording.get_channel_groups()
        self.single_segment_we.recording.set_channel_groups([0] * len(recording.channel_ids))
        metadata = dict(
            Ecephys=dict(
                ElectricalSeriesRaw1=dict(name="ElectricalSeriesRaw1", description="raw series"),
                ElectricalSeriesRaw2=dict(name="ElectricalSeriesRaw2", description="lfp series"),
            )
        )
        add_electrical_series_kwargs1 = dict(es_key="ElectricalSeriesRaw1")
        write_waveforms(
            waveform_extractor=self.single_segment_we,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs1,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(recording.channel_ids))

        # now we set new channel groups to mimic a different probe and call the function again
        recording3 = self.we_rec3chan_recording
        self.we_rec3chan.recording.set_channel_groups([1] * len(recording3.channel_ids))
        add_electrical_series_kwargs2 = dict(es_key="ElectricalSeriesRaw2")
        write_waveforms(
            waveform_extractor=self.we_rec3chan,
            nwbfile=self.nwbfile,
            write_electrical_series=False,
            metadata=metadata,
            add_electrical_series_kwargs=add_electrical_series_kwargs2,
        )
        # check that we have 2 groups
        self.assertEqual(len(self.nwbfile.electrode_groups), 2)
        self.assertEqual(len(np.unique(self.nwbfile.electrodes["group_name"])), 2)
        self.assertEqual(len(self.nwbfile.electrodes), len(recording.channel_ids) + len(recording3.channel_ids))

        # check that we have correct number of units
        self.assertEqual(len(self.nwbfile.units), 2 * len(self.we_recless.unit_ids))
        # check electrode regions of units
        for row in self.nwbfile.units.id:
            if row < len(self.we_recless.unit_ids):
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [0, 1, 2, 3])
            else:
                self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [4, 5, 6])

        # reset original channel groups
        self.single_segment_we.recording.set_channel_groups(original_channel_groups)

    def test_write_preprocessed_waveforms_and_raw_recording(self):
        """This test that the waveforms are computed on subset of "good" channels, but the
        raw recording contains a superset of channels"""
        # we write the first set of waveforms as belonging to group 0
        we = self.single_segment_we
        recording_raw = we.recording
        recording_preprocessed = recording_raw.remove_channels(recording_raw.channel_ids[::2])

        waveform_preprocessed = extract_waveforms(recording_preprocessed, we.sorting, folder=None, mode="memory")
        # make recordingless
        waveform_preprocessed._recording = None

        write_waveforms(
            waveform_extractor=waveform_preprocessed,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            recording=recording_raw,
            force_dense=False,
        )
        # check that electrodes are set correctly
        self.assertEqual(len(self.nwbfile.electrodes), len(recording_raw.channel_ids))
        for i, row in enumerate(self.nwbfile.units.id):
            waveform_proc_mean = self.nwbfile.units[row].waveform_mean.values[0]
            waveform_proc_std = self.nwbfile.units[row].waveform_sd.values[0]
            self.assertEqual(waveform_proc_mean.shape, (210, 2))
            self.assertEqual(waveform_proc_std.shape, (210, 2))
            self.assertEqual(self.nwbfile.units[row].electrodes.values[0], [1, 3])

    def test_write_preprocessed_waveforms_and_raw_recording_force_dense(self):
        """This test that the waveforms are computed on subset of "good" channels, but the
        raw recording contains a superset of channels"""
        # we write the first set of waveforms as belonging to group 0
        we = self.single_segment_we
        recording_raw = we.recording
        recording_preprocessed = recording_raw.remove_channels(recording_raw.channel_ids[::2])

        waveform_preprocessed = extract_waveforms(recording_preprocessed, we.sorting, folder=None, mode="memory")
        # make recordingless
        waveform_preprocessed._recording = None

        write_waveforms(
            waveform_extractor=waveform_preprocessed,
            nwbfile=self.nwbfile,
            write_electrical_series=True,
            recording=recording_raw,
            force_dense=True,
        )
        self.assertEqual(len(self.nwbfile.electrodes), len(recording_raw.channel_ids))
        # in this case, it is the same as sparse waveforms
        sparse_indices = recording_raw.ids_to_indices(waveform_preprocessed.channel_ids)
        non_sparse_indices = np.setdiff1d(np.arange(recording_raw.get_num_channels()), sparse_indices)
        unit_ids = waveform_preprocessed.sorting.unit_ids
        for i, row in enumerate(self.nwbfile.units.id):
            waveform_proc_mean = self.nwbfile.units[row].waveform_mean.values[0]
            waveform_proc_std = self.nwbfile.units[row].waveform_sd.values[0]
            self.assertEqual(waveform_proc_mean.shape, (210, 4))
            np.testing.assert_array_equal(
                waveform_proc_mean[:, non_sparse_indices], np.zeros_like(waveform_proc_mean[:, non_sparse_indices])
            )
            np.testing.assert_array_equal(
                waveform_proc_mean[:, sparse_indices], waveform_preprocessed.get_template(unit_ids[i])
            )
            self.assertEqual(waveform_proc_std.shape, (210, 4))
            np.testing.assert_array_equal(
                waveform_proc_std[:, non_sparse_indices], np.zeros_like(waveform_proc_std[:, non_sparse_indices])
            )
            np.testing.assert_array_equal(
                waveform_proc_std[:, sparse_indices], waveform_preprocessed.get_template(unit_ids[i], mode="std")
            )

    def test_missing_electrode_group(self):
        """This tests that waveforms are correctly written even if the 'group' property is not available"""
        groups = self.single_segment_we.recording.get_channel_groups()
        self.single_segment_we.recording.delete_property("group")
        write_waveforms(
            waveform_extractor=self.single_segment_we,
            nwbfile=self.nwbfile,
        )
        self.single_segment_we.recording.set_channel_groups(groups)

    def test_group_name_property(self):
        """This tests that the 'group_name' property is correctly used to instantiate electrode groups"""
        num_channels = len(self.single_segment_we.recording.channel_ids)
        self.single_segment_we.recording.set_property("group_name", ["my-fancy-group"] * num_channels)
        write_waveforms(
            waveform_extractor=self.single_segment_we,
            nwbfile=self.nwbfile,
        )
        self.assertIn("my-fancy-group", self.nwbfile.electrode_groups)
        self.assertEqual(len(self.nwbfile.electrode_groups), 1)
        self.single_segment_we.recording.delete_property("group_name")

    def test_units_table_name(self):
        """This tests the units naming exception"""
        with self.assertRaises(Exception) as context:
            write_waveforms(
                waveform_extractor=self.single_segment_we,
                nwbfile=self.nwbfile,
                write_as="units",
                units_name="units1",
            )

    def test_write_sparse_waveforms(self):
        """This tests that the waveforms are written appropriately when they are sparse"""
        write_waveforms(waveform_extractor=self.we_sparse, nwbfile=self.nwbfile, write_electrical_series=False)
        self._test_waveform_write(self.we_sparse, self.nwbfile)
        unit_ids = self.we_sparse.unit_ids
        sparse_indices = self.we_sparse.sparsity.unit_id_to_channel_indices
        for i, row in enumerate(self.nwbfile.units.id):
            self.assertEqual(self.nwbfile.units[row].electrodes.values[0], list(sparse_indices[unit_ids[i]]))

    def test_write_sparse_waveforms_force_dense(self):
        """This tests that the waveforms are written appropriately when they are sparse"""
        write_waveforms(
            waveform_extractor=self.we_sparse, nwbfile=self.nwbfile, write_electrical_series=False, force_dense=True
        )
        self._test_waveform_write(self.we_sparse, self.nwbfile, test_waveforms=False)
        unit_ids = self.we_sparse.unit_ids
        sparse_indices = self.we_sparse.sparsity.unit_id_to_channel_indices
        all_indices = np.arange(self.we_sparse.recording.get_num_channels())
        # test that waveforms and stds are the same
        for i, row in enumerate(self.nwbfile.units.id):
            self.assertEqual(self.nwbfile.units[row].electrodes.values[0], list(all_indices))
            wf_mean_si = self.we_sparse.get_template(unit_ids[i])
            wf_mean_nwb = self.nwbfile.units[i]["waveform_mean"].values[0]
            np.testing.assert_array_almost_equal(wf_mean_si, wf_mean_nwb[:, sparse_indices[unit_ids[i]]])
            wf_sd_si = self.we_sparse.get_template(unit_ids[i], mode="std")
            wf_sd_nwb = self.nwbfile.units[i]["waveform_sd"].values[0]
            np.testing.assert_array_almost_equal(wf_sd_si, wf_sd_nwb[:, sparse_indices[unit_ids[i]]])

    def test_write_sparse_waveforms_to_file_force_dense(self):
        """This tests that the waveforms are written appropriately when they are sparse, but force_dense is True"""
        write_waveforms(
            waveform_extractor=self.we_sparse, nwbfile=self.nwbfile, write_electrical_series=False, force_dense=True
        )
        with NWBHDF5IO(self.h5file, "w") as io:
            io.write(self.nwbfile)

    @unittest.expectedFailure
    def test_write_sparse_waveforms_to_file(self):
        """This tests that the waveforms are written appropriately when they are sparse. THIS SHOULD FAIL"""
        write_waveforms(waveform_extractor=self.we_sparse, nwbfile=self.nwbfile, write_electrical_series=False)
        with NWBHDF5IO(self.h5file, "w") as io:
            io.write(self.nwbfile)


if __name__ == "__main__":
    unittest.main()
