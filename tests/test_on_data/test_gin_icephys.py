import tempfile
import unittest
import pytest
import numpy.testing as npt
import os
from pathlib import Path
from pynwb import NWBHDF5IO

from nwb_conversion_tools import (
    NWBConverter,
    AbfNeoDataInterface
)
from nwb_conversion_tools.utils.neo import (
    get_number_of_electrodes,
    get_number_of_segments
)

try:
    from parameterized import parameterized, param

    HAVE_PARAMETERIZED = True
except ImportError:
    HAVE_PARAMETERIZED = False

# GIN dataset: https://gin.g-node.org/NeuralEnsemble/ephy_testing_data
if os.getenv("CI"):
    LOCAL_PATH = Path(".")  # Must be set to "." for CI
    print("Running GIN tests on Github CI!")
else:
    # Override the LOCAL_PATH to a point on your local system that contains the dataset folder
    # Use DANDIHub at hub.dandiarchive.org for open, free use of data found in the /shared/catalystneuro/ directory
    LOCAL_PATH = Path("/shared/catalystneuro/")
    print("Running GIN tests locally!")

DATA_PATH = LOCAL_PATH / "ephy_testing_data"
HAVE_DATA = DATA_PATH.exists()

SAVE_OUTPUTS = False
if SAVE_OUTPUTS:
    OUTPUT_PATH = LOCAL_PATH / "example_nwb_output"
    OUTPUT_PATH.mkdir(exist_ok=True)
else:
    OUTPUT_PATH = Path(tempfile.mkdtemp())

if not HAVE_PARAMETERIZED:
    pytest.fail("parameterized module is not installed! Please install (`pip install parameterized`).")

if not HAVE_DATA:
    pytest.fail(f"No ephy_testing_data folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(param.kwargs['data_interface'].__name__)}"
    )


class TestIcephysNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_recording_list = [
        param(
            data_interface=AbfNeoDataInterface,
            interface_kwargs=dict(files_paths=[str(DATA_PATH / "axon" / "File_axon_1.abf")]),
        )
    ]

    @parameterized.expand(input=parameterized_recording_list, name_func=custom_name_func)
    def test_convert_abf_to_nwb(self, data_interface, interface_kwargs):
        # NEO reader is the ground truth
        from neo import AxonIO
        neo_reader = AxonIO(filename=interface_kwargs["files_paths"][0])
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
        # metadata["NWBFile"].update(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            # Test number of traces = n_electrodes * n_segments
            npt.assert_equal(len(nwbfile.acquisition), n_electrodes * n_segments)


if __name__ == "__main__":
    unittest.main()
