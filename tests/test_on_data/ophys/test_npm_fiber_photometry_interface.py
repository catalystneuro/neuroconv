from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import NPMFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file

from ..setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "sampleData_NPM_4"
FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "npm_fiber_photometry_metadata.yaml"

# Values demultiplexed from PagCeAVgatFear_14421.csv (a Flags-multiplexed v2 file with three region
# columns, Region0G/Region1G/Region2G). The Flags column interleaves two channels: state 17
# (chev/isosbestic, first at row 2) and state 18 (chod/signal, first at row 1); row 0's Flags=16 is
# a startup frame and is dropped. Each channel keeps every other frame; the chod channels are one
# frame longer than chev before being truncated to the shared chev length. The per-channel rate and
# second timestamp follow from the Timestamp spacing (24107.012512 - 24106.962496 = 0.050016 s
# between chev frames).
EXPECTED_STREAM_NAMES = ["file0_chev1", "file0_chev2", "file0_chev3", "file0_chod1", "file0_chod2", "file0_chod3"]
EXPECTED_RATE = 20.001535475605188
EXPECTED_SAMPLES_PER_CHANNEL = 11559
EXPECTED_SECOND_TIMESTAMP = 0.050016000001051
# First sample of each stream (Region0G/1G/2G of the channel's first kept frame).
EXPECTED_FIRST_VALUES = {
    "file0_chev1": 0.0039288397682929,
    "file0_chev2": 0.0039264160546789,
    "file0_chev3": 0.0076003514613392,
    "file0_chod1": 0.00762985045687,
    "file0_chod2": 0.011721079037301,
    "file0_chod3": 0.0175961894191639,
}


