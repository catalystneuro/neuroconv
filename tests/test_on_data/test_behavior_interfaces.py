import unittest
from datetime import datetime

from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import DeepLabCutInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from .setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestDeepLabCutInterface(DataInterfaceTestMixin, unittest.TestCase):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "config.yaml"),
        subject_name="ind1",
    )
    save_directory = OUTPUT_PATH

    def run_conversion(self, nwbfile_path: str):
        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

    def check_align_starting_time_internal(self):
        pass  # TODO in separate PR

    def check_align_timestamps_internal(self):
        pass  # TODO in separate PR

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimation" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["PoseEstimation"].pose_estimation_series
            expected_pose_estimation_series = ["ind1_leftear", "ind1_rightear", "ind1_snout", "ind1_tailbase"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)
