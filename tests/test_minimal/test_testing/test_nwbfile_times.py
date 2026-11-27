import numpy as np
from pynwb import TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.testing._nwbfile_times import _get_nwbfile_times


class TestGetNWBFileTimes:
    def test_stimulus_template_is_left_out(self):
        # The template's times are relative to its own start, so only the response's session times are collected.
        nwbfile = mock_NWBFile()
        nwbfile.add_acquisition(
            TimeSeries(name="Response", data=[1.0, 2.0, 3.0], unit="V", starting_time=5.0, rate=10.0)
        )
        nwbfile.add_stimulus_template(
            TimeSeries(name="Template", data=[1.0, 2.0, 3.0], unit="A", starting_time=0.0, rate=10.0)
        )

        times = _get_nwbfile_times(nwbfile)

        assert list(times) == ["Response/timestamps"]
        np.testing.assert_allclose(times["Response/timestamps"], [5.0, 5.1, 5.2])
