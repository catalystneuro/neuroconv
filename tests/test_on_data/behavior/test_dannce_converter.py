import shutil
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version as importlib_version
from pathlib import Path
from warnings import warn

import pytest
from hdmf.testing import TestCase
from packaging import version
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject
from pynwb.image import ImageSeries

from neuroconv.converters import DANNCEConverter
from neuroconv.datainterfaces import DANNCEInterface
from neuroconv.tools import get_module
from neuroconv.utils import dict_deep_update

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH

ndx_pose_version = version.parse(importlib_version("ndx-pose"))

pytestmark = pytest.mark.skipif(
    ndx_pose_version < version.parse("0.4.0"),
    reason="DANNCEInterface requires ndx-pose version >= 0.4.0",
)

DANNCE_DATA_PATH = BEHAVIOR_DATA_PATH / "dannce"
SDANNCE_DATA_PATH = BEHAVIOR_DATA_PATH / "sdannce"


class TestDANNCEConverterSingleSubject(TestCase):
    """Full happy-path coverage: 'sdannce/single_subject' has six campy-recorded cameras (video +
    frametimes.npy + metadata.csv), 'hires_camN_params.mat' calibration, and a single-subject (no
    animal axis) prediction file -- the direct replacement for this file's previous 2-camera,
    flat-layout coverage."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]
    expected_serial_numbers = {"Camera1": "40054255", "Camera2": "40068500"}

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "single_subject"

        cls.converter = DANNCEConverter(
            file_paths=str(run_path / "SDANNCE" / "bsl0.5_FM" / "save_data_AVG0.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=str(run_path / "calibration"),
            metadata_key="PoseEstimationDANNCE",
        )
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_expected_metadata(self):
        metadata = self.converter.get_metadata()

        for camera_name in self.camera_names:
            assert camera_name in metadata["Devices"]

        videos_metadata = metadata["Behavior"]["ExternalVideos"]
        assert set(videos_metadata.keys()) == {f"video_{camera_name}" for camera_name in self.camera_names}

        container = metadata["Pose"]["MultiCameraPoseEstimations"]["PoseEstimationDANNCE"]
        pose_estimations = metadata["Pose"]["PoseEstimations"]
        camera_names_by_pose_estimation_metadata_key = [
            pose_estimations[key]["device_metadata_key"] for key in container["pose_estimation_metadata_keys"]
        ]
        assert camera_names_by_pose_estimation_metadata_key == self.camera_names

    def test_camera_capture_metadata_from_metadata_csv(self):
        """Each camera's real 'metadata.csv' (campy-style) should enrich its Device with serial_number
        and a shared DeviceModel (make/model), and its video description with the nominal frame rate."""
        metadata = self.converter.get_metadata()

        device_model_metadata_key = "CameraModel_a2A1920-160ucBAS"
        assert metadata["DeviceModels"][device_model_metadata_key] == dict(
            name="a2A1920-160ucBAS",
            manufacturer="Basler",
        )

        for camera_name, serial_number in self.expected_serial_numbers.items():
            device_metadata = metadata["Devices"][camera_name]
            assert device_metadata["serial_number"] == serial_number
            assert device_metadata["device_model_metadata_key"] == device_model_metadata_key

            video_description = metadata["Behavior"]["ExternalVideos"][f"video_{camera_name}"]["description"]
            assert "50 fps" in video_description

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter_single_subject.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="rat1", species="Rattus norvegicus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, stub_test=True)

        self._assert_nwbfile_structure(nwbfile_path=nwbfile_path)

    def _assert_nwbfile_structure(self, nwbfile_path: str):
        from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            for camera_name in self.camera_names:
                video_name = f"Video{camera_name}"
                assert video_name in nwbfile.acquisition
                assert isinstance(nwbfile.acquisition[video_name], ImageSeries)

            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            assert len(pe.pose_estimations) == len(self.camera_names)

            # Exactly one Device per camera -- the video's ImageSeries and DANNCE's per-camera
            # PoseEstimation child must share the same calibrated Device, not each create their own.
            assert set(nwbfile.devices.keys()) == set(self.camera_names)

            for camera_name in self.camera_names:
                device = nwbfile.devices[camera_name]
                assert isinstance(device, CalibratedCamera)

                video = nwbfile.acquisition[f"Video{camera_name}"]
                assert video.device is device

                camera_pose_estimation = pe.pose_estimations[f"{camera_name}PoseEstimation"]
                assert camera_pose_estimation.device is device
                assert camera_pose_estimation.source_video is video

            for pose_estimation_series in pe.pose_estimation_series.values():
                assert pose_estimation_series.data.shape[0] == 50  # full session, shorter than the stub limit


class TestDANNCEConverterClassicDannceNoFrametimes(TestCase):
    """'dannce/chunked_videos' is a classic (non-campy) DANNCE layout: 'kyle_camN_params.mat'
    calibration (exercises the generalized calibration filename pattern) and camera video folders
    with no 'frametimes.npy'/'metadata.csv' at all (exercises the 'sampling_rate' fallback)."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = DANNCE_DATA_PATH / "chunked_videos"

        cls.converter = DANNCEConverter(
            file_paths=str(run_path / "DANNCE" / "predict_results" / "save_data_AVG.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=str(run_path / "calibration"),
            sampling_rate=100.0,
            metadata_key="PoseEstimationDANNCE",
        )
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_expected_metadata(self):
        metadata = self.converter.get_metadata()
        for camera_name in self.camera_names:
            assert metadata["Devices"][camera_name]["type"] == "CalibratedCamera"

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter_chunked_videos.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="mouse1", species="Mus musculus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            for camera_name in self.camera_names:
                assert f"Video{camera_name}" in nwbfile.acquisition
                assert isinstance(nwbfile.devices[camera_name], CalibratedCamera)

            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            for series in pe.pose_estimation_series.values():
                assert series.data.shape[0] == 2  # this stub prediction file covers 2 frames


class TestDANNCEConverterPredictionsSplitAcrossJobs(TestCase):
    """'sdannce/predictions_split_across_jobs' partitions one subject's 50-frame session between two
    files in the same run folder (frames 0-24 and 25-49) -- exercises 'file_paths' concatenation."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "predictions_split_across_jobs"
        predict_path = run_path / "SDANNCE" / "predict00"

        cls.converter = DANNCEConverter(
            file_paths=[str(predict_path / "save_data_AVG0.mat"), str(predict_path / "save_data_AVG25.mat")],
            videos_folder_path=str(run_path / "videos"),
            calibration_path=str(run_path / "calibration"),
            animal_index=0,
            metadata_key="PoseEstimationDANNCE",
        )
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_concatenated_into_one_continuous_session(self):
        assert self.converter._dannce_interface._pred.shape[0] == 50
        sample_id = self.converter._dannce_interface._sample_id
        assert sample_id[0] == 0
        assert sample_id[-1] == 49

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter_split_jobs.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="rat1", species="Rattus norvegicus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        from ndx_pose import MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            # One continuous 50-frame pose estimation, not two 25-frame fragments.
            for series in pe.pose_estimation_series.values():
                assert series.data.shape[0] == 50


class TestDANNCEConverterMultipleSubjectsSharedDevices(TestCase):
    """'sdannce/multiple_subjects_per_file/two_subjects' stores both rats' predictions in one file
    along a subject axis -- verifies the documented workflow of one DANNCEConverter (writing the
    shared videos) plus one bare DANNCEInterface per additional animal, sharing camera Devices."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "multiple_subjects_per_file" / "two_subjects"
        file_path = str(run_path / "SDANNCE" / "predict00" / "save_data_AVG0.mat")
        calibration_path = str(run_path / "calibration")

        cls.converter_rat1 = DANNCEConverter(
            file_paths=file_path,
            videos_folder_path=str(run_path / "videos"),
            calibration_path=calibration_path,
            animal_index=0,
            subject_name="rat1",
            metadata_key="PoseEstimationRat1",
        )
        cls.interface_rat2 = DANNCEInterface(
            file_paths=file_path,
            calibration_path=calibration_path,
            animal_index=1,
            subject_name="rat2",
            metadata_key="PoseEstimationRat2",
            camera_names=cls.converter_rat1._camera_names,
        )
        cls.interface_rat2.set_aligned_timestamps(cls.converter_rat1._dannce_interface.get_timestamps())
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_shares_camera_devices(self):
        metadata = self.converter_rat1.get_metadata()
        metadata = dict_deep_update(metadata, self.interface_rat2.get_metadata())
        metadata["NWBFile"] = dict(
            session_description="test",
            identifier="test_dannce_multi_subject",
            session_start_time=datetime.now(timezone.utc),
        )

        nwbfile = NWBFile(**metadata["NWBFile"])
        nwbfile.subject = Subject(subject_id="rat1_rat2_session", species="Rattus norvegicus", sex="U")

        self.converter_rat1.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self.interface_rat2.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = str(self.test_dir / "test_dannce_converter_multi_subject.nwb")
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, "r", load_namespaces=True) as io:
            nwbfile_read = io.read()
            assert set(nwbfile_read.devices.keys()) == set(self.camera_names)

            behavior = get_module(nwbfile=nwbfile_read, name="behavior")
            assert "PoseEstimationRat1" in behavior.data_interfaces
            assert "PoseEstimationRat2" in behavior.data_interfaces


