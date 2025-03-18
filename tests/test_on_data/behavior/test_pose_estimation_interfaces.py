import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import sleap_io
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from parameterized import param, parameterized
from pynwb import NWBHDF5IO

from neuroconv.datainterfaces import (
    DeepLabCutInterface,
    LightningPoseDataInterface,
    SLEAPInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)
from neuroconv.utils import DeepDict

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

from importlib.metadata import version as importlib_version
from platform import python_version
from sys import platform

from packaging import version

python_version = version.parse(python_version())
# TODO: remove after this is merged https://github.com/talmolab/sleap-io/pull/143 and released
ndx_pose_version = version.parse(importlib_version("ndx-pose"))


@pytest.mark.skipif(ndx_pose_version < version.parse("0.2.0"), reason="Interface requires ndx-pose version >= 0.2.0")
class TestLightningPoseDataInterface(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
    )
    conversion_options = dict(reference_frame="(0,0) corresponds to the top left corner of the video.")
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):

        cls = request.cls

        cls.pose_estimation_name = "PoseEstimation"
        cls.original_video_height = 406
        cls.original_video_width = 396
        cls.expected_keypoint_names = [
            "paw1LH_top",
            "paw2LF_top",
            "paw3RF_top",
            "paw4RH_top",
            "tailBase_top",
            "tailMid_top",
            "nose_top",
            "obs_top",
            "paw1LH_bot",
            "paw2LF_bot",
            "paw3RF_bot",
            "paw4RH_bot",
            "tailBase_bot",
            "tailMid_bot",
            "nose_bot",
            "obsHigh_bot",
            "obsLow_bot",
        ]
        cls.expected_metadata = DeepDict(
            PoseEstimation=dict(
                name=cls.pose_estimation_name,
                description="Contains the pose estimation series for each keypoint.",
                scorer="heatmap_tracker",
                source_software="LightningPose",
                camera_name="CameraPoseEstimation",
            )
        )
        cls.expected_metadata[cls.pose_estimation_name].update(
            {
                keypoint_name: dict(
                    name=f"PoseEstimationSeries{keypoint_name}",
                    description=f"The estimated position (x, y) of {keypoint_name} over time.",
                )
                for keypoint_name in cls.expected_keypoint_names
            }
        )

        cls.test_data = pd.read_csv(cls.interface_kwargs["file_path"], header=[0, 1, 2])["heatmap_tracker"]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 11, 9, 10, 14, 37, 0)
        assert self.pose_estimation_name in metadata["Behavior"]
        assert metadata["Behavior"][self.pose_estimation_name] == self.expected_metadata[self.pose_estimation_name]

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import PoseEstimation, PoseEstimationSeries

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            # Replacing assertIn with pytest-style assert
            assert "behavior" in nwbfile.processing
            assert self.pose_estimation_name in nwbfile.processing["behavior"].data_interfaces
            assert "Skeletons" in nwbfile.processing["behavior"].data_interfaces

            pose_estimation_container = nwbfile.processing["behavior"].data_interfaces[self.pose_estimation_name]

            # Replacing assertIsInstance with pytest-style assert
            assert isinstance(pose_estimation_container, PoseEstimation)

            pose_estimation_metadata = self.expected_metadata[self.pose_estimation_name]

            # Replacing assertEqual with pytest-style assert
            assert pose_estimation_container.description == pose_estimation_metadata["description"]
            assert pose_estimation_container.scorer == pose_estimation_metadata["scorer"]
            assert pose_estimation_container.source_software == pose_estimation_metadata["source_software"]

            # Using numpy's assert_array_equal
            assert_array_equal(
                pose_estimation_container.dimensions[:], [[self.original_video_height, self.original_video_width]]
            )

            # Replacing assertEqual with pytest-style assert
            assert len(pose_estimation_container.pose_estimation_series) == len(self.expected_keypoint_names)

            assert pose_estimation_container.skeleton.nodes[:].tolist() == self.expected_keypoint_names

            for keypoint_name in self.expected_keypoint_names:
                series_metadata = pose_estimation_metadata[keypoint_name]

                # Replacing assertIn with pytest-style assert
                assert series_metadata["name"] in pose_estimation_container.pose_estimation_series

                pose_estimation_series = pose_estimation_container.pose_estimation_series[series_metadata["name"]]

                # Replacing assertIsInstance with pytest-style assert
                assert isinstance(pose_estimation_series, PoseEstimationSeries)

                # Replacing assertEqual with pytest-style assert
                assert pose_estimation_series.unit == "px"
                assert pose_estimation_series.description == series_metadata["description"]
                assert pose_estimation_series.reference_frame == self.conversion_options["reference_frame"]

                test_data = self.test_data[keypoint_name]

                # Using numpy's assert_array_equal
                assert_array_equal(pose_estimation_series.data[:], test_data[["x", "y"]].values)


