"""On-data tests for the Neurophotometrics (NPM) fiber photometry interfaces.

The NPM interfaces are thin wrappers over :class:`.CSVFiberPhotometryInterface`, so these read the
real gin stub recordings and check the demultiplexed values against literals verified against the
files. Expected timestamps are irregular (real acquisition), so each series is written with an
explicit timestamps array rather than a rate.
"""

import numpy as np

from neuroconv.datainterfaces import (
    NPMFiberPhotometryInterface,
    NPMLegacyFiberPhotometryInterface,
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
    """The modern (``Flags``-labeled) NPM interface reading the by-column multiplexed stub."""

    data_interface_cls = NPMFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=str(NPM_DATA_PATH / "led_multiplexing" / "by_column" / "PagCeAVgatFear_14421.csv"),
        led_state=17,
        data_columns="Region0G",
        metadata_key="isosbestic_region0",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 Region0G samples of the Flags==17 (isosbestic) channel and their timestamps (seconds).
    expected_response_series_data = np.array(
        [0.0039288397682929, 0.0039215686274509, 0.003860975787101, 0.003856128359873, 0.003844009791803]
    )
    expected_timestamps = np.array([24106.962496, 24107.012512, 24107.062496, 24107.112512, 24107.162528])

    def test_get_available_led_states(self):
        states = self.data_interface_cls.get_available_led_states(self.interface_kwargs["file_path"])
        assert states == [16, 17, 18]

    def test_get_available_regions(self):
        regions = self.data_interface_cls.get_available_regions(self.interface_kwargs["file_path"])
        assert regions == ["Region0G", "Region1G", "Region2G"]


class TestNPMLegacyFiberPhotometryInterface(FiberPhotometryInterfaceTestMixin):
    """The legacy (header-less, row-cycling) NPM interface reading the by-row multiplexed stub."""

    data_interface_cls = NPMLegacyFiberPhotometryInterface
    interface_kwargs = dict(
        file_path=str(NPM_DATA_PATH / "led_multiplexing" / "by_row" / "PagCeAVgatFear_1512_1.csv"),
        number_of_channels=2,
        index=0,
        data_columns=1,
        metadata_key="isosbestic_column1",
    )
    conversion_options = dict(stub_test=True, stub_samples=5)
    save_directory = OUTPUT_PATH

    # First 5 samples of the even-row (index 0) channel, column 1, and their timestamps: the file's
    # millisecond timestamps scaled to seconds by the default time_unit="milliseconds".
    expected_response_series_data = np.array(
        [6558.51912568306, 6568.51366120219, 6566.09836065574, 6562.48087431694, 6575.35519125683]
    )
    expected_timestamps = np.array([40263.5104768, 40263.5642624, 40263.6107904, 40263.6613376, 40263.712960000004])


class TestNPMTimestampColumnSelection:
    """The multi-timestamp NPM file exercises ``timestamps_column`` selection."""

    file_path = str(NPM_DATA_PATH / "multi_timestamp" / "signals.csv")

    def test_defaults_to_first_timestamp_column(self):
        interface = NPMFiberPhotometryInterface(file_path=self.file_path, led_state=1, data_columns="G0")
        assert interface.source_data["timestamps_column"] == "SystemTimestamp"
        np.testing.assert_allclose(interface.get_original_timestamps()[:3], [1800.69552, 1800.820544, 1800.945536])

    def test_explicit_timestamp_column_is_used(self):
        interface = NPMFiberPhotometryInterface(
            file_path=self.file_path, led_state=1, data_columns="G0", timestamps_column="ComputerTimestamp"
        )
        np.testing.assert_allclose(
            interface.get_original_timestamps()[:3], [35205063.952, 35205189.0654, 35205313.9613]
        )