class TestDANNCEInterfaceAvgAndMaxPredictions(TestCase):
    """'dannce/avg_and_max_predictions' has no videos -- covers the bare DANNCEInterface with
    'kyle_camN_params.mat' calibration only, for both AVG (world coordinates) and MAX (COM-relative)
    prediction variants."""

    run_path = DANNCE_DATA_PATH / "avg_and_max_predictions"

    def test_avg_predictions_load_and_write(self):
        interface = DANNCEInterface(
            file_paths=str(self.run_path / "DANNCE" / "predict_results" / "save_data_AVG.mat"),
            calibration_path=str(self.run_path / "calibration"),
            sampling_rate=100.0,
        )
        assert interface._pred.shape == (100, 3, 22)
        assert interface._camera_names == [f"Camera{i}" for i in range(1, 7)]

        from pynwb.testing.mock.file import mock_NWBFile

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        behavior = get_module(nwbfile=nwbfile, name="behavior")
        assert "PoseEstimationDANNCE" in behavior.data_interfaces

    def test_max_predictions_load_and_write(self):
        interface = DANNCEInterface(
            file_paths=str(self.run_path / "DANNCE" / "predict_results" / "save_data_MAX.mat"),
            calibration_path=str(self.run_path / "calibration"),
            sampling_rate=100.0,
        )
        assert interface._pred.shape == (100, 3, 22)

        from pynwb.testing.mock.file import mock_NWBFile

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        behavior = get_module(nwbfile=nwbfile, name="behavior")
        assert "PoseEstimationDANNCE" in behavior.data_interfaces


