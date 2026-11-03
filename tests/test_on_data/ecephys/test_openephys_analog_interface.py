import pytest
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import OpenEphysBinaryAnalogInterface
from neuroconv.tools.testing.data_interface_mixins import TimeSeriesInterfaceTestMixin

try:
    from ..setup_paths import ECEPHY_DATA_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH

if not ECEPHY_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {ECEPHY_DATA_PATH}!")


class TestOpenEphysBinaryAnalogInterface(TimeSeriesInterfaceTestMixin):
    data_interface_cls = OpenEphysBinaryAnalogInterface
    interface_kwargs = dict(
        folder_path=ECEPHY_DATA_PATH / "openephysbinary" / "neural_and_non_neural_data_mixed",
        stream_name="Rhythm_FPGA-100.0_ADC",
    )
    expected_time_series_names = ("TimeSeriesOpenEphysAnalog",)

    def check_extracted_metadata(self, metadata):
        assert set(metadata["TimeSeries"]) == {"open_ephys_analog"}


def test_openephys_analog_interface(tmp_path):
    """Test the OpenEphysBinaryAnalogInterface with sample data containing analog channels."""
    folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "neural_and_non_neural_data_mixed"
    stream_name = "Rhythm_FPGA-100.0_ADC"

    interface = OpenEphysBinaryAnalogInterface(folder_path=folder_path, stream_name=stream_name)

    # Run conversion
    nwbfile_path = tmp_path / "openephys_analog_test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    # Verify the output
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()

        # Check that the TimeSeries was added to acquisition
        assert "TimeSeriesOpenEphysAnalog" in nwbfile.acquisition
        time_series = nwbfile.acquisition["TimeSeriesOpenEphysAnalog"]

        # Check properties of the TimeSeries
        assert time_series.name == "TimeSeriesOpenEphysAnalog"
        assert "ADC data acquired with OpenEphys system." in time_series.description

        # Check data dimensions
        assert len(time_series.data.shape) == 2  # [time, channels]
        assert time_series.data.shape[1] == len(interface.analog_channel_ids)


def test_openephys_analog_interface_nidq(tmp_path):
    """Test the OpenEphysBinaryAnalogInterface with data obtained using the NI-DAQmx plugin."""
    folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "v0.6.x_neuropixels_with_sync"
    open_ephys_binary = ECEPHY_DATA_PATH / "openephysbinary"
    stream_name = "Record Node 104#NI-DAQmx-103.PXIe-6341"
    assert (
        folder_path.exists()
    ), f"Test data folder does not exist: {folder_path}, available, available folders are: {list(open_ephys_binary.iterdir())}"

    interface = OpenEphysBinaryAnalogInterface(folder_path=folder_path, stream_name=stream_name)

    # Run conversion
    nwbfile_path = tmp_path / "openephys_analog_neuropixels_sync_test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True)

    # Verify the output
    with NWBHDF5IO(nwbfile_path, "r") as io:
        nwbfile = io.read()

        # Check that the TimeSeries was added to acquisition
        assert "TimeSeriesOpenEphysAnalog" in nwbfile.acquisition
        time_series = nwbfile.acquisition["TimeSeriesOpenEphysAnalog"]

        # Check properties of the TimeSeries
        assert time_series.name == "TimeSeriesOpenEphysAnalog"
        assert "ADC data acquired with OpenEphys system." in time_series.description

        # Check data dimensions
        assert len(time_series.data.shape) == 2  # [time, channels]
        assert time_series.data.shape[1] == len(interface.analog_channel_ids)


def test_time_series_name_is_independent_of_metadata_key():
    """The key addresses the entry; ``time_series_name`` names the object, independently."""
    folder_path = ECEPHY_DATA_PATH / "openephysbinary" / "neural_and_non_neural_data_mixed"
    stream_name = "Rhythm_FPGA-100.0_ADC"

    custom_interface = OpenEphysBinaryAnalogInterface(
        folder_path=folder_path,
        stream_name=stream_name,
        metadata_key="my_adc",
        time_series_name="TimeSeriesMyADC",
    )
    time_series_metadata = custom_interface.get_metadata()["TimeSeries"]
    assert set(time_series_metadata) == {"my_adc"}
    assert time_series_metadata["my_adc"]["name"] == "TimeSeriesMyADC"
