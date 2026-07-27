"""On-data tests for the Neurophotometrics (NPM) fiber photometry interface.

The NPM interface is a thin wrapper over :class:`.CSVFiberPhotometryInterface`, so these read the
real gin stub recordings and check the demultiplexed values against literals verified against the
files. Expected timestamps are irregular (real acquisition), so each series is written with an
explicit timestamps array rather than a rate.
"""

import numpy as np
import pytest

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


class TestNPMFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """The NPM interface reading the by-column multiplexed stub, selecting the 415 nm channel."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=str(NPM_DATA_PATH / "led_multiplexing" / "by_column" / "PagCeAVgatFear_14421.csv"),
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
        wavelengths = self.data_interface_cls.get_available_excitation_wavelengths(self.interface_kwargs["file_path"])
        assert wavelengths == [415, 470]


class TestNPMTimestampColumnSelection:
    """The multi-timestamp NPM file (SystemTimestamp/ComputerTimestamp, no ``Timestamp``) exercises
    ``timestamps_column`` selection: the default fails loudly, an explicit column is used."""

    file_path = str(NPM_DATA_PATH / "multi_timestamp" / "signals.csv")

    def test_default_timestamp_column_missing_fails_loudly(self):
        with pytest.raises(AssertionError, match="Timestamp"):
            NPMFiberPhotometryInterface(file_path=self.file_path, excitation_wavelength_in_nm=415, data_columns="G0")

    def test_system_timestamp_column_is_used(self):
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path,
            excitation_wavelength_in_nm=415,
            data_columns="G0",
            timestamps_column="SystemTimestamp",
        )
        np.testing.assert_allclose(interface.get_original_timestamps()[:3], [1800.69552, 1800.820544, 1800.945536])

    def test_computer_timestamp_column_is_used(self):
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path,
            excitation_wavelength_in_nm=415,
            data_columns="G0",
            timestamps_column="ComputerTimestamp",
        )
        np.testing.assert_allclose(
            interface.get_original_timestamps()[:3], [35205063.952, 35205189.0654, 35205313.9613]
        )