@pytest.mark.skipif(ndx_pose_version < version.parse("0.2.0"), reason="Interface requires ndx-pose version >= 0.2.0")
class TestLightningPoseDataInterfaceWithStubTest(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
    )

    conversion_options = dict(stub_test=True)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            pose_estimation_container = nwbfile.processing["behavior"].data_interfaces["PoseEstimation"]
            for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
                assert pose_estimation_series.data.shape[0] == 10
                assert pose_estimation_series.confidence.shape[0] == 10


@pytest.mark.skipif(
    ndx_pose_version >= version.parse("0.2.0"), reason="SLEAPInterface requires ndx-pose version < 0.2.0"
)
class TestSLEAPInterface(DataInterfaceTestMixin, TemporalAlignmentMixin):

    data_interface_cls = SLEAPInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "SLEAP_VIDEO_000_20190128_113421" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["SLEAP_VIDEO_000_20190128_113421"].data_interfaces
            assert "track=track_0" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces["track=track_0"].pose_estimation_series
            expected_pose_estimation_series = [
                "abdomen",
                "eyeL",
                "eyeR",
                "forelegL4",
                "forelegR4",
                "head",
                "hindlegL4",
                "hindlegR4",
                "midlegL4",
                "midlegR4",
                "thorax",
                "wingL",
                "wingR",
            ]

            assert set(pose_estimation_series_in_nwb) == set(expected_pose_estimation_series)


