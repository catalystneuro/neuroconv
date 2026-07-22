import numpy as np
import pandas as pd
import pytest

from neuroconv.datainterfaces import (
    CSVFiberPhotometryInterface,
    MultiFileCSVFiberPhotometryInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

# Parameters for the dynamically generated CSVs. All values are dyadic (SAMPLING_RATE is a power of
# two, data values are multiples of 1/4), so the CSV text round-trips losslessly and the written
# arrays compare exactly-equal on every platform.
SAMPLING_RATE = 128.0
NUM_SAMPLES = 20
STUB_SAMPLES = 5
TIMESTAMPS = np.arange(NUM_SAMPLES) / SAMPLING_RATE  # k / 128
SIGNAL_DATA = 0.5 * np.arange(NUM_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ...
CONTROL_DATA = 0.25 * np.arange(NUM_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ...


class TestCSVFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """Single-file CSV fiber photometry interface (one FiberPhotometryResponseSeries)."""

    data_interface_cls = CSVFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # First STUB_SAMPLES samples of the "data" column, written from the bare scaffold metadata.
    expected_response_series_data = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    # Regular timestamps (k / 128), so the series is written as starting_time + rate.
    expected_starting_time = 0.0
    expected_rate = SAMPLING_RATE

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):
        cls = request.cls
        data_directory = tmp_path_factory.mktemp("csv_fiber_photometry")
        signal_path = data_directory / "Sample_Signal_Channel.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        cls.signal_path = signal_path
        cls.interface_kwargs = dict(
            file_path=signal_path,
            data_columns="data",
            timestamps_column="timestamps",
            metadata_key="calcium_signal",
        )

    def test_get_available_columns(self):
        assert CSVFiberPhotometryInterface.get_available_columns(file_path=self.signal_path) == ["timestamps", "data"]

    def test_metadata_key_generated_from_file_name(self):
        """With no explicit metadata_key, it is derived from the file name."""
        interface = CSVFiberPhotometryInterface(
            file_path=self.signal_path, data_columns="data", timestamps_column="timestamps"
        )
        assert interface.metadata_key == "fiber_photometry_sample_signal_channel"
        assert interface.metadata_key in interface.get_metadata()["FiberPhotometry"]

    def test_read_header_less_csv_by_integer_position(self, tmp_path):
        """Integer column identifiers address a header-less CSV by position."""
        path = tmp_path / "header_less.csv"
        pd.DataFrame({"a": TIMESTAMPS, "b": SIGNAL_DATA}).to_csv(path, index=False, header=False)
        interface = CSVFiberPhotometryInterface(file_path=path, data_columns=1, timestamps_column=0)
        np.testing.assert_array_equal(interface.get_original_timestamps(), TIMESTAMPS)
        np.testing.assert_array_equal(interface._read_response_data(), SIGNAL_DATA)

    def test_multiple_data_columns_stack_into_multichannel_series(self, tmp_path):
        """A list of data_columns from one file is column-stacked into one multi-channel series."""
        path = tmp_path / "wide.csv"
        pd.DataFrame({"time": TIMESTAMPS, "signal": SIGNAL_DATA, "control": CONTROL_DATA}).to_csv(path, index=False)
        interface = CSVFiberPhotometryInterface(
            file_path=path, data_columns=["signal", "control"], timestamps_column="time"
        )
        data = interface._read_response_data()
        assert data.shape == (NUM_SAMPLES, 2)
        np.testing.assert_array_equal(data[:, 0], SIGNAL_DATA)
        np.testing.assert_array_equal(data[:, 1], CONTROL_DATA)

    def test_missing_data_column_raises_at_construction(self, tmp_path):
        """A file missing a named data column fails loudly up front, not at read time."""
        path = tmp_path / "signal.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(path, index=False)
        with pytest.raises(AssertionError, match="not found"):
            CSVFiberPhotometryInterface(file_path=path, data_columns="missing", timestamps_column="timestamps")

    def test_read_kwargs_propagate_to_column_check_and_data_read(self, tmp_path):
        """read_kwargs reach both the up-front column check and the data read, not just the latter.

        A semicolon-delimited file: without sep=";" the bare comma parser sees one fused column, so the
        column check would wrongly reject a column that is present. The dialect must reach every read.
        """
        path = tmp_path / "semicolon.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(path, index=False, sep=";")
        interface = CSVFiberPhotometryInterface(
            file_path=path, data_columns="data", timestamps_column="timestamps", read_kwargs=dict(sep=";")
        )
        np.testing.assert_array_equal(interface.get_original_timestamps(), TIMESTAMPS)
        np.testing.assert_array_equal(interface._read_response_data(), SIGNAL_DATA)

    def test_get_available_columns_respects_read_kwargs(self, tmp_path):
        """get_available_columns parses the header with the caller's dialect, not the bare comma parser."""
        path = tmp_path / "semicolon.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(path, index=False, sep=";")
        # Bare parser fuses the header into a single column; the ";" dialect splits it correctly.
        assert CSVFiberPhotometryInterface.get_available_columns(file_path=path) == ["timestamps;data"]
        assert CSVFiberPhotometryInterface.get_available_columns(file_path=path, read_kwargs=dict(sep=";")) == [
            "timestamps",
            "data",
        ]


class TestMultiFileCSVFiberPhotometryInterface:
    """Aggregating several per-channel CSV files into one FiberPhotometryResponseSeries.

    These are focused unit tests for the aggregator's novel behavior (multi-file stacking, timestamp
    alignment, and up-front validation). The full metadata → NWB roundtrip is exercised by
    ``TestCSVFiberPhotometryInterface`` above, whose NWB-assembly path the aggregator inherits
    unchanged from ``BaseFiberPhotometryInterface``.
    """

    @pytest.fixture
    def signal_and_control_paths(self, tmp_path):
        """Two per-channel CSVs (GuPPy layout) on a common timebase."""
        signal_path = tmp_path / "Sample_Signal_Channel.csv"
        control_path = tmp_path / "Sample_Control_Channel.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": CONTROL_DATA}).to_csv(control_path, index=False)
        return signal_path, control_path

    @pytest.fixture
    def interface(self, signal_and_control_paths):
        signal_path, control_path = signal_and_control_paths
        return MultiFileCSVFiberPhotometryInterface(
            file_paths=[signal_path, control_path], data_columns="data", timestamps_column="timestamps"
        )

    def test_files_stack_into_multichannel_series(self, interface):
        """Per-channel CSVs are column-stacked into one multi-channel series, in file order, on the
        first file's timestamps."""
        np.testing.assert_array_equal(interface.get_original_timestamps(), TIMESTAMPS)
        data = interface._read_response_data()
        assert data.shape == (NUM_SAMPLES, 2)
        np.testing.assert_array_equal(data[:, 0], SIGNAL_DATA)
        np.testing.assert_array_equal(data[:, 1], CONTROL_DATA)

    def test_metadata_key_generated_from_file_names(self, interface):
        """With no explicit metadata_key, it is derived from all file names, in order."""
        assert interface.metadata_key == "fiber_photometry_sample_signal_channel_sample_control_channel"
        assert interface.metadata_key in interface.get_metadata()["FiberPhotometry"]

    def test_secondary_file_may_omit_timestamps_column(self, tmp_path):
        """A secondary file whose (redundant) timestamps column is absent is still aggregated."""
        signal_path = tmp_path / "signal.csv"
        control_path = tmp_path / "control.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        pd.DataFrame({"data": CONTROL_DATA}).to_csv(control_path, index=False)  # no timestamps column
        interface = MultiFileCSVFiberPhotometryInterface(
            file_paths=[signal_path, control_path], data_columns="data", timestamps_column="timestamps"
        )
        data = interface._read_response_data()
        assert data.shape == (NUM_SAMPLES, 2)
        np.testing.assert_array_equal(data[:, 0], SIGNAL_DATA)
        np.testing.assert_array_equal(data[:, 1], CONTROL_DATA)

    def test_misaligned_timestamps_raise(self, tmp_path):
        """A secondary file carrying a different timebase fails loudly instead of being mis-timed."""
        signal_path = tmp_path / "signal.csv"
        control_path = tmp_path / "control.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        # Same length, but shifted by 100 s -- a different timebase from the first file.
        pd.DataFrame({"timestamps": TIMESTAMPS + 100.0, "data": CONTROL_DATA}).to_csv(control_path, index=False)
        with pytest.raises(AssertionError, match="do not match"):
            MultiFileCSVFiberPhotometryInterface(
                file_paths=[signal_path, control_path], data_columns="data", timestamps_column="timestamps"
            )

    def test_timestampless_file_wrong_length_raises(self, tmp_path):
        """A timestamp-less secondary file of the wrong length fails loudly at construction."""
        signal_path = tmp_path / "signal.csv"
        control_path = tmp_path / "control.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)  # 20 rows
        pd.DataFrame({"data": CONTROL_DATA[:10]}).to_csv(control_path, index=False)  # 10 rows, no timestamps
        with pytest.raises(AssertionError, match="rows"):
            MultiFileCSVFiberPhotometryInterface(
                file_paths=[signal_path, control_path], data_columns="data", timestamps_column="timestamps"
            )

    def test_missing_data_column_raises_at_construction(self, tmp_path):
        """A file missing a named data column fails loudly up front, not at read time."""
        signal_path = tmp_path / "signal.csv"
        control_path = tmp_path / "control.csv"
        pd.DataFrame({"timestamps": TIMESTAMPS, "data": SIGNAL_DATA}).to_csv(signal_path, index=False)
        pd.DataFrame({"timestamps": TIMESTAMPS, "other": CONTROL_DATA}).to_csv(control_path, index=False)
        with pytest.raises(AssertionError, match="not found"):
            MultiFileCSVFiberPhotometryInterface(
                file_paths=[signal_path, control_path], data_columns="data", timestamps_column="timestamps"
            )
