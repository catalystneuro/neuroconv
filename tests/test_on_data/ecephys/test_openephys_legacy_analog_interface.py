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
# A GUI 0.4 session with the auxiliary inputs of two headstages and no analog inputs of the acquisition board
AUX_WITHOUT_ADC_FOLDER_PATH = (
    ECEPHY_DATA_PATH / "openephys" / "v0.4.x_aux_channels_without_adc" / "629146_2018-04-20_pure tones"
)


class TestOpenEphysLegacyAnalogInterfaceADC(TimeSeriesInterfaceTestMixin):
    data_interface_cls = OpenEphysLegacyAnalogInterface
    interface_kwargs = dict(folder_path=AUX_AND_ADC_FOLDER_PATH)
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


def test_folder_without_analog_inputs_raises():
    folder_path = AUX_WITHOUT_ADC_FOLDER_PATH
    expected_error_msg = (
        f"The folder '{folder_path}' holds no analog inputs of the acquisition board (stream 'Signals ADC'). "
        "Its streams are ['Signals CH', 'Signals AUX']."
    )
    with pytest.raises(ValueError, match=re.escape(expected_error_msg)):
        OpenEphysLegacyAnalogInterface(folder_path=folder_path)
