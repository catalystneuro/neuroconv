from pathlib import Path

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import NPMFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file

from ..setup_paths import OPHYS_DATA_PATH

NPM_FOLDER = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM" / "sampleData_NPM_1"
FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "npm_fiber_photometry_metadata.yaml"

# Values demultiplexed from bl72bl82_12feb2024_fp.csv with the default (SystemTimestamp, seconds)
# settings. The LedState column interleaves two channels: state 1 (chev/isosbestic, first at row 2,
# G0 = 0.020567264) and state 2 (chod/signal, first at row 1, G0 = 0.017824438). Each channel keeps
# every other frame for 3609 samples; the per-channel rate and second timestamp follow from the
# SystemTimestamp spacing (1891.379168 - 1891.345856 = 0.033312 s between chev frames).
EXPECTED_RATE = 30.009459340799644
EXPECTED_SAMPLES_PER_CHANNEL = 3609
EXPECTED_SIGNAL_FIRST_VALUE = 0.017824438
EXPECTED_CONTROL_FIRST_VALUE = 0.020567264
EXPECTED_SECOND_TIMESTAMP = 0.033312000000023545


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
        """The raw interleaved CSV demultiplexes into one chev (isosbestic) and one chod (signal)
        channel; the 2-column stimuli CSV is excluded (it belongs to the events interface)."""
        assert sorted(interface._get_stream_names()) == ["file0_chev1", "file0_chod1"]

    def test_demultiplexed_values(self, interface):
        """Each channel keeps every other frame, normalized to start at zero."""
        signal = interface._read_stream("file0_chod1")
        control = interface._read_stream("file0_chev1")
        assert signal["data"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
        assert control["data"].shape[0] == EXPECTED_SAMPLES_PER_CHANNEL
        np.testing.assert_allclose(signal["data"][0], EXPECTED_SIGNAL_FIRST_VALUE, rtol=1e-9)
        np.testing.assert_allclose(control["data"][0], EXPECTED_CONTROL_FIRST_VALUE, rtol=1e-9)
        np.testing.assert_allclose(signal["timestamps"][0], 0.0, atol=1e-12)
        np.testing.assert_allclose(control["timestamps"][1], EXPECTED_SECOND_TIMESTAMP, rtol=1e-9)
        np.testing.assert_allclose(signal["rate"], EXPECTED_RATE, rtol=1e-9)

    def test_timestamp_column_selection(self):
        """Selecting ComputerTimestamp (a different column with a much larger scale) changes the
        per-channel rate, confirming the timestamp-column argument is honored."""
        default_interface = NPMFiberPhotometryInterface(folder_path=NPM_FOLDER, verbose=False)
        computer_interface = NPMFiberPhotometryInterface(
            folder_path=NPM_FOLDER, timestamp_column_name="ComputerTimestamp", verbose=False
        )
        default_rate = default_interface._read_stream("file0_chev1")["rate"]
        computer_rate = computer_interface._read_stream("file0_chev1")["rate"]
        np.testing.assert_allclose(default_rate, EXPECTED_RATE, rtol=1e-9)
        assert not np.isclose(default_rate, computer_rate)

    def test_get_original_starting_time_and_rate(self, interface):
        starting_time_and_rate = interface.get_original_starting_time_and_rate()
        assert set(starting_time_and_rate) == {"file0_chev1", "file0_chod1"}
        for starting_time, rate in starting_time_and_rate.values():
            assert starting_time == 0.0
            np.testing.assert_allclose(rate, EXPECTED_RATE, rtol=1e-9)

    def test_set_aligned_starting_time(self, interface):
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        timestamps = interface.get_timestamps()
        assert timestamps["file0_chev1"][0] == 10.0
        assert timestamps["file0_chod1"][0] == 10.0

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
            assert response_series_names == {"calcium_signal", "isosbestic_control"}

            fiber_photometry_table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
            assert len(fiber_photometry_table) == 2

            signal_series = nwbfile.acquisition["calcium_signal"]
            control_series = nwbfile.acquisition["isosbestic_control"]
            # stub_test reads ~1 second (ceil(rate)) of samples.
            assert signal_series.data.shape[0] == int(np.ceil(EXPECTED_RATE))
            np.testing.assert_allclose(signal_series.data[0], EXPECTED_SIGNAL_FIRST_VALUE, rtol=1e-9)
            np.testing.assert_allclose(control_series.data[0], EXPECTED_CONTROL_FIRST_VALUE, rtol=1e-9)
            np.testing.assert_allclose(signal_series.rate, EXPECTED_RATE, rtol=1e-9)
            # Each response series links to its own single-row region of the table.
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]
            assert list(control_series.fiber_photometry_table_region.data[:]) == [1]

    def test_run_conversion_aligned_starting_time_and_rate(self, interface, metadata, tmp_path):
        interface.set_aligned_starting_time_and_rate(
            {
                "file0_chev1": (5.0, EXPECTED_RATE),
                "file0_chod1": (5.0, EXPECTED_RATE),
            }
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
            signal_series = nwbfile.acquisition["calcium_signal"]
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
            signal_series = nwbfile.acquisition["calcium_signal"]
            # First aligned timestamp is the original 0.0 shifted by 7.0; length matches the stub data.
            assert signal_series.timestamps[0] == 7.0
            assert signal_series.timestamps.shape[0] == signal_series.data.shape[0]
