import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from hdmf.testing import TestCase
from natsort import natsorted
from ndx_miniscope import Miniscope
from ndx_miniscope.utils import get_timestamps
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from pynwb.behavior import Position, SpatialSeries

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    FicTracDataInterface,
    MedPCInterface,
    MiniscopeBehaviorInterface,
    NeuralynxNvtInterface,
    VideoInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    MedPCInterfaceMixin,
    TemporalAlignmentMixin,
    VideoInterfaceMixin,
)

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OPHYS_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH


class TestFicTracDataInterface(DataInterfaceTestMixin):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"),
        configuration_file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "config.txt"),
    )

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        expected_session_start_time = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)
        assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        configuration_metadata = (
            '{"version": "v2.1.1", '
            '"build_date": "Jul 24 2023", '
            '"c2a_cnrs_xy": [191, 171, 128, 272, 20, 212, 99, 132], '
            '"c2a_r": [0.722445, -0.131314, -0.460878], '
            '"c2a_src": "c2a_cnrs_xy", '
            '"c2a_t": [-0.674396, 0.389373, 2.889648], '
            '"do_display": true, '
            '"max_bad_frames": -1, '
            '"opt_bound": 0.35, '
            '"opt_do_global": false, '
            '"opt_max_err": -1.0, '
            '"opt_max_evals": 50, '
            '"opt_tol": 0.001, '
            '"q_factor": 6, '
            '"roi_c": [-0.22939, 0.099969, 0.968187], '
            '"roi_circ": [63, 171, 81, 145, 106, 135, 150, 160], '
            '"roi_ignr": [[96, 156, 113, 147, 106, 128, 82, 130, 81, 150], '
            "[71, 213, 90, 219, 114, 218, 135, 211, 154, 196, 150, 217, 121, 228, 99, 234, 75, 225]], "
            '"roi_r": 0.124815, '
            '"save_debug": false, '
            '"save_raw": false, '
            '"src_fn": "sample.mp4", '
            '"src_fps": -1.0, '
            '"thr_ratio": 1.25, '
            '"thr_win_pc": 0.25, '
            '"vfov": 45.0}'
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            fictrac_position_container = nwbfile.processing["behavior"].data_interfaces["FicTrac"]
            assert isinstance(fictrac_position_container, Position)

            assert len(fictrac_position_container.spatial_series) == 10

            column_to_nwb_mapping = self.interface.column_to_nwb_mapping
            for data_dict in column_to_nwb_mapping.values():
                spatial_series_name = data_dict["spatial_series_name"]
                assert spatial_series_name in fictrac_position_container.spatial_series

                reference_frame = data_dict["reference_frame"]
                spatial_series = fictrac_position_container.spatial_series[spatial_series_name]
                assert reference_frame == spatial_series.reference_frame

                expected_units = "radians"
                assert spatial_series.unit == expected_units
                assert spatial_series.conversion == 1.0

                expected_metadata = f"{configuration_metadata}"
                assert spatial_series.comments == expected_metadata

                assert spatial_series.timestamps[0] == 0.0


class TestFicTracDataInterfaceWithRadius(DataInterfaceTestMixin):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"), radius=1.0
    )

    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        expected_session_start_time = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)
        assert metadata["NWBFile"]["session_start_time"] == expected_session_start_time

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        configuration_metadata = (
            '{"version": "v2.1.1", '
            '"build_date": "Jul 24 2023", '
            '"c2a_cnrs_xy": [191, 171, 128, 272, 20, 212, 99, 132], '
            '"c2a_r": [0.722445, -0.131314, -0.460878], '
            '"c2a_src": "c2a_cnrs_xy", '
            '"c2a_t": [-0.674396, 0.389373, 2.889648], '
            '"do_display": true, '
            '"max_bad_frames": -1, '
            '"opt_bound": 0.35, '
            '"opt_do_global": false, '
            '"opt_max_err": -1.0, '
            '"opt_max_evals": 50, '
            '"opt_tol": 0.001, '
            '"q_factor": 6, '
            '"roi_c": [-0.22939, 0.099969, 0.968187], '
            '"roi_circ": [63, 171, 81, 145, 106, 135, 150, 160], '
            '"roi_ignr": [[96, 156, 113, 147, 106, 128, 82, 130, 81, 150], '
            "[71, 213, 90, 219, 114, 218, 135, 211, 154, 196, 150, 217, 121, 228, 99, 234, 75, 225]], "
            '"roi_r": 0.124815, '
            '"save_debug": false, '
            '"save_raw": false, '
            '"src_fn": "sample.mp4", '
            '"src_fps": -1.0, '
            '"thr_ratio": 1.25, '
            '"thr_win_pc": 0.25, '
            '"vfov": 45.0}'
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()

            fictrac_position_container = nwbfile.processing["behavior"].data_interfaces["FicTrac"]
            assert isinstance(fictrac_position_container, Position)

            assert len(fictrac_position_container.spatial_series) == 10

            column_to_nwb_mapping = self.interface.column_to_nwb_mapping
            for data_dict in column_to_nwb_mapping.values():
                spatial_series_name = data_dict["spatial_series_name"]
                assert spatial_series_name in fictrac_position_container.spatial_series

                reference_frame = data_dict["reference_frame"]
                spatial_series = fictrac_position_container.spatial_series[spatial_series_name]
                assert reference_frame == spatial_series.reference_frame
                expected_units = "meters"
                assert spatial_series.unit == expected_units
                assert spatial_series.conversion == self.interface.radius

                expected_metadata = f"{configuration_metadata}"
                assert spatial_series.comments == expected_metadata

                assert spatial_series.timestamps[0] == 0.0


class TestFicTracDataInterfaceTiming(TemporalAlignmentMixin):
    data_interface_cls = FicTracDataInterface
    interface_kwargs = dict(file_path=str(BEHAVIOR_DATA_PATH / "FicTrac" / "sample" / "sample-20230724_113055.dat"))

    save_directory = OUTPUT_PATH


class TestMiniscopeInterface(DataInterfaceTestMixin):
    data_interface_cls = MiniscopeBehaviorInterface
    interface_kwargs = dict(folder_path=str(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5"))
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    def setup_metadata(self, request):
        cls = request.cls
        folder_path = Path(OPHYS_DATA_PATH / "imaging_datasets" / "Miniscope" / "C6-J588_Disc5")
        cls.device_name = "BehavCam2"
        cls.image_series_name = "BehavCamImageSeries"

        cls.device_metadata = dict(
            name=cls.device_name,
            compression="MJPG",
            deviceType="WebCam-1920x1080",
            framesPerFile=1000,
            ROI={"height": 720, "leftEdge": 0, "topEdge": 0, "width": 1280},
        )
        cls.starting_frames = np.array([0, 5, 10])  # there are 5 frames in each of the three avi files
        cls.external_files = [str(file) for file in list(natsorted(folder_path.glob("*/BehavCam*/0.avi")))]
        cls.timestamps = get_timestamps(folder_path=str(folder_path), file_pattern="BehavCam*/timeStamps.csv")

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 10, 7, 15, 3, 28, 635)
        assert metadata["Behavior"]["Device"][0] == self.device_metadata

        image_series_metadata = metadata["Behavior"]["ImageSeries"][0]
        assert image_series_metadata["name"] == self.image_series_name
        assert image_series_metadata["device"] == self.device_name
        assert image_series_metadata["unit"] == "px"
        assert image_series_metadata["dimension"] == [1280, 720]  # width x height

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()

            # Check device metadata
            assert self.device_name in nwbfile.devices
            device = nwbfile.devices[self.device_name]
            assert isinstance(device, Miniscope)
            assert device.compression == self.device_metadata["compression"]
            assert device.deviceType == self.device_metadata["deviceType"]
            assert device.framesPerFile == self.device_metadata["framesPerFile"]
            roi = [self.device_metadata["ROI"]["height"], self.device_metadata["ROI"]["width"]]
            assert_array_equal(device.ROI[:], roi)

            # Check ImageSeries
            assert self.image_series_name in nwbfile.acquisition
            image_series = nwbfile.acquisition[self.image_series_name]
            assert image_series.format == "external"
            assert_array_equal(image_series.starting_frame, self.starting_frames)
            assert_array_equal(image_series.dimension[:], [1280, 720])
            assert image_series.unit == "px"
            assert device == nwbfile.acquisition[self.image_series_name].device
            assert_array_equal(image_series.timestamps[:], self.timestamps)
            assert_array_equal(image_series.external_file[:], self.external_files)


class TestNeuralynxNvtInterface(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls = NeuralynxNvtInterface
    interface_kwargs = dict(file_path=str(BEHAVIOR_DATA_PATH / "neuralynx" / "test.nvt"))
    conversion_options = dict(add_angle=True)
    save_directory = OUTPUT_PATH

    def check_read_nwb(self, nwbfile_path: str):  # This is currently structured to be file-specific
        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert isinstance(nwbfile.acquisition["NvtPosition"].spatial_series["NvtSpatialSeries"], SpatialSeries)
            assert isinstance(
                nwbfile.acquisition["NvtCompassDirection"].spatial_series["NvtAngleSpatialSeries"], SpatialSeries
            )

    def check_metadata(self):
        super().check_metadata()
        metadata = self.interface.get_metadata()
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 5, 15, 10, 35, 29)


class TestVideoInterface(VideoInterfaceMixin):
    data_interface_cls = VideoInterface
    save_directory = OUTPUT_PATH

    @pytest.fixture(
        params=[
            (dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_avi.avi")])),
            (dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_flv.flv")])),
            (dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mov.mov")])),
            (dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_mp4.mp4")])),
            (dict(file_paths=[str(BEHAVIOR_DATA_PATH / "videos" / "CFR" / "video_wmv.wmv")])),
        ],
        ids=["avi", "flv", "mov", "mp4", "wmv"],
    )
    def setup_interface(self, request):

        test_id = request.node.callspec.id
        self.test_name = test_id
        self.interface_kwargs = request.param
        self.interface = self.data_interface_cls(**self.interface_kwargs)

        return self.interface, self.test_name


class TestVideoConversions(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.video_files = list((BEHAVIOR_DATA_PATH / "videos" / "CFR").iterdir())
        cls.video_files.sort()
        cls.number_of_video_files = len(cls.video_files)
        cls.aligned_segment_starting_times = [0.0, 50.0, 100.0, 150.0, 175.0]

    def _get_metadata(self):
        """TODO: temporary helper function to fetch new metadata each time; need to debug in follow-up."""
        self.metadata = self.converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        self.image_series_name = self.metadata["Behavior"]["Videos"][0]["name"]

    def test_real_videos(self):
        # TODO - merge this with the data mixin in follow-up
        for file_index, (file_path, segment_starting_time) in enumerate(
            zip(self.video_files, self.aligned_segment_starting_times)
        ):
            self.file_index = file_index

            class VideoTestNWBConverter(NWBConverter):
                data_interface_classes = dict(Video=VideoInterface)

            source_data = dict(Video=dict(file_paths=[file_path]))
            self.converter = VideoTestNWBConverter(source_data)
            self.interface = self.converter.data_interface_objects["Video"]
            self.interface.set_aligned_segment_starting_times(
                aligned_segment_starting_times=[self.aligned_segment_starting_times[self.file_index]]
            )

            self.check_video_set_aligned_starting_times()
            self.check_video_custom_module()
            self.check_video_chunking()

    def check_video_set_aligned_starting_times(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False))
        nwbfile_path = OUTPUT_PATH / "check_video_starting_times.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            self.image_series = nwbfile.acquisition[self.image_series_name]

            if self.image_series.starting_time is not None:
                assert self.aligned_segment_starting_times[self.file_index] == self.image_series.starting_time
            else:
                assert self.aligned_segment_starting_times[self.file_index] == self.image_series.timestamps[0]

    def check_video_custom_module(self):
        self._get_metadata()
        module_name = "TestModule"
        module_description = "This is a test module."
        conversion_options = dict(
            Video=dict(
                external_mode=False,
                module_name=module_name,
                module_description=module_description,
            )
        )
        nwbfile_path = OUTPUT_PATH / "test_video_custom_module.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert module_name in nwbfile.processing
            assert module_description == nwbfile.processing[module_name].description
            assert self.image_series_name in nwbfile.processing[module_name].data_interfaces

    def check_video_chunking(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True, chunk_data=False))
        nwbfile_path = OUTPUT_PATH / "check_video_chunking.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )

        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.chunks is not None

    def check_external_mode(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=True))
        nwbfile_path = OUTPUT_PATH / "check_external_mode.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].external_file[0] == str(
                self.video_files[self.file_index]
            )

    def check_video_stub(self):
        self._get_metadata()
        conversion_options = dict(Video=dict(external_mode=False, stub_test=True))
        nwbfile_path = OUTPUT_PATH / "check_video_stub.nwb"
        self.converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=self.metadata,
        )
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            assert self.image_series_name in nwbfile.acquisition
            assert nwbfile.acquisition[self.image_series_name].data.shape[0] == 10


class TestMedPCInterface(TestCase, MedPCInterfaceMixin):
    data_interface_cls = MedPCInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "medpc" / "example_medpc_file_06_06_2024.txt"),
        session_conditions={
            "Start Date": "04/10/19",
            "Start Time": "12:36:13",
        },
        start_variable="Start Date",
        metadata_medpc_name_to_info_dict={
            "Start Date": {"name": "start_date", "is_array": False},
            "Start Time": {"name": "start_time", "is_array": False},
            "Subject": {"name": "subject", "is_array": False},
            "Box": {"name": "box", "is_array": False},
            "MSN": {"name": "MSN", "is_array": False},
        },
        aligned_timestamp_names=[],
    )
    save_directory = OUTPUT_PATH
    expected_metadata = {
        "start_date": "04/10/19",
        "start_time": "12:36:13",
        "subject": "95.259",
        "box": "1",
        "MSN": "FOOD_FR1 TTL Left",
    }
    expected_events = [
        {
            "name": "left_nose_poke_times",
            "description": "Left nose poke times",
        },
        {
            "name": "right_nose_poke_times",
            "description": "Right nose poke times",
        },
        {
            "name": "left_reward_times",
            "description": "Left reward times",
        },
    ]
    expected_interval_series = [
        {
            "name": "reward_port_intervals",
            "description": "Interval of time spent in reward port (1 is entry, -1 is exit)",
            "onset_name": "port_entry_times",
            "duration_name": "duration_of_port_entry",
        },
    ]

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["MedPC"] == self.expected_metadata

    def check_read_nwb(self, nwbfile_path: str):
        with NWBHDF5IO(nwbfile_path, "r") as io:
            nwbfile = io.read()
            for event_dict in self.expected_events:
                expected_name = event_dict["name"]
                expected_description = event_dict["description"]
                assert expected_name in nwbfile.processing["behavior"].data_interfaces
                event = nwbfile.processing["behavior"].data_interfaces[expected_name]
                assert event.description == expected_description

            for interval_dict in self.expected_interval_series:
                expected_name = interval_dict["name"]
                expected_description = interval_dict["description"]
                assert expected_name in nwbfile.processing["behavior"]["behavioral_epochs"].interval_series
                interval_series = nwbfile.processing["behavior"]["behavioral_epochs"].interval_series[expected_name]
                assert interval_series.description == expected_description

    def test_all_conversion_checks(self):
        metadata = {
            "NWBFile": {"session_start_time": datetime(2019, 4, 10, 12, 36, 13).astimezone()},
            "MedPC": {
                "start_date": "04/10/19",
                "start_time": "12:36:13",
                "subject": "95.259",
                "box": "1",
                "MSN": "FOOD_FR1 TTL Left",
                "module_name": "behavior",
                "module_description": "Behavioral data from MedPC output files.",
                "medpc_name_to_info_dict": {
                    "A": {"name": "left_nose_poke_times", "is_array": True},
                    "B": {"name": "left_reward_times", "is_array": True},
                    "C": {"name": "right_nose_poke_times", "is_array": True},
                    "D": {"name": "right_reward_times", "is_array": True},
                    "E": {"name": "duration_of_port_entry", "is_array": True},
                    "G": {"name": "port_entry_times", "is_array": True},
                },
                "Events": [
                    {
                        "name": "left_nose_poke_times",
                        "description": "Left nose poke times",
                    },
                    {
                        "name": "right_nose_poke_times",
                        "description": "Right nose poke times",
                    },
                    {
                        "name": "left_reward_times",
                        "description": "Left reward times",
                    },
                ],
                "IntervalSeries": [
                    {
                        "name": "reward_port_intervals",
                        "description": "Interval of time spent in reward port (1 is entry, -1 is exit)",
                        "onset_name": "port_entry_times",
                        "duration_name": "duration_of_port_entry",
                    },
                ],
            },
        }
        super().test_all_conversion_checks(metadata=metadata)

    def test_interface_alignment(self):
        medpc_name_to_info_dict = {
            "A": {"name": "left_nose_poke_times", "is_array": True},
            "B": {"name": "left_reward_times", "is_array": True},
            "C": {"name": "right_nose_poke_times", "is_array": True},
            "D": {"name": "right_reward_times", "is_array": True},
            "E": {"name": "duration_of_port_entry", "is_array": True},
            "G": {"name": "port_entry_times", "is_array": True},
        }
        super().test_interface_alignment(medpc_name_to_info_dict=medpc_name_to_info_dict)


if __name__ == "__main__":
    unittest.main()
