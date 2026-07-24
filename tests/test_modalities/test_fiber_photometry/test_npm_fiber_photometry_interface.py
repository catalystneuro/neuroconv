"""Synthetic tests for the Neurophotometrics (NPM) fiber photometry interfaces.

The NPM interfaces are thin wrappers over :class:`.CSVFiberPhotometryInterface`: they auto-detect the
``Flags``/``LedState`` column (modern) or take a row-cycling stride (legacy) and translate the
selection into a demux config. These tests build small synthetic NPM-shaped CSVs so the demuxed
values are hand-computable literals, and reuse ``FiberPhotometryInterfaceTestMixin`` for the
round-trip. All values are dyadic (a power-of-two sampling rate, quarter-integer data) so the CSV
text round-trips losslessly and the written arrays compare exactly-equal on every platform.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from neuroconv.datainterfaces import (
    NPMFiberPhotometryInterface,
    NPMLegacyFiberPhotometryInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

# One channel's samples are read every other row (the two LED states interleave frame-by-frame), so
# the per-channel timebase steps by 2 * ROW_DT. ROW_DT = 1/128 makes the per-channel rate 64 Hz.
ROW_DT = 1.0 / 128.0
CHANNEL_RATE = 1.0 / (2.0 * ROW_DT)  # 64.0 Hz
NUM_CHANNEL_SAMPLES = 8
STUB_SAMPLES = 5
ISOSBESTIC_DATA = 0.5 * np.arange(NUM_CHANNEL_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ... (LedState/Flags 17)
SIGNAL_DATA = 0.25 * np.arange(NUM_CHANNEL_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ... (LedState/Flags 18)


def _build_modern_npm_frame(state_column: str) -> pd.DataFrame:
    """Build a modern NPM frame: a startup frame (state 16) then interleaved isosbestic/signal rows.

    The isosbestic rows (state 17) carry ``ISOSBESTIC_DATA`` in every region column and land on a
    timebase starting at 0.0 stepping by 2 * ROW_DT; the signal rows (state 18) carry ``SIGNAL_DATA``.
    """
    num_rows = 1 + 2 * NUM_CHANNEL_SAMPLES  # startup + interleaved pairs
    state = np.empty(num_rows, dtype=int)
    state[0] = 16  # startup/all-LEDs-on frame, excluded by not being any interface's led_state
    state[1::2] = 17  # isosbestic
    state[2::2] = 18  # signal
    # Row r has timestamp (r - 1) * ROW_DT, so the first isosbestic row (r=1) starts the channel at 0.0.
    timestamp = (np.arange(num_rows) - 1) * ROW_DT
    region = np.zeros(num_rows)
    region[1::2] = ISOSBESTIC_DATA
    region[2::2] = SIGNAL_DATA
    return pd.DataFrame(
        {
            "FrameCounter": np.arange(num_rows),
            "Timestamp": timestamp,
            state_column: state,
            "Region0G": region,
            "Region1G": region + 100.0,
            "Region2G": region + 200.0,
        }
    )


class TestNPMFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """The modern (``Flags``/``LedState``-labeled) NPM interface (one FiberPhotometryResponseSeries)."""

    data_interface_cls = NPMFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # led_state 17 (isosbestic), Region0G: the first STUB_SAMPLES isosbestic samples on the 64 Hz timebase.
    expected_response_series_data = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    expected_starting_time = 0.0
    expected_rate = CHANNEL_RATE

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):
        cls = request.cls
        data_directory = tmp_path_factory.mktemp("npm_fiber_photometry")
        file_path = data_directory / "PagCe_14421.csv"
        _build_modern_npm_frame(state_column="Flags").to_csv(file_path, index=False)
        cls.file_path = file_path
        cls.interface_kwargs = dict(
            file_path=file_path,
            led_state=17,
            data_columns="Region0G",
            metadata_key="isosbestic_region0",
        )

    def test_detects_ledstate_column(self, tmp_path):
        """The state column is auto-detected whether the file uses ``Flags`` or ``LedState``."""
        path = tmp_path / "ledstate.csv"
        _build_modern_npm_frame(state_column="LedState").to_csv(path, index=False)
        interface = NPMFiberPhotometryInterface(file_path=path, led_state=17, data_columns="Region0G")
        np.testing.assert_array_equal(interface._read_response_data(), ISOSBESTIC_DATA)

    def test_led_state_selects_one_channel(self):
        """``led_state`` reads exactly the rows of that state; the startup frame (16) is left out."""
        signal = NPMFiberPhotometryInterface(file_path=self.file_path, led_state=18, data_columns="Region0G")
        np.testing.assert_array_equal(signal._read_response_data(), SIGNAL_DATA)
        np.testing.assert_array_equal(
            signal.get_original_timestamps(), ROW_DT + np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_multiple_regions_stack_into_multichannel_series(self):
        """Several region columns for one led_state column-stack into one multi-channel series."""
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path, led_state=17, data_columns=["Region0G", "Region1G", "Region2G"]
        )
        data = interface._read_response_data()
        assert data.shape == (NUM_CHANNEL_SAMPLES, 3)
        np.testing.assert_array_equal(data[:, 0], ISOSBESTIC_DATA)
        np.testing.assert_array_equal(data[:, 1], ISOSBESTIC_DATA + 100.0)
        np.testing.assert_array_equal(data[:, 2], ISOSBESTIC_DATA + 200.0)

    def test_get_available_led_states(self):
        """All state values are surfaced, including the startup frame (16) the user then skips."""
        assert NPMFiberPhotometryInterface.get_available_led_states(self.file_path) == [16, 17, 18]

    def test_default_metadata_key_distinct_per_channel(self):
        """Two interfaces reading the same file get distinct auto-generated metadata keys."""
        isosbestic = NPMFiberPhotometryInterface(file_path=self.file_path, led_state=17, data_columns="Region0G")
        signal = NPMFiberPhotometryInterface(file_path=self.file_path, led_state=18, data_columns="Region0G")
        assert isosbestic.metadata_key != signal.metadata_key

    def test_missing_state_column_raises(self, tmp_path):
        """A file without a Flags/LedState column fails loudly at construction."""
        path = tmp_path / "no_state.csv"
        pd.DataFrame({"Timestamp": [0.0, 1.0], "Region0G": [1.0, 2.0]}).to_csv(path, index=False)
        with pytest.raises(ValueError, match="Flags"):
            NPMFiberPhotometryInterface(file_path=path, led_state=17, data_columns="Region0G")

    def test_default_timestamp_column_reads_the_timestamp_column(self):
        """The default ``Timestamp`` is used for the standard single-timestamp file."""
        interface = NPMFiberPhotometryInterface(file_path=self.file_path, led_state=17, data_columns="Region0G")
        assert interface.source_data["timestamps_column"] == "Timestamp"
        np.testing.assert_array_equal(
            interface.get_original_timestamps(), np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_dual_timestamp_file_requires_explicit_column(self, tmp_path):
        """A file with SystemTimestamp/ComputerTimestamp has no ``Timestamp``, so the default fails loudly."""
        frame = _build_modern_npm_frame(state_column="LedState")
        # A second, 10x-coarser timestamp column; the demuxed channel's first value distinguishes them.
        frame.insert(2, "ComputerTimestamp", frame["Timestamp"] * 10.0)
        frame = frame.rename(columns={"Timestamp": "SystemTimestamp"})
        path = tmp_path / "two_timestamps.csv"
        frame.to_csv(path, index=False)

        with pytest.raises(AssertionError, match="Timestamp"):
            NPMFiberPhotometryInterface(file_path=path, led_state=17, data_columns="Region0G")

        system = NPMFiberPhotometryInterface(
            file_path=path, led_state=17, data_columns="Region0G", timestamps_column="SystemTimestamp"
        )
        np.testing.assert_array_equal(system.get_original_timestamps(), np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE)

        computer = NPMFiberPhotometryInterface(
            file_path=path, led_state=17, data_columns="Region0G", timestamps_column="ComputerTimestamp"
        )
        np.testing.assert_array_equal(
            computer.get_original_timestamps(), 10.0 * np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_unknown_timestamp_column_rejected(self):
        """timestamps_column is a closed set; an out-of-set name is rejected before construction."""
        with pytest.raises(ValidationError):
            NPMFiberPhotometryInterface(
                file_path=self.file_path, led_state=17, data_columns="Region0G", timestamps_column="WallClock"
            )


def _build_legacy_npm_frame() -> pd.DataFrame:
    """Build a legacy header-less NPM frame: column 0 timestamps (milliseconds), columns 1-3 regions.

    Rows cycle through two channels; even rows (index 0) carry ``ISOSBESTIC_DATA``, odd rows
    (index 1) carry ``SIGNAL_DATA``. Timestamps step by ROW_DT seconds (expressed in milliseconds).
    """
    num_rows = 2 * NUM_CHANNEL_SAMPLES
    timestamp_ms = np.arange(num_rows) * ROW_DT * 1e3
    region = np.zeros(num_rows)
    region[0::2] = ISOSBESTIC_DATA
    region[1::2] = SIGNAL_DATA
    return pd.DataFrame({0: timestamp_ms, 1: region, 2: region + 100.0, 3: region + 200.0})


class TestNPMLegacyFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """The legacy (header-less, row-cycling) NPM interface (one FiberPhotometryResponseSeries)."""

    data_interface_cls = NPMLegacyFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # Channel index 0, data column 1: the first STUB_SAMPLES isosbestic samples on the 64 Hz timebase.
    expected_response_series_data = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
    expected_starting_time = 0.0
    expected_rate = CHANNEL_RATE

    @pytest.fixture(scope="class", autouse=True)
    def setup_test(self, request, tmp_path_factory):
        cls = request.cls
        data_directory = tmp_path_factory.mktemp("npm_legacy_fiber_photometry")
        file_path = data_directory / "PagCe_1512_1.csv"
        _build_legacy_npm_frame().to_csv(file_path, index=False, header=False)
        cls.file_path = file_path
        cls.interface_kwargs = dict(
            file_path=file_path,
            number_of_channels=2,
            index=0,
            data_columns=1,
            time_unit="milliseconds",
            metadata_key="isosbestic_column1",
        )

    def test_index_selects_cyclic_channel(self):
        """``index`` reads every other row; milliseconds are scaled to seconds via ``time_unit``."""
        signal = NPMLegacyFiberPhotometryInterface(
            file_path=self.file_path, number_of_channels=2, index=1, data_columns=1, time_unit="milliseconds"
        )
        np.testing.assert_array_equal(signal._read_response_data(), SIGNAL_DATA)
        np.testing.assert_allclose(
            signal.get_original_timestamps(), ROW_DT + np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_index_beyond_channels_raises(self):
        """A stride index >= number_of_channels addresses no channel and is rejected up front."""
        with pytest.raises(ValidationError, match="must be <"):
            NPMLegacyFiberPhotometryInterface(file_path=self.file_path, number_of_channels=2, index=2, data_columns=1)
