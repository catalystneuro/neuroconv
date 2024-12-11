import numpy as np
import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import SpikeGLXNIDQInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")


def test_nidq_interface_digital_data(tmp_path):

    nwbfile_path = tmp_path / "nidq_test_digital.nwb"
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "DigitalChannelTest_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert len(nwbfile.acquisition) == 1  # Only one channel has data for this set
        events = nwbfile.acquisition["EventsNIDQDigitalChannelXD0"]
        assert events.name == "EventsNIDQDigitalChannelXD0"
        assert events.timestamps.size == 326
        assert len(nwbfile.devices) == 1

        data = events.data
        # Check that there is one followed by 0
        np.sum(data == 1) == 163
        np.sum(data == 0) == 163


def test_nidq_interface_analog_data(tmp_path):

    nwbfile_path = tmp_path / "nidq_test_analog.nwb"
    folder_path = ECEPHY_DATA_PATH / "spikeglx" / "Noise4Sam_g0"
    interface = SpikeGLXNIDQInterface(folder_path=folder_path)
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()
        assert len(nwbfile.acquisition) == 1  # The time series object
        time_series = nwbfile.acquisition["TimeSeriesNIDQ"]
        assert time_series.name == "TimeSeriesNIDQ"
        expected_description = "Analog data from the NIDQ board. Channels are ['XA0' 'XA1' 'XA2' 'XA3' 'XA4' 'XA5' 'XA6' 'XA7'] in that order."
        assert time_series.description == expected_description
        number_of_samples = time_series.data.shape[0]
        assert number_of_samples == 60_864
        number_of_channels = time_series.data.shape[1]
        assert number_of_channels == 8

        assert len(nwbfile.devices) == 1
