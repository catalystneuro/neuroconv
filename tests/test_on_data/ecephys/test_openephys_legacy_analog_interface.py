import re
from datetime import datetime

import pytest

from neuroconv.datainterfaces import OpenEphysLegacyAnalogInterface
from neuroconv.tools.testing.data_interface_mixins import TimeSeriesInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

# A GUI 0.4 session holding both analog streams next to 16 electrode channels
AUX_AND_ADC_FOLDER_PATH = ECEPHY_DATA_PATH / "openephys" / "v0.4.x_aux_and_adc_channels" / "1544_2023-04-21_09-55-34_of"


class TestOpenEphysLegacyAnalogInterfaceADC(TimeSeriesInterfaceTestMixin):
    data_interface_cls = OpenEphysLegacyAnalogInterface
    interface_kwargs = dict(folder_path=AUX_AND_ADC_FOLDER_PATH, stream_name="Signals ADC")
    expected_time_series_names = ("TimeSeriesOpenEphysLegacyADC",)
    expected_temporal_alignment_keys = ("open_ephys_legacy_adc_0",)

    def check_extracted_metadata(self, metadata):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 4, 21)
        assert metadata["TimeSeries"] == {
            "open_ephys_legacy_adc": dict(
                name="TimeSeriesOpenEphysLegacyADC",
                description=(
                    "Analog data acquired with the OpenEphys legacy format, stream 'Signals ADC'. Channels are "
                    "['ADC1', 'ADC2', 'ADC3', 'ADC4', 'ADC5', 'ADC6', 'ADC7', 'ADC8'] in that order."
                ),
            )
        }


class TestOpenEphysLegacyAnalogInterfaceAUX(TimeSeriesInterfaceTestMixin):
    data_interface_cls = OpenEphysLegacyAnalogInterface
    interface_kwargs = dict(folder_path=AUX_AND_ADC_FOLDER_PATH, stream_name="Signals AUX")
    expected_time_series_names = ("TimeSeriesOpenEphysLegacyAUX",)
    expected_temporal_alignment_keys = ("open_ephys_legacy_aux_0",)

    def check_extracted_metadata(self, metadata):
        assert metadata["TimeSeries"] == {
            "open_ephys_legacy_aux": dict(
                name="TimeSeriesOpenEphysLegacyAUX",
                description=(
                    "Analog data acquired with the OpenEphys legacy format, stream 'Signals AUX'. Channels are "
                    "['AUX1', 'AUX2', 'AUX3'] in that order."
                ),
            )
        }


class TestOpenEphysLegacyAnalogInterfaceRecordNode(TimeSeriesInterfaceTestMixin):
    """The legacy engine of GUI 0.6, which writes into a Record Node folder, with only the analog inputs."""

    data_interface_cls = OpenEphysLegacyAnalogInterface
    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH
        / "openephys"
        / "v0.6.x_adc_channels"
        / "LARRY_2025-10-20_13-14-15_PHY_DAY1_RUN4"
        / "Record Node 106"
    )
    expected_time_series_names = ("TimeSeriesOpenEphysLegacyADC",)
    expected_temporal_alignment_keys = ("open_ephys_legacy_adc_0",)


def test_stream_name_is_required_when_the_folder_holds_both_analog_streams():
    expected_error_msg = (
        "The folder holds more than one analog stream, ['Signals ADC', 'Signals AUX']. "
        "Choose one with the `stream_name` argument."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error_msg)):
        OpenEphysLegacyAnalogInterface(folder_path=AUX_AND_ADC_FOLDER_PATH)


def test_electrode_stream_raises():
    expected_error_msg = (
        "The stream 'Signals CH' is not an analog stream of this folder. Its analog streams are "
        "['Signals ADC', 'Signals AUX']. For the electrode channels use `OpenEphysLegacyRecordingInterface`."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error_msg)):
        OpenEphysLegacyAnalogInterface(folder_path=AUX_AND_ADC_FOLDER_PATH, stream_name="Signals CH")
