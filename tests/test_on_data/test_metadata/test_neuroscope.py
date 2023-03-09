import unittest
from datetime import datetime

import numpy as np
import numpy.testing as npt
import pytest
from parameterized import param, parameterized
from pynwb import NWBHDF5IO
from spikeinterface.extractors import NwbRecordingExtractor

from neuroconv import NWBConverter
from neuroconv.datainterfaces import NeuroScopeRecordingInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH

if not DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    interface_name = param.kwargs["data_interface"].__name__
    reduced_interface_name = interface_name.replace("Recording", "").replace("Interface", "").replace("Sorting", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestNeuroscopeNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_gains(self, name, conversion_options):
        input_gain = 2.0
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=input_gain)

        nwbfile_path = str(self.savedir / f"test_neuroscope_gains_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            # output_channel_conversion = nwbfile.acquisition["ElectricalSeriesRaw"].channel_conversion[:]
            # input_gain_array = np.ones_like(output_channel_conversion) * input_gain
            # np.testing.assert_array_almost_equal(input_gain_array, output_channel_conversion)
            assert nwbfile.acquisition["ElectricalSeries"].channel_conversion is None

            nwb_recording = NwbRecordingExtractor(file_path=nwbfile_path)
            nwb_recording_gains = nwb_recording.get_channel_gains()
            npt.assert_almost_equal(input_gain * np.ones_like(nwb_recording_gains), nwb_recording_gains)

    @parameterized.expand(
        input=[
            param(
                name="complete",
                conversion_options=None,
            ),
            param(name="stub", conversion_options=dict(TestRecording=dict(stub_test=True))),
        ]
    )
    def test_neuroscope_dtype(self, name, conversion_options):
        interface_kwargs = dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat"), gain=2.0)

        nwbfile_path = str(self.savedir / f"test_neuroscope_dtype_{name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, conversion_options=conversion_options
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            output_dtype = nwbfile.acquisition["ElectricalSeries"].data.dtype
            self.assertEqual(first=output_dtype, second=np.dtype("int16"))

    def test_neuroscope_starting_time(self):
        nwbfile_path = str(self.savedir / "testing_start_time.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=NeuroScopeRecordingInterface)

        converter = TestConverter(
            source_data=dict(TestRecording=dict(file_path=str(DATA_PATH / "neuroscope" / "test1" / "test1.dat")))
        )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        starting_time = 123.0
        converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            conversion_options=dict(TestRecording=dict(starting_time=starting_time)),
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            self.assertEqual(first=starting_time, second=nwbfile.acquisition["ElectricalSeries"].starting_time)


if __name__ == "__main__":
    unittest.main()
