from datetime import datetime

from neuroconv.datainterfaces import AxonAnalogInterface
from neuroconv.tools.testing.data_interface_mixins import TimeSeriesInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

AXON_DATA_PATH = ECEPHY_DATA_PATH / "axon" / "intracellular_data"


class TestAxonAnalogInterfaceTemperature(TimeSeriesInterfaceTestMixin):
    """The temperature probe of a 16-channel gap-free file, next to cells and spare inputs of other units."""

    data_interface_cls = AxonAnalogInterface
    interface_kwargs = dict(
        file_path=AXON_DATA_PATH / "abf2_gapfree_max_channels.abf",
        channels_to_include=["Tmp"],
    )
    expected_time_series_names = ("TimeSeriesAxonAnalog",)
    expected_temporal_alignment_keys = ("axon_analog_0",)

    def check_extracted_metadata(self, metadata):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 7, 15, 13, 10, 31)
        assert metadata["TimeSeries"] == {
            "axon_analog": dict(
                name="TimeSeriesAxonAnalog",
                description="Analog channels from an Axon Binary Format file. Channels are ['Tmp'] in that order.",
            )
        }


class TestAxonAnalogInterfaceOpticalChannels(TimeSeriesInterfaceTestMixin):
    """The two optical channels of an episodic FRET recording, one series per sweep."""

    data_interface_cls = AxonAnalogInterface
    interface_kwargs = dict(
        file_path=AXON_DATA_PATH / "abf2_optical_fret_channels.abf",
        channels_to_include=["YFP", "CFP"],
    )
    expected_time_series_names = (
        "TimeSeriesAxonAnalogSegment0",
        "TimeSeriesAxonAnalogSegment1",
        "TimeSeriesAxonAnalogSegment2",
        "TimeSeriesAxonAnalogSegment3",
        "TimeSeriesAxonAnalogSegment4",
        "TimeSeriesAxonAnalogSegment5",
        "TimeSeriesAxonAnalogSegment6",
        "TimeSeriesAxonAnalogSegment7",
        "TimeSeriesAxonAnalogSegment8",
        "TimeSeriesAxonAnalogSegment9",
        "TimeSeriesAxonAnalogSegment10",
        "TimeSeriesAxonAnalogSegment11",
        "TimeSeriesAxonAnalogSegment12",
    )
    expected_temporal_alignment_keys = (
        "axon_analog_0",
        "axon_analog_1",
        "axon_analog_2",
        "axon_analog_3",
        "axon_analog_4",
        "axon_analog_5",
        "axon_analog_6",
        "axon_analog_7",
        "axon_analog_8",
        "axon_analog_9",
        "axon_analog_10",
        "axon_analog_11",
        "axon_analog_12",
    )


class TestAxonAnalogInterfaceStimulusMonitor(TimeSeriesInterfaceTestMixin):
    """The stimulus channel of a spinal cord file that records a cell, a ventral root and the stimulus."""

    data_interface_cls = AxonAnalogInterface
    interface_kwargs = dict(
        file_path=AXON_DATA_PATH / "spinal_cord_clamp_examples" / "24102012_Current_Clamp.abf",
        channels_to_include=["stim"],
    )
    expected_time_series_names = ("TimeSeriesAxonAnalog",)
    expected_temporal_alignment_keys = ("axon_analog_0",)