@pytest.mark.skipif(
    ndx_pose_version >= version.parse("0.2.0"), reason="SLEAPInterface requires ndx-pose version < 0.2.0"
)
class CustomTestSLEAPInterface(TestCase):
    savedir = OUTPUT_PATH

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
                ),
            )
        ]
    )
    def test_sleap_to_nwb_interface(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            processing_module_name = "SLEAP_VIDEO_000_20190128_113421"
            assert processing_module_name in nwbfile.processing

            # For this case we have as many containers as tracks
            # Each track usually represents a subject
            processing_module = nwbfile.processing[processing_module_name]
            processing_module_interfaces = processing_module.data_interfaces
            assert len(processing_module_interfaces) == len(labels.tracks)

            # Test name of PoseEstimation containers
            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

            # Test one PoseEstimation container
            container_name = f"track={track.name}"
            pose_estimation_container = processing_module_interfaces[container_name]
            # Test that the skeleton nodes are store as nodes in containers
            expected_node_names = [node.name for node in labels.skeletons[0]]
            assert expected_node_names == list(pose_estimation_container.nodes[:])

            # Test that each PoseEstimationSeries is named as a node
            for node_name in pose_estimation_container.nodes[:]:
                assert node_name in pose_estimation_container.pose_estimation_series

    @parameterized.expand(
        [
            param(
                data_interface=SLEAPInterface,
                interface_kwargs=dict(
                    file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.slp"),
                    video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
                ),
            )
        ]
    )
    def test_sleap_interface_timestamps_propagation(self, data_interface, interface_kwargs):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}.nwb")

        interface = SLEAPInterface(**interface_kwargs)
        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)

        slp_predictions_path = interface_kwargs["file_path"]
        labels = sleap_io.load_slp(slp_predictions_path)

        from neuroconv.datainterfaces.behavior.sleap.sleap_utils import (
            extract_timestamps,
        )

        expected_timestamps = set(extract_timestamps(interface_kwargs["video_file_path"]))

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            # Test matching number of processing modules
            number_of_videos = len(labels.videos)
            assert len(nwbfile.processing) == number_of_videos

            # Test processing module naming as video
            video_name = Path(labels.videos[0].filename).stem
            processing_module_name = f"SLEAP_VIDEO_000_{video_name}"

            # For this case we have as many containers as tracks
            processing_module_interfaces = nwbfile.processing[processing_module_name].data_interfaces

            extracted_container_names = processing_module_interfaces.keys()
            for track in labels.tracks:
                expected_track_name = f"track={track.name}"
                assert expected_track_name in extracted_container_names

                container_name = f"track={track.name}"
                pose_estimation_container = processing_module_interfaces[container_name]

                # Test that each PoseEstimationSeries is named as a node
                for node_name in pose_estimation_container.nodes[:]:
                    pose_estimation_series = pose_estimation_container.pose_estimation_series[node_name]
                    extracted_timestamps = pose_estimation_series.timestamps[:]

                    # Some frames do not have predictions associated with them, so we test for sub-set
                    assert set(extracted_timestamps).issubset(expected_timestamps)


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0 and not supported on macOS with Python < 3.10",
)
class TestDeepLabCutInterface(DataInterfaceTestMixin):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "config.yaml"),
        subject_name="ind1",
    )
    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        self.check_renaming_instance(nwbfile_path=self.nwbfile_path)

    def check_renaming_instance(self, nwbfile_path: str):
        custom_container_name = "TestPoseEstimation"

        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.run_conversion(
            nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata, container_name=custom_container_name
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            assert custom_container_name in nwbfile.processing["behavior"].data_interfaces

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimationDeepLabCut" in processing_module_interfaces
            assert "Skeletons" in processing_module_interfaces

            pose_estimation_container = processing_module_interfaces["PoseEstimationDeepLabCut"]
            pose_estimation_series_in_nwb = pose_estimation_container.pose_estimation_series
            expected_pose_estimation_series = ["ind1_leftear", "ind1_rightear", "ind1_snout", "ind1_tailbase"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)

            skeleton = pose_estimation_container.skeleton
            assert skeleton.nodes[:].tolist() == ["snout", "leftear", "rightear", "tailbase"]


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0 and not supported on macOS with Python < 3.10",
)
class TestDeepLabCutInterfaceNoConfigFile(DataInterfaceTestMixin):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
        config_file_path=None,
        subject_name="ind1",
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimationDeepLabCut" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces[
                "PoseEstimationDeepLabCut"
            ].pose_estimation_series
            expected_pose_estimation_series = ["ind1_leftear", "ind1_rightear", "ind1_snout", "ind1_tailbase"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0 and not supported on macOS with Python < 3.10",
)
class TestDeepLabCutInterfaceSetTimestamps(DataInterfaceTestMixin):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "config.yaml"),
        subject_name="ind1",
    )

    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        self.check_custom_timestamps(nwbfile_path=self.nwbfile_path)

    def check_custom_timestamps(self, nwbfile_path: str):
        custom_timestamps = np.concatenate(
            (np.linspace(10, 110, 1000), np.linspace(150, 250, 1000), np.linspace(300, 400, 330))
        )

        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.set_aligned_timestamps(custom_timestamps)
        assert len(self.interface._timestamps) == 2330

        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimationDeepLabCut" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces[
                "PoseEstimationDeepLabCut"
            ].pose_estimation_series

            for pose_estimation in pose_estimation_series_in_nwb.values():
                pose_timestamps = pose_estimation.timestamps
                np.testing.assert_array_equal(pose_timestamps, custom_timestamps)

    # This was tested in the other test
    def check_read_nwb(self, nwbfile_path: str):
        pass


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0 and not supported on macOS with Python < 3.10",
)
class TestDeepLabCutInterfaceFromCSV(DataInterfaceTestMixin):
    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "SL18_csv"
            / "SL18_D19_S01_F01_BOX_SLP_20230503_112642.1DLC_resnet50_SubLearnSleepBoxRedLightJun26shuffle1_100000_stubbed.csv"
        ),
        config_file_path=None,
        subject_name="SL18",
    )
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
            assert "PoseEstimationDeepLabCut" in processing_module_interfaces

            pose_estimation_series_in_nwb = processing_module_interfaces[
                "PoseEstimationDeepLabCut"
            ].pose_estimation_series
            expected_pose_estimation_series = ["SL18_redled", "SL18_shoulder", "SL18_haunch", "SL18_baseoftail"]

            expected_pose_estimation_series_are_in_nwb_file = [
                pose_estimation in pose_estimation_series_in_nwb for pose_estimation in expected_pose_estimation_series
            ]

            assert all(expected_pose_estimation_series_are_in_nwb_file)


@pytest.fixture
def clean_pose_extension_import():
    modules_to_remove = [m for m in sys.modules if m.startswith("ndx_pose")]
    for module in modules_to_remove:
        del sys.modules[module]


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0 and not supported on macOS with Python < 3.10",
)
def test_deep_lab_cut_import_pose_extension_bug(clean_pose_extension_import, tmp_path):
    """
    Test that the DeepLabCutInterface writes correctly without importing the ndx-pose extension.
    See issues:
    https://github.com/catalystneuro/neuroconv/issues/1114
    https://github.com/rly/ndx-pose/issues/36

    """

    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
        config_file_path=str(BEHAVIOR_DATA_PATH / "DLC" / "open_field_without_video" / "config.yaml"),
    )

    interface = DeepLabCutInterface(**interface_kwargs)
    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)

    nwbfile_path = tmp_path / "test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        read_nwbfile = io.read()
        pose_estimation_container = read_nwbfile.processing["behavior"]["PoseEstimationDeepLabCut"]

        assert len(pose_estimation_container.fields) > 0