class TestDANNCEInterfacePreLabel3dLayout(TestCase):
    """'dannce/pre_label3d_layout' predates Label3D bundling synchronization/labels into one file
    (irrelevant to this interface, which never reads sync/labeling files) -- covers the bare
    DANNCEInterface against its prediction + 'kyle_camN_params.mat' calibration only."""

    def test_load_and_write(self):
        run_path = DANNCE_DATA_PATH / "pre_label3d_layout"
        interface = DANNCEInterface(
            file_paths=str(run_path / "DANNCE" / "predict_results" / "save_data_AVG.mat"),
            calibration_path=str(run_path / "calibration"),
            sampling_rate=100.0,
        )
        assert interface._pred.shape == (100, 3, 22)
        assert interface._camera_names == [f"Camera{i}" for i in range(1, 7)]

        from pynwb.testing.mock.file import mock_NWBFile

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        behavior = get_module(nwbfile=nwbfile, name="behavior")
        assert "PoseEstimationDANNCE" in behavior.data_interfaces


class TestDANNCEInterfaceAvgAndMaxWithRunMetadata(TestCase):
    """'dannce/avg_and_max_with_run_metadata' predictions carry an extra top-level 'metadata' key
    (run configuration: 'expval', 'predict_mode', 'camnames', ...) that this interface does not use --
    covers that loading tolerates its presence, for both AVG and MAX (which also adds 'log_pmax')."""

    run_path = DANNCE_DATA_PATH / "avg_and_max_with_run_metadata"

    def test_avg_with_run_metadata_loads(self):
        interface = DANNCEInterface(file_paths=str(self.run_path / "save_data_AVG.mat"), sampling_rate=1.0)
        assert interface._pred.shape == (8, 3, 22)

    def test_max_with_run_metadata_loads(self):
        interface = DANNCEInterface(file_paths=str(self.run_path / "save_data_MAX.mat"), sampling_rate=1.0)
        assert interface._pred.shape == (8, 3, 22)


