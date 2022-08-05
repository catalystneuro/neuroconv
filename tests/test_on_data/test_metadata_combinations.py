import unittest
from datetime import datetime

from parameterized import parameterized, param

from neuroconv.datainterfaces.ophys.suite2p import Suite2pSegmentationInterface
from neuroconv.datainterfaces.ophys.tiff import TiffImagingInterface
from neuroconv import NWBConverter
from .setup_paths import OPHYS_DATA_PATH


TiffImagingInterface_source_data = dict(
    file_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Tif" / "demoMovie.tif"), sampling_frequency=15.0
)
Suite2pSegmentationInterface_source_data = dict(folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p"))

interface_to_source_data_map = dict(
    TiffImagingInterface=TiffImagingInterface_source_data,
    Suite2pSegmentationInterface=Suite2pSegmentationInterface_source_data,
)

interface_to_class_map = dict(
    TiffImagingInterface=TiffImagingInterface,
    Suite2pSegmentationInterface=Suite2pSegmentationInterface,
)

interfaces_to_combine = ["TiffImagingInterface", "Suite2pSegmentationInterface"]


def custom_name_func(testcase_func, param_num, param):
    return f"{testcase_func.__name__}_{param_num}" f"_{param.kwargs.get('case_name', '')}"


class TestConversionCombinations(unittest.TestCase):
    parameterized_list = list()

    param_case = param(
        interfaces_to_combine=["TiffImagingInterface", "Suite2pSegmentationInterface"],
        case_name="-".join(interfaces_to_combine).replace("Interface", ""),
    )
    parameterized_list.append(param_case)

    param_case = param(
        interfaces_to_combine=["Suite2pSegmentationInterface", "TiffImagingInterface"],
        case_name="-".join(interfaces_to_combine),
    )
    parameterized_list.append(param_case)

    @parameterized.expand(input=parameterized_list, name_func=custom_name_func)
    def test_interface_combination(self, interfaces_to_combine, case_name=""):
        class TestConverter(NWBConverter):
            data_interface_classes = {
                interface: interface_to_class_map[interface] for interface in interfaces_to_combine
            }

        source_data = {interface: interface_to_source_data_map[interface] for interface in interfaces_to_combine}
        converter = TestConverter(source_data=source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        converter.validate_metadata(metadata=metadata)
