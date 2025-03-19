import unittest
from datetime import datetime

import numpy.testing as npt
import pytest
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces import AbfInterface
from neuroconv.tools.neo import get_number_of_electrodes, get_number_of_segments

from ..setup_paths import ECEPHY_DATA_PATH, OUTPUT_PATH

try:
    from parameterized import param, parameterized

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

if not HAVE_PARAMETERIZED:
    pytest.fail("parameterized module is not installed! Please install (`pip install parameterized`).")


def custom_name_func(testcase_func, param_num, param):
    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(param.kwargs['data_interface'].__name__)}"
    )


class TestIcephysNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_recording_list = [
        param(
            data_interface=AbfInterface,
            interface_kwargs=dict(
                file_paths=[str(ECEPHY_DATA_PATH / "axon" / "File_axon_1.abf")],
                icephys_metadata={
                    "recording_sessions": [
                        {"abf_file_name": "File_axon_1.abf", "icephys_experiment_type": "voltage_clamp"}
                    ]
                },
            ),
        )
    ]

    def check_set_aligned_starting_time(self):  # TODO - use the mixin class in the future
        fresh_interface = self.data_interface_cls(file_paths=self.file_paths)

        aligned_starting_time = 1.23
        relative_segment_starting_times = [[0.1]]
        fresh_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=relative_segment_starting_times
        )
        fresh_interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

        neo_reader_starting_times = [reader._t_starts for reader in fresh_interface.readers_list]
        expecting_starting_times = [[1.33]]
        self.assertListEqual(list1=neo_reader_starting_times, list2=expecting_starting_times)

    def check_set_aligned_segment_starting_times(self):
        fresh_interface = self.data_interface_cls(file_paths=self.file_paths)

        aligned_segment_starting_times = [[1.2]]
        fresh_interface.set_aligned_segment_starting_times(
            aligned_segment_starting_times=aligned_segment_starting_times
        )

        neo_reader_starting_times = [reader._t_starts for reader in fresh_interface.readers_list]
        self.assertListEqual(list1=neo_reader_starting_times, list2=aligned_segment_starting_times)

    @parameterized.expand(input=parameterized_recording_list, name_func=custom_name_func)
    def test_convert_abf_to_nwb(self, data_interface, interface_kwargs):
        # NEO reader is the ground truth
        from neo import AxonIO

        self.data_interface_cls = data_interface
        self.file_paths = [interface_kwargs["file_paths"][0]]
        # TODO - in future, add more test cases for multiple file paths

        neo_reader = AxonIO(filename=self.file_paths[0])
        n_segments = get_number_of_segments(neo_reader, block=0)
        n_electrodes = get_number_of_electrodes(neo_reader)

        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestRecording=data_interface)

        converter = TestConverter(source_data=dict(TestRecording=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path", "file_paths"]:
                self.assertIn(
                    member=interface_kwarg, container=converter.data_interface_objects["TestRecording"].source_data
                )
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))

        metadata["Icephys"]["Electrodes"][0].update(cell_id="ID001")

        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            # Test number of traces = n_electrodes * n_segments
            npt.assert_equal(len(nwbfile.acquisition), n_electrodes * n_segments)

            self.check_set_aligned_starting_time()
            self.check_set_aligned_segment_starting_times()

            assert nwbfile.icephys_electrodes["electrode-0"].cell_id == "ID001"


if __name__ == "__main__":
    unittest.main()