class TestDANNCEInterfaceTwentyKeypoints(TestCase):
    """'dannce/twenty_keypoints' has 20 landmarks (rather than the 22-23 seen elsewhere) -- covers
    that landmark count is derived from the data rather than assumed fixed."""

    def test_load_and_write(self):
        run_path = DANNCE_DATA_PATH / "twenty_keypoints"
        interface = DANNCEInterface(file_paths=str(run_path / "save_data_AVG.mat"), sampling_rate=1.0)
        assert interface._pred.shape == (40, 3, 20)
        assert len(interface._landmark_names) == 20

        from pynwb.testing.mock.file import mock_NWBFile

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        pe = nwbfile.processing["behavior"]["PoseEstimationDANNCE"]
        assert len(pe.pose_estimation_series) == 20


class TestDANNCEConverterOneFilePerSubject(TestCase):
    """'sdannce/one_file_per_subject/two_subjects' stores each rat's predictions in its own file
    (no subject axis), sharing one 'videos_folder_path' -- verifies the shared-camera-devices
    workflow for the file-per-subject variant of multi-animal data (as opposed to the
    subject-axis-in-one-file variant covered by 'TestDANNCEConverterMultipleSubjectsSharedDevices')."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "one_file_per_subject" / "two_subjects"
        calibration_path = str(run_path / "calibration")

        cls.converter_rat1 = DANNCEConverter(
            file_paths=str(run_path / "SDANNCE" / "bsl0.5_FM_rat1" / "save_data_AVG0.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=calibration_path,
            subject_name="rat1",
            metadata_key="PoseEstimationRat1",
        )
        cls.interface_rat2 = DANNCEInterface(
            file_paths=str(run_path / "SDANNCE" / "bsl0.5_FM_rat2" / "save_data_AVG0.mat"),
            calibration_path=calibration_path,
            subject_name="rat2",
            metadata_key="PoseEstimationRat2",
            camera_names=cls.converter_rat1._camera_names,
        )
        cls.interface_rat2.set_aligned_timestamps(cls.converter_rat1._dannce_interface.get_timestamps())
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_shares_camera_devices(self):
        metadata = self.converter_rat1.get_metadata()
        metadata = dict_deep_update(metadata, self.interface_rat2.get_metadata())
        metadata["NWBFile"] = dict(
            session_description="test",
            identifier="test_dannce_one_file_per_subject",
            session_start_time=datetime.now(timezone.utc),
        )

        nwbfile = NWBFile(**metadata["NWBFile"])
        nwbfile.subject = Subject(subject_id="rat1_rat2_session", species="Rattus norvegicus", sex="U")

        self.converter_rat1.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self.interface_rat2.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = str(self.test_dir / "test_dannce_converter_one_file_per_subject.nwb")
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, "r", load_namespaces=True) as io:
            nwbfile_read = io.read()
            assert set(nwbfile_read.devices.keys()) == set(self.camera_names)

            behavior = get_module(nwbfile=nwbfile_read, name="behavior")
            assert "PoseEstimationRat1" in behavior.data_interfaces
            assert "PoseEstimationRat2" in behavior.data_interfaces


class TestDANNCEConverterThreeSubjectsSharedDevices(TestCase):
    """'sdannce/multiple_subjects_per_file/three_subjects' extends the two-subject, subject-axis
    case to three animals in one prediction file, sharing camera Devices across all three."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "multiple_subjects_per_file" / "three_subjects"
        file_path = str(run_path / "SDANNCE" / "predict00" / "save_data_AVG0.mat")
        calibration_path = str(run_path / "calibration")

        cls.converter_animal0 = DANNCEConverter(
            file_paths=file_path,
            videos_folder_path=str(run_path / "videos"),
            calibration_path=calibration_path,
            animal_index=0,
            subject_name="animal1",
            metadata_key="PoseEstimationAnimal1",
        )
        cls.interfaces = []
        for animal_index, subject_name in ((1, "animal2"), (2, "animal3")):
            interface = DANNCEInterface(
                file_paths=file_path,
                calibration_path=calibration_path,
                animal_index=animal_index,
                subject_name=subject_name,
                metadata_key=f"PoseEstimation{subject_name.capitalize()}",
                camera_names=cls.converter_animal0._camera_names,
            )
            interface.set_aligned_timestamps(cls.converter_animal0._dannce_interface.get_timestamps())
            cls.interfaces.append(interface)
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_shares_camera_devices(self):
        metadata = self.converter_animal0.get_metadata()
        for interface in self.interfaces:
            metadata = dict_deep_update(metadata, interface.get_metadata())
        metadata["NWBFile"] = dict(
            session_description="test",
            identifier="test_dannce_three_subjects",
            session_start_time=datetime.now(timezone.utc),
        )

        nwbfile = NWBFile(**metadata["NWBFile"])
        nwbfile.subject = Subject(subject_id="three_animal_session", species="Rattus norvegicus", sex="U")

        self.converter_animal0.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        for interface in self.interfaces:
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = str(self.test_dir / "test_dannce_converter_three_subjects.nwb")
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, "r", load_namespaces=True) as io:
            nwbfile_read = io.read()
            assert set(nwbfile_read.devices.keys()) == set(self.camera_names)

            behavior = get_module(nwbfile=nwbfile_read, name="behavior")
            assert "PoseEstimationAnimal1" in behavior.data_interfaces
            assert "PoseEstimationAnimal2" in behavior.data_interfaces
            assert "PoseEstimationAnimal3" in behavior.data_interfaces


