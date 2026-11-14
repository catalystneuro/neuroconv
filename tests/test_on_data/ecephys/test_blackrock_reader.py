import re

import numpy as np
import pytest

from neuroconv.datainterfaces.ecephys.blackrock._blackrock_extractors import (
    _BlackrockRecordingExtractor,
    _BlackrockSortingExtractor,
)
from neuroconv.datainterfaces.ecephys.blackrock._blackrock_reader import (
    read_nev,
    read_nsx,
)

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestOneSampleBlocks:
    """A spec 2.3 file with two blocks of a single sample, each followed one tick later by the next block."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_3"
        / "time_structure"
        / "one_sample_blocks"
        / "one_sample_blocks.ns5"
    )

    def test_data_blocks(self):
        nsx_file = read_nsx(self.file_path)

        expected_blocks = [(0, 100), (404800, 1), (404801, 100), (819981, 100), (879002, 1), (879003, 100)]
        assert [(block.timestamp, block.sample_count) for block in nsx_file.data_blocks] == expected_blocks

    def test_contiguous_blocks_are_one_segment(self):
        # A new block only starts after a gap longer than one sample, so a block that starts where the previous
        # one ends continues the same segment.
        recording = _BlackrockRecordingExtractor(self.file_path)

        expected_samples_per_segment = [100, 101, 100, 101]
        assert [recording.get_num_samples(segment) for segment in range(4)] == expected_samples_per_segment
        assert recording.get_num_segments() == 4


class TestSamplesOutOfOrderInPTPTimestamps:
    """A spec 3.0 file with PTP timestamps where a run of samples was written after the run that follows it."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_3_0"
        / "time_structure"
        / "samples_out_of_order_in_ptp_timestamps"
        / "samples_out_of_order_in_ptp_timestamps.ns6"
    )

    def test_timestamps_step_back_in_the_file(self):
        nsx_file = read_nsx(self.file_path)
        steps = np.diff(nsx_file.get_ptp_timestamps().astype("int64"))

        assert nsx_file.is_ptp
        assert np.count_nonzero(steps < 0) == 1
        assert steps.min() == -1900042

    def test_samples_are_sorted_back(self):
        recording = _BlackrockRecordingExtractor(self.file_path)
        steps = np.diff(recording.get_times(segment_index=0))

        # Sorting gives back an even grid at 30 kHz.
        assert recording.get_num_segments() == 1
        assert recording.get_num_samples(segment_index=0) == 1000
        assert steps.min() > 32.9e-6
        assert steps.max() < 33.9e-6


class TestPauseAndResume:
    """A spec 3.0 file with PTP timestamps, paused and resumed within one recording."""

    file_path = (
        ECEPHY_DATA_PATH / "blackrock" / "version_3_0" / "time_structure" / "pause_and_resume" / "pause_and_resume.ns5"
    )

    def test_pause_is_a_jump_in_the_times(self):
        recording = _BlackrockRecordingExtractor(self.file_path)
        steps = np.diff(recording.get_times(segment_index=0))

        assert recording.get_num_segments() == 1
        assert recording.get_num_samples(segment_index=0) == 6000
        assert np.argmax(steps) == 2999
        assert np.isclose(steps.max(), 3.619, atol=1e-3)


class TestStimulationElectrodeIds:
    """A spec 2.2 event file from Trellis, where stimulation packets use electrode ids above 5120."""

    file_path = (
        ECEPHY_DATA_PATH
        / "blackrock"
        / "version_2_2"
        / "spikes"
        / "stim_electrode_ids_above_5120"
        / "stim_electrode_ids_above_5120.nev"
    )

    def test_stimulation_packets_are_not_spikes(self):
        nev_file = read_nev(self.file_path)

        assert len(nev_file.spikes) == 300
        assert nev_file.spikes["electrode_id"].max() == 224
        assert len(nev_file.stimulation_events) == 32
        assert list(np.unique(nev_file.stimulation_events["electrode_id"])) == [5136, 5139, 5176, 5209]
        assert len(nev_file.digital_events) == 16

    def test_sorting_extractor_reads_only_spikes(self):
        sorting = _BlackrockSortingExtractor(self.file_path)

        assert sorting.get_num_segments() == 1
        assert sum(len(sorting.get_unit_spike_train(unit_id)) for unit_id in sorting.get_unit_ids()) == 300


class TestSpec20EventFile:
    """A spec 2.0 event file, which has the same layout as spec 2.1."""

    file_path = ECEPHY_DATA_PATH / "blackrock" / "version_2_0" / "spikes" / "packet_bytes_110" / "packet_bytes_110.nev"

    def test_spikes(self):
        nev_file = read_nev(self.file_path)

        assert nev_file.spec == "2.0"
        assert len(nev_file.spikes) == 2000


class TestBlackrockReaderEdgeCases:
    """Continuous files whose block headers do not match their data, and a file that ends inside its header."""

    def test_block_declares_zero_points(self):
        file_path = (
            ECEPHY_DATA_PATH
            / "blackrock"
            / "files_with_errors"
            / "version_2_2"
            / "block_declares_zero_points"
            / "block_declares_zero_points.ns2"
        )
        nsx_file = read_nsx(file_path)

        expected_notes = ["Data block 0 declares 0 points but data follows it; read 100 samples from the file size."]
        assert nsx_file.notes == expected_notes
        assert _BlackrockRecordingExtractor(file_path).get_num_samples(segment_index=0) == 100

    def test_zero_filled_tail_after_data_block(self):
        file_path = (
            ECEPHY_DATA_PATH
            / "blackrock"
            / "files_with_errors"
            / "version_2_3"
            / "zero_filled_tail_after_data_block"
            / "zero_filled_tail_after_data_block.ns6"
        )
        nsx_file = read_nsx(file_path)

        expected_notes = ["The 4105 bytes after data block 0 are all zero and were not read."]
        assert nsx_file.notes == expected_notes
        assert _BlackrockRecordingExtractor(file_path).get_num_samples(segment_index=0) == 600

    def test_file_truncated_inside_header_raises(self):
        file_path = (
            ECEPHY_DATA_PATH
            / "blackrock"
            / "files_with_errors"
            / "version_2_3"
            / "nsx_truncated_inside_header"
            / "nsx_truncated_inside_header.ns5"
        )

        expected_message = (
            "'nsx_truncated_inside_header.ns5' is 16384 bytes long, shorter than the 17210 bytes its header "
            "declares, so it holds no data."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            read_nsx(file_path)
