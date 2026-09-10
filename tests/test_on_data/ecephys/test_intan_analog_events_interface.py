"""On-data tests for deriving events from Intan USB-board ADC channels."""

import numpy as np
import pytest
from pydantic import ValidationError
from pynwb import read_nwb

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
    data_interface_cls = IntanAnalogEventsInterface
    interface_kwargs = dict(file_path=FILE_PATH, detection_configuration=CONFIGURATION)

    def test_configuration_is_required(self):
        with pytest.raises(ValidationError, match="detection_configuration"):
            IntanAnalogEventsInterface(file_path=self.FILE_PATH)

    def check_extracted_metadata(self, metadata):
        assert metadata["Events"] == {
            "intan_analog_events": {"event_types": {"ANALOG-IN-1": {"event_name": "ANALOG-IN-1"}}}
        }

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)

        assert not nwbfile.acquisition
        assert set(nwbfile.events) == {"ANALOG-IN-1"}
        timestamps = np.asarray(nwbfile.events["ANALOG-IN-1"]["timestamp"][:])
        assert len(timestamps) == 4_072
        np.testing.assert_allclose(timestamps[:3], [0.00016, 0.00032, 0.00048])