class TestNPMFiberPhotometryInterface:
    @pytest.fixture
    def interface(self):
        return NPMFiberPhotometryInterface(folder_path=NPM_FOLDER, verbose=False)

    @pytest.fixture
    def metadata(self, interface):
        editable_metadata = load_dict_from_file(FIBER_PHOTOMETRY_METADATA_FILE)
        return dict_deep_update(interface.get_metadata(), editable_metadata)

    def test_construction(self, interface):
        assert interface.source_data["folder_path"] == NPM_FOLDER

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        """NPM recordings carry no embedded start time, so the interface must not invent one."""
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_stream_discovery_demultiplexes_channels(self, interface):
        """The raw interleaved CSV demultiplexes into chev (isosbestic) and chod (signal) channels
        for each of the three region columns; the 2-column event CSV is excluded."""
        assert sorted(interface._get_stream_names()) == EXPECTED_STREAM_NAMES

    def test_demultiplexed_values(self, interface):
        """Each channel keeps every other frame, normalized to start at zero, and chod is truncated
        to the chev length so data and timestamps match."""
        for stream_name, expected_first_value in EXPECTED_FIRST_VALUES.items():
            stream = interface._read_stream(stream_name)
            assert stream["data"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
            assert stream["timestamps"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
            np.testing.assert_allclose(stream["data"][0], expected_first_value, rtol=1e-9)
            np.testing.assert_allclose(stream["timestamps"][0], 0.0, atol=1e-12)
            np.testing.assert_allclose(stream["timestamps"][1], EXPECTED_SECOND_TIMESTAMP, rtol=1e-9)
            np.testing.assert_allclose(stream["rate"], EXPECTED_RATE, rtol=1e-9)

    def test_timestamp_column_selection(self, tmp_path):
        """Selecting a different timestamp column (a column on a much larger scale) changes the
        per-channel rate, confirming the timestamp-column argument is honored."""
        folder_path = tmp_path / "npm_two_timestamps"
        folder_path.mkdir()
        number_of_rows = 8
        # Flags 16 (startup) then alternating 17/18 -> two interleaved channels.
        dataframe = pd.DataFrame(
            {
                "FrameCounter": np.arange(number_of_rows),
                "SystemTimestamp": np.arange(number_of_rows) * 0.1,  # 10 Hz overall
                "Flags": [16, 17, 18, 17, 18, 17, 18, 17],
                "ComputerTimestamp": np.arange(number_of_rows) * 1.0,  # 10x larger spacing
                "Region0G": np.arange(number_of_rows) * 0.01,
            }
        )
        dataframe.to_csv(folder_path / "fp.csv", index=False)

        default_interface = NPMFiberPhotometryInterface(folder_path=folder_path, verbose=False)
        computer_interface = NPMFiberPhotometryInterface(
            folder_path=folder_path, timestamp_column_name="ComputerTimestamp", verbose=False
        )
        default_rate = default_interface._read_stream("file0_chev1")["rate"]
        computer_rate = computer_interface._read_stream("file0_chev1")["rate"]
        # SystemTimestamp spacing is 10x finer than ComputerTimestamp, so its rate is 10x higher.
        np.testing.assert_allclose(default_rate, 10.0 * computer_rate, rtol=1e-9)

    def test_get_original_starting_time_and_rate(self, interface):
        starting_time_and_rate = interface.get_original_starting_time_and_rate()
        assert set(starting_time_and_rate) == set(EXPECTED_STREAM_NAMES)
        for starting_time, rate in starting_time_and_rate.values():
            assert starting_time == 0.0
            np.testing.assert_allclose(rate, EXPECTED_RATE, rtol=1e-9)

    def test_set_aligned_starting_time(self, interface):
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        timestamps = interface.get_timestamps()
        for stream_name in EXPECTED_STREAM_NAMES:
            assert timestamps[stream_name][0] == 10.0

    def test_run_conversion_writes_response_series(self, interface, metadata, tmp_path):
        nwbfile_path = tmp_path / "npm_fiber_photometry.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()

            response_series_names = {
                name
                for name, obj in nwbfile.acquisition.items()
                if obj.neurodata_type == "FiberPhotometryResponseSeries"
            }
            assert response_series_names == {
                "calcium_signal_region0",
                "isosbestic_control_region0",
                "calcium_signal_region1",
                "isosbestic_control_region1",
                "calcium_signal_region2",
                "isosbestic_control_region2",
            }

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert len(fiber_photometry_table) == 6

            signal_series = nwbfile.acquisition["calcium_signal_region0"]
            control_series = nwbfile.acquisition["isosbestic_control_region0"]
            # stub_test reads ~1 second (ceil(rate)) of samples.
            assert signal_series.data.shape[0] == int(np.ceil(EXPECTED_RATE))
            np.testing.assert_allclose(signal_series.data[0], EXPECTED_FIRST_VALUES["file0_chod1"], rtol=1e-9)
            np.testing.assert_allclose(control_series.data[0], EXPECTED_FIRST_VALUES["file0_chev1"], rtol=1e-9)
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-9)
            # Each response series links to its own single-row region of the table.
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]
            assert list(control_series.fiber_photometry_table_region.data[:]) == [1]

    def test_run_conversion_aligned_starting_time_and_rate(self, interface, metadata, tmp_path):
        interface.set_aligned_starting_time_and_rate(
            {stream_name: (5.0, EXPECTED_RATE) for stream_name in EXPECTED_STREAM_NAMES}
        )
        nwbfile_path = tmp_path / "npm_fiber_photometry_aligned.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            timing_source="aligned_starting_time_and_rate",
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal_region0"]
            assert signal_series.starting_time == 5.0
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-9)

    def test_run_conversion_aligned_timestamps(self, interface, metadata, tmp_path):
        original_timestamps = interface.get_original_timestamps()
        shifted_timestamps = {name: timestamps + 7.0 for name, timestamps in original_timestamps.items()}
        interface.set_aligned_timestamps(shifted_timestamps)
        nwbfile_path = tmp_path / "npm_fiber_photometry_timestamps.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
            timing_source="aligned_timestamps",
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal_region0"]
            # First aligned timestamp is the original 0.0 shifted by 7.0; length matches the stub data.
            assert signal_series.timestamps[0] == 7.0
            assert signal_series.timestamps.shape[0] == signal_series.data.shape[0]
