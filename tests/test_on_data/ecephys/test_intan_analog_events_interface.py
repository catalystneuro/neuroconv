"""On-data tests for deriving events from Intan USB-board ADC channels."""

import numpy as np
import pytest
from pydantic import ValidationError
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import IntanAnalogEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanAnalogEventsInterface(EventsInterfaceTestMixin):
    """The RHS fixture has eight ADC inputs and two ADC outputs."""

    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    CONFIGURATION = {"ANALOG-IN-1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]}
    OUTPUT_CONFIGURATION = {"ANALOG-OUT-1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]}
    data_interface_cls = IntanAnalogEventsInterface
    interface_kwargs = dict(file_path=FILE_PATH, detection_configuration=CONFIGURATION)

    def test_configuration_is_required(self):
        with pytest.raises(ValidationError, match="detection_configuration"):
            IntanAnalogEventsInterface(file_path=self.FILE_PATH)

    def test_only_adc_channels_are_accepted(self):
        with pytest.raises(ValueError, match="not one of the file's signals"):
            IntanAnalogEventsInterface(
                file_path=self.FILE_PATH,
                detection_configuration={
                    "RHD2000 auxiliary input channel": [
                        {"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}
                    ]
                },
            )

    def test_writes_configured_events_without_the_raw_trace(self):
        interface = IntanAnalogEventsInterface(
            file_path=self.FILE_PATH,
            detection_configuration=self.CONFIGURATION | self.OUTPUT_CONFIGURATION,
            metadata_key="adc_events",
        )

        assert set(interface._available_signals) == {
            *{f"ANALOG-IN-{index}" for index in range(1, 9)},
            *{f"ANALOG-OUT-{index}" for index in range(1, 3)},
        }
        assert interface.get_metadata()["Events"] == {
            "adc_events": {
                "event_types": {
                    "ANALOG-IN-1": {"event_name": "ANALOG-IN-1"},
                    "ANALOG-OUT-1": {"event_name": "ANALOG-OUT-1"},
                }
            }
        }

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        assert set(nwbfile.events) == {"ANALOG-IN-1", "ANALOG-OUT-1"}
        timestamps = np.asarray(nwbfile.events["ANALOG-IN-1"]["timestamp"][:])
        assert len(timestamps) == 4_072
        np.testing.assert_allclose(timestamps[:3], [0.00016, 0.00032, 0.00048])
