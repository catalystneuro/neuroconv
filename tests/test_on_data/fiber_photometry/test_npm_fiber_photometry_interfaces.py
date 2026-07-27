"""On-data tests for the Neurophotometrics (NPM) fiber photometry interface.

The NPM interface is a thin wrapper over :class:`.CSVFiberPhotometryInterface`: it auto-detects the
``Flags``/``LedState`` column, masks its three lowest bits to the excitation LED, and reads the one
channel matching a given ``excitation_wavelength_in_nm``. Each distinct configuration is validated
end-to-end through ``FiberPhotometryInterfaceTestMixin`` (one subclass per configuration, checking the
written NWB series against literals verified against the file); construction/validation error paths,
which the mixin cannot express, live in a dedicated plain class. Expected timestamps are irregular
(real acquisition), so each series is written with an explicit timestamps array rather than a rate.
"""

import numpy as np
import pytest
from pydantic import ValidationError

from neuroconv.datainterfaces import (
    NPMFiberPhotometryInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    FiberPhotometryInterfaceTestMixin,
)

try:
    from ..setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

NPM_DATA_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "NPM"
# A modern Flags-labeled recording (Flags 16/17/18 -> no-LED startup frame, 415 nm, 470 nm).
BY_COLUMN_FILE = str(NPM_DATA_PATH / "led_multiplexing" / "by_column" / "PagCeAVgatFear_14421.csv")
# A LedState-labeled recording with two timestamp columns and no ``Timestamp`` (LedState 1/2/7).
MULTI_TIMESTAMP_FILE = str(NPM_DATA_PATH / "multi_timestamp" / "signals.csv")


class TestNPMFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm (isosbestic) channel of the by-column Flags-labeled stub."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=BY_COLUMN_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="Region0G",
        metadata_key="isosbestic_region0",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 Region0G samples of the 415 nm (Flags==17, isosbestic) channel and their timestamps (seconds).
    expected_response_series_data = np.array(
        [0.0039288397682929, 0.0039215686274509, 0.003860975787101, 0.003856128359873, 0.003844009791803]
    )
    expected_timestamps = np.array([24106.962496, 24107.012512, 24107.062496, 24107.112512, 24107.162528])

    def test_get_available_excitation_wavelengths(self):
        """The single-LED wavelengths are surfaced; the no-LED startup frame (Flags 16) is not."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(BY_COLUMN_FILE) == [415, 470]


class TestNPMFiberPhotometrySignalChannel(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 470 nm (signal) channel of the same stub -- a different channel and timebase,
    selecting the Flags==18 rows."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=BY_COLUMN_FILE,
        excitation_wavelength_in_nm=470,
        data_columns="Region0G",
        metadata_key="signal_region0",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 Region0G samples of the 470 nm (Flags==18) channel and their timestamps (seconds).
    expected_response_series_data = np.array(
        [0.00762985045687, 0.007620155602414, 0.007620155602414, 0.0071596500157541, 0.0071644974429821]
    )
    expected_timestamps = np.array([24106.937504, 24106.98752, 24107.037504, 24107.08752, 24107.137504])


class TestNPMFiberPhotometryMultiRegion(FiberPhotometryInterfaceTestMixin):
    """Round-trip several region columns of one channel column-stacked into one multi-channel series."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=BY_COLUMN_FILE,
        excitation_wavelength_in_nm=415,
        data_columns=["Region0G", "Region1G", "Region2G"],
        metadata_key="isosbestic_all_regions",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 rows of [Region0G, Region1G, Region2G] for the 415 nm channel, in column order.
    expected_response_series_data = np.array(
        [
            [0.0039288397682929, 0.0039264160546789, 0.0076003514613392],
            [0.0039215686274509, 0.0039264160546789, 0.0075517943026267],
            [0.003860975787101, 0.0038706706415569, 0.0072905105438401],
            [0.003856128359873, 0.0038706706415569, 0.0072234554199038],
            [0.003844009791803, 0.0038658232143289, 0.0071679615242323],
        ]
    )
    expected_timestamps = np.array([24106.962496, 24107.012512, 24107.062496, 24107.112512, 24107.162528])