class TestDANNCEConverterSyncLongerThanVideo(TestCase):
    """'sdannce/sync_longer_than_video' has a Label3D synchronization table longer than the actual
    video/predictions (irrelevant here -- this interface never reads sync tables). Its prediction
    file has a singleton animal axis with no explicit 'animal_index' passed, exercising the
    auto-default-to-0 behavior end-to-end on real data."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "sync_longer_than_video"

        cls.converter = DANNCEConverter(
            file_paths=str(run_path / "SDANNCE" / "predict00" / "save_data_AVG0.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=str(run_path / "calibration"),
            metadata_key="PoseEstimationDANNCE",
        )
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_animal_index_auto_defaulted(self):
        assert self.converter._dannce_interface._animal_index == 0

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter_sync_longer_than_video.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="rat1", species="Rattus norvegicus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        from ndx_pose import MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)


class TestDANNCEConverterTwoRunsForOneSubject(TestCase):
    """'sdannce/two_runs_for_one_subject' has two alternative pose-estimation runs (DANNCE and
    sDANNCE) of the same subject and videos -- verifies both can be written to one NWBFile, sharing
    camera Devices, distinguished only by 'metadata_key'."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "two_runs_for_one_subject"
        calibration_path = str(run_path / "calibration")

        cls.converter_dannce_run = DANNCEConverter(
            file_paths=str(run_path / "DANNCE" / "predict00" / "save_data_AVG0.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=calibration_path,
            metadata_key="PoseEstimationDANNCERun",
        )
        cls.interface_sdannce_run = DANNCEInterface(
            file_paths=str(run_path / "SDANNCE" / "predict00" / "save_data_AVG0.mat"),
            calibration_path=calibration_path,
            metadata_key="PoseEstimationSDANNCERun",
            camera_names=cls.converter_dannce_run._camera_names,
        )
        cls.interface_sdannce_run.set_aligned_timestamps(cls.converter_dannce_run._dannce_interface.get_timestamps())
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion_shares_camera_devices(self):
        metadata = self.converter_dannce_run.get_metadata()
        metadata = dict_deep_update(metadata, self.interface_sdannce_run.get_metadata())
        metadata["NWBFile"] = dict(
            session_description="test",
            identifier="test_dannce_two_runs",
            session_start_time=datetime.now(timezone.utc),
        )

        nwbfile = NWBFile(**metadata["NWBFile"])
        nwbfile.subject = Subject(subject_id="rat1", species="Rattus norvegicus", sex="U")

        self.converter_dannce_run.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        self.interface_sdannce_run.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        nwbfile_path = str(self.test_dir / "test_dannce_converter_two_runs.nwb")
        with NWBHDF5IO(nwbfile_path, "w") as io:
            io.write(nwbfile)

        with NWBHDF5IO(nwbfile_path, "r", load_namespaces=True) as io:
            nwbfile_read = io.read()
            assert set(nwbfile_read.devices.keys()) == set(self.camera_names)

            behavior = get_module(nwbfile=nwbfile_read, name="behavior")
            assert "PoseEstimationDANNCERun" in behavior.data_interfaces
            assert "PoseEstimationSDANNCERun" in behavior.data_interfaces


class TestDANNCEConverterSdannceChunkedVideosWithFrametimes(TestCase):
    """'sdannce/chunked_videos' pairs multi-segment videos (two chunks per camera) with real
    'frametimes.npy' files -- unlike 'dannce/chunked_videos' (no frametimes at all), this exercises
    the original per-segment timestamp-splitting path (frametimes present) rather than the
    'sampling_rate' fallback."""

    camera_names = [f"Camera{i}" for i in range(1, 7)]

    @classmethod
    def setUpClass(cls) -> None:
        run_path = SDANNCE_DATA_PATH / "chunked_videos"

        cls.converter = DANNCEConverter(
            file_paths=str(run_path / "SDANNCE" / "predict00" / "save_data_AVG0.mat"),
            videos_folder_path=str(run_path / "videos"),
            calibration_path=str(run_path / "calibration"),
            metadata_key="PoseEstimationDANNCE",
        )
        cls.test_dir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            shutil.rmtree(cls.test_dir)
        except PermissionError:
            warn(f"Unable to cleanup testing data at {cls.test_dir}! Please remove it manually.")

    def test_run_conversion(self):
        nwbfile_path = str(self.test_dir / "test_dannce_converter_sdannce_chunked_videos.nwb")
        metadata = self.converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime.now(timezone.utc)
        metadata["Subject"] = dict(subject_id="rat1", species="Rattus norvegicus", sex="U")
        self.converter.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata)

        from ndx_pose import MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            for camera_name in self.camera_names:
                assert f"Video{camera_name}" in nwbfile.acquisition

            behavior = get_module(nwbfile=nwbfile, name="behavior")
            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            for series in pe.pose_estimation_series.values():
                assert series.data.shape[0] == 50
