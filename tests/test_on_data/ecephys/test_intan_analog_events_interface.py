"""On-data tests for deriving events from Intan USB-board ADC channels."""

import re

import numpy as np
import pytest
from pynwb import read_nwb

from neuroconv.datainterfaces import IntanAnalogEventsInterface
from neuroconv.tools.testing.data_interface_mixins import EventsInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH


class TestIntanAnalogEventsInterfaceErrors:
    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "test_tetrode_240502_162925" / "test_tetrode_240502_162925.rhd"
    CONFIGURATION = {"ANALOG-IN-1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]}

    def test_no_adc_streams_raises(self):
        expected_error = f"'{self.FILE_PATH}' carries no channels in its ADC input or output streams."
        with pytest.raises(ValueError, match=re.escape(expected_error)):
            IntanAnalogEventsInterface(
                file_path=self.FILE_PATH,
                detection_configuration=self.CONFIGURATION,
                saved_files_are_split=True,
            )


class TestIntanAnalogEventsInterface(EventsInterfaceTestMixin):
    """The RHS fixture has eight ADC inputs and two ADC outputs."""

    FILE_PATH = ECEPHY_DATA_PATH / "intan" / "rhs_stim_data_single_file_format" / "intanTestFile.rhs"
    CONFIGURATION = {"ANALOG-IN-1": [{"signal_conditioning": {"binarize": "midpoint"}, "detection": "rising"}]}
    METADATA_KEY = "intan_analog_events"
    data_interface_cls = IntanAnalogEventsInterface
    interface_kwargs = dict(
        file_path=FILE_PATH,
        detection_configuration=CONFIGURATION,
        metadata_key=METADATA_KEY,
    )

    def check_extracted_metadata(self, metadata):
        assert metadata["Events"] == {
            self.METADATA_KEY: {"event_types": {"ANALOG-IN-1": {"event_name": "ANALOG-IN-1"}}}
        }

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)

        assert not nwbfile.acquisition
        assert set(nwbfile.events) == {"ANALOG-IN-1"}
        timestamps = np.asarray(nwbfile.events["ANALOG-IN-1"]["timestamp"][:])
        assert len(timestamps) == 4_072
        np.testing.assert_allclose(timestamps[:3], [0.00016, 0.00032, 0.00048])