class TestNPMFiberPhotometryMultiTimestamp(FiberPhotometryInterfaceTestMixin):
    """Round-trip the 415 nm channel of the LedState-labeled two-timestamp file, choosing an explicit
    ``SystemTimestamp`` column. Also exercises ``LedState`` (vs ``Flags``) detection and the
    ``timestamps_column`` selection this file requires (it has no default ``Timestamp`` column)."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=MULTI_TIMESTAMP_FILE,
        excitation_wavelength_in_nm=415,
        data_columns="G0",
        timestamps_column="SystemTimestamp",
        metadata_key="isosbestic_g0",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 G0 samples of the 415 nm (LedState==1) channel and its SystemTimestamp values (seconds).
    expected_response_series_data = np.array(
        [0.0771836007130125, 0.0790616246498599, 0.0791030048382989, 0.0790839062897886, 0.0789618877854172]
    )
    expected_timestamps = np.array([1800.69552, 1800.820544, 1800.945536, 1801.070528, 1801.19552])

    def test_ledstate_detection_excludes_all_leds_frame(self):
        """The state column is found whether named ``Flags`` or ``LedState``; the all-LEDs frame
        (LedState 7) is not a single-LED channel and is left out."""
        assert self.data_interface_cls.get_available_excitation_wavelengths(MULTI_TIMESTAMP_FILE) == [415, 470]

    def test_computer_timestamp_column_is_used(self):
        """An explicit ``ComputerTimestamp`` selects that column instead of ``SystemTimestamp``."""
        interface = self.data_interface_cls(
            file_path=MULTI_TIMESTAMP_FILE,
            excitation_wavelength_in_nm=415,
            data_columns="G0",
            timestamps_column="ComputerTimestamp",
        )
        np.testing.assert_allclose(
            interface.get_original_timestamps()[:3], [35205063.952, 35205189.0654, 35205313.9613]
        )

    def test_default_timestamp_column_missing_fails_loudly(self):
        """This file has no ``Timestamp`` column, so the default fails loudly at construction."""
        with pytest.raises(AssertionError, match="Timestamp"):
            self.data_interface_cls(file_path=MULTI_TIMESTAMP_FILE, excitation_wavelength_in_nm=415, data_columns="G0")


class TestNPMFiberPhotometryConstruction:
    """Construction/validation error paths, which the round-trip mixin cannot express."""

    def test_absent_wavelength_raises(self):
        """The by-column stub carries only 415/470 nm, so requesting 560 nm fails loudly."""
        with pytest.raises(AssertionError, match="560 nm"):
            NPMFiberPhotometryInterface(
                file_path=BY_COLUMN_FILE, excitation_wavelength_in_nm=560, data_columns="Region0G"
            )

    def test_unknown_wavelength_rejected(self):
        """excitation_wavelength_in_nm is a closed set; an out-of-set value is rejected up front."""
        with pytest.raises(ValidationError):
            NPMFiberPhotometryInterface(
                file_path=BY_COLUMN_FILE, excitation_wavelength_in_nm=500, data_columns="Region0G"
            )

    def test_missing_state_column_raises(self, tmp_path):
        """A headered file without a Flags/LedState column fails loudly. No gin fixture has this shape
        (every real NPM recording carries the state column), so a representative file is generated here."""
        file_path = tmp_path / "no_state.csv"
        file_path.write_text("Timestamp,Region0G\n0.0,1.0\n1.0,2.0\n")
        with pytest.raises(ValueError, match="Flags"):
            NPMFiberPhotometryInterface(
                file_path=str(file_path), excitation_wavelength_in_nm=415, data_columns="Region0G"
            )
