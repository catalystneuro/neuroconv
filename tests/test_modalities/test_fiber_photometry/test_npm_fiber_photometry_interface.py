"""Synthetic tests for the Neurophotometrics (NPM) fiber photometry interface.

The NPM interface is a thin wrapper over :class:`.CSVFiberPhotometryInterface`: it auto-detects the
``Flags``/``LedState`` column, masks its three lowest bits to the excitation LED, and translates a
requested ``excitation_wavelength_in_nm`` into the set of state values that carry it. These tests
build small synthetic NPM-shaped CSVs so the demuxed values are hand-computable literals, and reuse
``FiberPhotometryInterfaceTestMixin`` for the round-trip. All values are dyadic (a power-of-two
sampling rate, quarter-integer data) so the CSV text round-trips losslessly and the written arrays
compare exactly-equal on every platform.
"""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from neuroconv.datainterfaces import (
    NPMFiberPhotometryInterface,
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
ISOSBESTIC_DATA = 0.5 * np.arange(NUM_CHANNEL_SAMPLES) + 0.5  # 0.5, 1.0, 1.5, ... (415 nm, state 17)
SIGNAL_DATA = 0.25 * np.arange(NUM_CHANNEL_SAMPLES) + 0.25  # 0.25, 0.5, 0.75, ... (470 nm, state 18)


def _build_modern_npm_frame(state_column: str) -> pd.DataFrame:
    """Build an NPM frame: a startup frame (state 16) then interleaved 415 nm / 470 nm rows.

    The isosbestic rows (state 17 -> 415 nm) carry ``ISOSBESTIC_DATA`` in every region column and land
    on a timebase starting at 0.0 stepping by 2 * ROW_DT; the signal rows (state 18 -> 470 nm) carry
    ``SIGNAL_DATA``.
    """
    num_rows = 1 + 2 * NUM_CHANNEL_SAMPLES  # startup + interleaved pairs
    state = np.empty(num_rows, dtype=int)
    state[0] = 16  # startup/all-outputs-high frame (masks to 0, no LED), not an excitation channel
    state[1::2] = 17  # 415 nm
    state[2::2] = 18  # 470 nm
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
    """The NPM interface (``Flags``/``LedState``-labeled, one FiberPhotometryResponseSeries)."""

    data_interface_cls = NPMFiberPhotometryInterface
    conversion_options = dict(stub_test=True, stub_samples=STUB_SAMPLES)

    # 415 nm (isosbestic), Region0G: the first STUB_SAMPLES isosbestic samples on the 64 Hz timebase.
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
            excitation_wavelength_in_nm=415,
            data_columns="Region0G",
            metadata_key="isosbestic_region0",
        )

    def test_detects_ledstate_column(self, tmp_path):
        """The state column is auto-detected whether the file uses ``Flags`` or ``LedState``."""
        path = tmp_path / "ledstate.csv"
        _build_modern_npm_frame(state_column="LedState").to_csv(path, index=False)
        interface = NPMFiberPhotometryInterface(
            file_path=path, excitation_wavelength_in_nm=415, data_columns="Region0G"
        )
        np.testing.assert_array_equal(interface._read_response_data(), ISOSBESTIC_DATA)

    def test_wavelength_selects_one_channel(self):
        """``excitation_wavelength_in_nm`` reads exactly its channel's rows; the startup frame is left out."""
        signal = NPMFiberPhotometryInterface(
            file_path=self.file_path, excitation_wavelength_in_nm=470, data_columns="Region0G"
        )
        np.testing.assert_array_equal(signal._read_response_data(), SIGNAL_DATA)
        np.testing.assert_array_equal(
            signal.get_original_timestamps(), ROW_DT + np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_multiple_regions_stack_into_multichannel_series(self):
        """Several region columns for one wavelength column-stack into one multi-channel series."""
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path, excitation_wavelength_in_nm=415, data_columns=["Region0G", "Region1G", "Region2G"]
        )
        data = interface._read_response_data()
        assert data.shape == (NUM_CHANNEL_SAMPLES, 3)
        np.testing.assert_array_equal(data[:, 0], ISOSBESTIC_DATA)
        np.testing.assert_array_equal(data[:, 1], ISOSBESTIC_DATA + 100.0)
        np.testing.assert_array_equal(data[:, 2], ISOSBESTIC_DATA + 200.0)

    def test_get_available_excitation_wavelengths(self):
        """The single-LED wavelengths are surfaced; the startup frame (state 16, no LED) is not."""
        assert NPMFiberPhotometryInterface.get_available_excitation_wavelengths(self.file_path) == [415, 470]

    def test_absent_wavelength_raises(self):
        """Requesting a wavelength the file does not carry fails loudly at construction."""
        with pytest.raises(AssertionError, match="560 nm"):
            NPMFiberPhotometryInterface(
                file_path=self.file_path, excitation_wavelength_in_nm=560, data_columns="Region0G"
            )

    def test_default_metadata_key_distinct_per_channel(self):
        """Two interfaces reading the same file get distinct auto-generated metadata keys."""
        isosbestic = NPMFiberPhotometryInterface(
            file_path=self.file_path, excitation_wavelength_in_nm=415, data_columns="Region0G"
        )
        signal = NPMFiberPhotometryInterface(
            file_path=self.file_path, excitation_wavelength_in_nm=470, data_columns="Region0G"
        )
        assert isosbestic.metadata_key != signal.metadata_key

    def test_missing_state_column_raises(self, tmp_path):
        """A file without a Flags/LedState column fails loudly at construction."""
        path = tmp_path / "no_state.csv"
        pd.DataFrame({"Timestamp": [0.0, 1.0], "Region0G": [1.0, 2.0]}).to_csv(path, index=False)
        with pytest.raises(ValueError, match="Flags"):
            NPMFiberPhotometryInterface(file_path=path, excitation_wavelength_in_nm=415, data_columns="Region0G")

    def test_default_timestamp_column_reads_the_timestamp_column(self):
        """The default ``Timestamp`` is used for the standard single-timestamp file."""
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path, excitation_wavelength_in_nm=415, data_columns="Region0G"
        )
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
            NPMFiberPhotometryInterface(file_path=path, excitation_wavelength_in_nm=415, data_columns="Region0G")

        system = NPMFiberPhotometryInterface(
            file_path=path,
            excitation_wavelength_in_nm=415,
            data_columns="Region0G",
            timestamps_column="SystemTimestamp",
        )
        np.testing.assert_array_equal(system.get_original_timestamps(), np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE)

        computer = NPMFiberPhotometryInterface(
            file_path=path,
            excitation_wavelength_in_nm=415,
            data_columns="Region0G",
            timestamps_column="ComputerTimestamp",
        )
        np.testing.assert_array_equal(
            computer.get_original_timestamps(), 10.0 * np.arange(NUM_CHANNEL_SAMPLES) / CHANNEL_RATE
        )

    def test_unknown_timestamp_column_rejected(self):
        """timestamps_column is a closed set; an out-of-set name is rejected before construction."""
        with pytest.raises(ValidationError):
            NPMFiberPhotometryInterface(
                file_path=self.file_path,
                excitation_wavelength_in_nm=415,
                data_columns="Region0G",
                timestamps_column="WallClock",
            )

    def test_unknown_wavelength_rejected(self):
        """excitation_wavelength_in_nm is a closed set; an out-of-set value is rejected up front."""
        with pytest.raises(ValidationError):
            NPMFiberPhotometryInterface(
                file_path=self.file_path, excitation_wavelength_in_nm=560.5, data_columns="Region0G"
            )
