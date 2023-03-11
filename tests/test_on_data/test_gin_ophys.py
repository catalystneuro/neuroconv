import unittest
from datetime import datetime

import pytest
from hdmf.testing import TestCase
from parameterized import param, parameterized
from roiextractors import NwbSegmentationExtractor
from roiextractors.testing import check_segmentations_equal

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    CaimanSegmentationInterface,
    CnmfeSegmentationInterface,
    ExtractSegmentationInterface,
    Suite2pSegmentationInterface,
)

# enable to run locally in interactive mode
try:
    from .setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH, OUTPUT_PATH

if not OPHYS_DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {OPHYS_DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(param.kwargs['data_interface'].__name__)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestOphysNwbConversions(TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=CaimanSegmentationInterface,
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "caiman" / "caiman_analysis.hdf5")
                ),
            ),
            param(
                data_interface=CnmfeSegmentationInterface,
                interface_kwargs=dict(
                    file_path=str(
                        OPHYS_DATA_PATH
                        / "segmentation_datasets"
                        / "cnmfe"
                        / "2014_04_01_p203_m19_check01_cnmfeAnalysis.mat"
                    )
                ),
            ),
            param(
                data_interface=ExtractSegmentationInterface,
                interface_kwargs=dict(
                    file_path=str(
                        OPHYS_DATA_PATH
                        / "segmentation_datasets"
                        / "extract"
                        / "2014_04_01_p203_m19_check01_extractAnalysis.mat"
                    ),
                    sampling_frequency=15.0,  # typically provided by user
                ),
                case_name="LegacyExtractSegmentation",
            ),
            param(
                data_interface=ExtractSegmentationInterface,
                interface_kwargs=dict(
                    file_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"),
                    sampling_frequency=15.0,  # typically provided by user
                ),
                case_name="NewExtractSegmentation",
            ),
            param(
                data_interface=Suite2pSegmentationInterface,
                interface_kwargs=dict(folder_path=str(OPHYS_DATA_PATH / "segmentation_datasets" / "suite2p")),
            ),
        ],
        name_func=custom_name_func,
    )
    def test_convert_segmentation_extractor_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestSegmentation=data_interface)

        converter = TestConverter(source_data=dict(TestSegmentation=dict(interface_kwargs)))
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        segmentation = converter.data_interface_objects["TestSegmentation"].segmentation_extractor
        nwb_segmentation = NwbSegmentationExtractor(file_path=nwbfile_path)
        check_segmentations_equal(segmentation, nwb_segmentation)

    def test_extract_segmentation_interface_non_default_output_struct_name(self):
        """Test that the value for 'output_struct_name' is propagated to the extractor level
        where an error is raised."""
        file_path = OPHYS_DATA_PATH / "segmentation_datasets" / "extract" / "extract_public_output.mat"
        with self.assertRaisesWith(AssertionError, "Output struct name 'not_output' not found in file."):
            ExtractSegmentationInterface(
                file_path=str(file_path),
                sampling_frequency=15.0,
                output_struct_name="not_output",
            )


if __name__ == "__main__":
    unittest.main()
