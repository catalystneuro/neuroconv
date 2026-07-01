from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import CSVFiberPhotometryInterface
from neuroconv.utils import dict_deep_update, load_dict_from_file

FIBER_PHOTOMETRY_METADATA_FILE = Path(__file__).parent / "csv_fiber_photometry_metadata.yaml"

# Parameters for the dynamically generated stream CSVs. NUM_SAMPLES exceeds ceil(SAMPLING_RATE) so
# that stub_test (which reads ceil(rate) rows) genuinely truncates the trace. All values are dyadic
# (SAMPLING_RATE is a power of two, data values are multiples of 1/4), so the CSV text round-trips
# losslessly and the written arrays compare exactly-equal on every platform.
SAMPLING_RATE = 128.0
NUM_SAMPLES = 200
STUB_LENGTH = int(np.ceil(SAMPLING_RATE))  # 128
TIMESTAMPS = np.arange(NUM_SAMPLES) / SAMPLING_RATE  # k / 128
SIGNAL_DATA = 0.5 * np.arange(NUM_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ...
CONTROL_DATA = 0.25 * np.arange(NUM_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ...


def _write_stream_csv(path, data):
    """Write one 3-column data stream CSV (sampling_rate only on the first row, NaN elsewhere)."""
    sampling_rate = np.full(NUM_SAMPLES, np.nan)
    sampling_rate[0] = SAMPLING_RATE
    pd.DataFrame({"timestamps": TIMESTAMPS, "data": data, "sampling_rate": sampling_rate}).to_csv(path, index=False)


class TestCSVFiberPhotometryInterface:
    @pytest.fixture
    def csv_folder(self, tmp_path):
        _write_stream_csv(tmp_path / "Sample_Signal_Channel.csv", SIGNAL_DATA)
        _write_stream_csv(tmp_path / "Sample_Control_Channel.csv", CONTROL_DATA)
        # A single-column event CSV to verify stream discovery excludes it.
        (tmp_path / "Sample_TTL.csv").write_text("timestamps\n1.0\n2.0\n")
        return tmp_path

    @pytest.fixture
    def interface(self, csv_folder):
        return CSVFiberPhotometryInterface(folder_path=csv_folder, verbose=False)

    @pytest.fixture
    def metadata(self, interface):
        editable_metadata = load_dict_from_file(FIBER_PHOTOMETRY_METADATA_FILE)
        return dict_deep_update(interface.get_metadata(), editable_metadata)

    def test_construction(self, interface, csv_folder):
        assert interface.source_data["folder_path"] == csv_folder

    def test_get_metadata_does_not_set_session_start_time(self, interface):
        """CSV recordings carry no embedded start time, so the interface must not invent one."""
        metadata = interface.get_metadata()
        assert metadata["NWBFile"].get("session_start_time") is None

    def test_stream_discovery_excludes_event_csv(self, interface):
        """Only the 3-column data CSVs are streams; the single-column TTL CSV is excluded."""
        assert sorted(interface._get_stream_names()) == ["Sample_Control_Channel", "Sample_Signal_Channel"]

    def test_get_original_starting_time_and_rate(self, interface):
        starting_time_and_rate = interface.get_original_starting_time_and_rate()
        assert starting_time_and_rate == {
            "Sample_Signal_Channel": (0.0, SAMPLING_RATE),
            "Sample_Control_Channel": (0.0, SAMPLING_RATE),
        }

    def test_set_aligned_starting_time(self, interface):
        interface.set_aligned_starting_time(aligned_starting_time=10.0)
        timestamps = interface.get_timestamps()
        np.testing.assert_array_equal(timestamps["Sample_Signal_Channel"], TIMESTAMPS + 10.0)
        np.testing.assert_array_equal(timestamps["Sample_Control_Channel"], TIMESTAMPS + 10.0)

    def test_run_conversion_writes_response_series(self, interface, metadata, tmp_path):
        """With stub_test=False the entire trace (all NUM_SAMPLES samples) is written."""
        nwbfile_path = tmp_path / "csv_fiber_photometry.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=False,
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
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA)
            np.testing.assert_array_equal(control_series.data[:], CONTROL_DATA)
            assert signal_series.rate == SAMPLING_RATE
            # Each response series links to its own single-row region of the table.
            assert list(signal_series.fiber_photometry_table_region.data[:]) == [0]
            assert list(control_series.fiber_photometry_table_region.data[:]) == [1]

    def test_run_conversion_stub_test_truncates_trace(self, interface, metadata, tmp_path):
        """With stub_test=True only the first ceil(rate) samples of each trace are written."""
        nwbfile_path = tmp_path / "csv_fiber_photometry_stub.nwb"
        interface.run_conversion(
            nwbfile_path=str(nwbfile_path),
            metadata=metadata,
            overwrite=True,
            stub_test=True,
        )

        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            nwbfile = io.read()
            signal_series = nwbfile.acquisition["calcium_signal"]
            control_series = nwbfile.acquisition["isosbestic_control"]
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA[:STUB_LENGTH])
            np.testing.assert_array_equal(control_series.data[:], CONTROL_DATA[:STUB_LENGTH])
            assert signal_series.rate == SAMPLING_RATE

    def test_run_conversion_aligned_starting_time_and_rate(self, interface, metadata, tmp_path):
        interface.set_aligned_starting_time_and_rate(
            {
                "Sample_Signal_Channel": (5.0, SAMPLING_RATE),
                "Sample_Control_Channel": (5.0, SAMPLING_RATE),
            }
        )
        nwbfile_path = tmp_path / "csv_fiber_photometry_aligned.nwb"
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
            assert signal_series.rate == SAMPLING_RATE
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA[:STUB_LENGTH])

    def test_run_conversion_aligned_timestamps(self, interface, metadata, tmp_path):
        original_timestamps = interface.get_original_timestamps()
        shifted_timestamps = {name: timestamps + 7.0 for name, timestamps in original_timestamps.items()}
        interface.set_aligned_timestamps(shifted_timestamps)
        nwbfile_path = tmp_path / "csv_fiber_photometry_timestamps.nwb"
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
            # The aligned timestamps are the originals shifted by 7.0, truncated to the stub length.
            np.testing.assert_array_equal(signal_series.timestamps[:], (TIMESTAMPS + 7.0)[:STUB_LENGTH])
            np.testing.assert_array_equal(signal_series.data[:], SIGNAL_DATA[:STUB_LENGTH])
