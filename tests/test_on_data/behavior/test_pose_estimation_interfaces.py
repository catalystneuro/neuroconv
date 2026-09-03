import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile, mock_Subject

from neuroconv.datainterfaces import (
    DANNCEInterface,
    DeepLabCutInterface,
    LightningPoseDataInterface,
    SLEAPInterface,
)
from neuroconv.tools.testing.data_interface_mixins import (
    PoseEstimationInterfaceTestMixin,
)
from neuroconv.utils import DeepDict

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

from importlib.metadata import version as importlib_version
from platform import machine, python_version
from sys import platform

from packaging import version

python_version = version.parse(python_version())
# TODO: remove after this is merged https://github.com/talmolab/sleap-io/pull/143 and released
ndx_pose_version = version.parse(importlib_version("ndx-pose"))

# SLEAP conversion is not yet supported on macOS Intel with Python 3.13. See
# https://github.com/catalystneuro/neuroconv/actions/runs/32099304619/job/95596631882.
SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED = (
    platform == "darwin" and machine() == "x86_64" and python_version.release[:2] == (3, 13)
)


class TestLightningPoseDataInterface(PoseEstimationInterfaceTestMixin):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
        metadata_key="lightning_pose_key",
    )
    conversion_options = dict(reference_frame="(0,0) corresponds to the top left corner of the video.")
    save_directory = OUTPUT_PATH

    @pytest.fixture(scope="class", autouse=True)
    @classmethod
    def setup_metadata(cls):

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

    # TODO: remove test_metadata and check_extracted_metadata_old_format when the legacy
    # metadata["Behavior"]["PoseEstimation"] block is removed (then check_extracted_metadata is the
    # only metadata hook).
    def test_metadata(self, setup_interface):
        metadata = self.interface.get_metadata(use_new_metadata_format=False)
        self.interface.validate_metadata(metadata=metadata)
        self.check_extracted_metadata_old_format(metadata)

    def check_extracted_metadata_old_format(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 11, 9, 10, 14, 37, 0)
        assert self.pose_estimation_name in metadata["Behavior"]
        assert metadata["Behavior"][self.pose_estimation_name] == self.expected_metadata[self.pose_estimation_name]

    def test_get_metadata(self, setup_interface):
        metadata = self.interface.get_metadata(use_new_metadata_format=True)
        self.check_extracted_metadata(metadata)

    def run_custom_checks(self):
        self.check_written_values(nwbfile_path=self.nwbfile_path)

    def check_written_values(self, nwbfile_path: str):
        """What the mixin cannot know: the source's own samples, its video dimensions, and the reference
        frame the deprecated conversion option routes into every series."""
        nwbfile = read_nwb(nwbfile_path)
        pose_estimation_container = nwbfile.processing["behavior"].data_interfaces[self.pose_estimation_name]

        assert_array_equal(
            pose_estimation_container.dimensions[:],
            [[self.original_video_height, self.original_video_width]],
        )

        for keypoint_name in self.expected_keypoint_names:
            pose_estimation_series = pose_estimation_container.pose_estimation_series[
                f"PoseEstimationSeries{keypoint_name}"
            ]
            assert pose_estimation_series.reference_frame == self.conversion_options["reference_frame"]
            assert_array_equal(pose_estimation_series.data[:], self.test_data[keypoint_name][["x", "y"]].values)
        nwbfile.read_io.close()

    def check_extracted_metadata(self, metadata: dict):
        """The dict-based metadata shape, checked against a full expected dict.

        The equality is strict: provenance-first means ``get_metadata`` emits only source-derived
        values and object names (no ``description``/``unit`` defaults, those are applied by the
        writer), so any extra emitted field would fail the comparison. ``reference_frame`` is
        source-derived here: image coordinates are a property of the tracker's output rather than a
        stand-in for something the file failed to record.
        """
        metadata_key = "lightning_pose_key"

        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 11, 9, 10, 14, 37, 0)
        # The legacy metadata["Behavior"]["PoseEstimation"] block must be gone in the dict-based shape.
        assert "Behavior" not in metadata

        expected_pose_metadata = {
            "Skeletons": {
                metadata_key: {
                    "name": "SkeletonPoseEstimation",
                    "nodes": self.expected_keypoint_names,
                    "edges": [],
                },
            },
            "PoseEstimations": {
                metadata_key: {
                    "name": self.pose_estimation_name,
                    "source_software": "LightningPose",
                    "scorer": "heatmap_tracker",
                    "dimensions": [[self.original_video_height, self.original_video_width]],
                    "original_videos": [self.interface_kwargs["original_video_file_path"]],
                    "labeled_videos": None,
                    "skeleton_metadata_key": metadata_key,
                    "PoseEstimationSeries": {
                        keypoint_name: {
                            "name": f"PoseEstimationSeries{keypoint_name}",
                            "reference_frame": (
                                "(0,0) is the top-left pixel of the video frame, with x increasing "
                                "to the right and y increasing downward."
                            ),
                        }
                        for keypoint_name in self.expected_keypoint_names
                    },
                },
            },
        }

        # No Devices block: no pose format records a camera, so the writer supplies the one released
        # ndx-pose still requires alongside the frame dimensions and the video paths.
        assert "Devices" not in metadata
        assert metadata["Pose"] == expected_pose_metadata

    # TODO: remove when the legacy metadata["Behavior"]["PoseEstimation"] block is removed. The
    # mixin's conversion checks write from the dict-based format, so that is the covered path and
    # this is what holds the old one to writing the same file.
    def test_conversion_old_metadata_format(self, setup_interface):
        metadata = self.interface.get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"].update(session_start_time=datetime.now(timezone.utc))

        nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_old_metadata_format.nwb")
        self.interface.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
            **self.conversion_options,
        )
        self.check_read_nwb(nwbfile_path=nwbfile_path)
        self.check_written_values(nwbfile_path=nwbfile_path)

        # The legacy path keeps its own free text and its camera, which the dict-based path leaves to the
        # writer and does not write at all.
        nwbfile = read_nwb(nwbfile_path)
        pose_estimation_container = nwbfile.processing["behavior"].data_interfaces[self.pose_estimation_name]
        assert pose_estimation_container.description == "Contains the pose estimation series for each keypoint."
        assert [device.name for device in pose_estimation_container.devices] == ["CameraPoseEstimation"]
        for keypoint_name in self.expected_keypoint_names:
            pose_estimation_series = pose_estimation_container.pose_estimation_series[
                f"PoseEstimationSeries{keypoint_name}"
            ]
            assert pose_estimation_series.unit == "px"
            assert pose_estimation_series.description == f"The estimated position (x, y) of {keypoint_name} over time."
        nwbfile.read_io.close()

    def test_written_text_in_dict_based_format(self, setup_interface):
        """The dict-based metadata carries no free text, so the writer's and ndx-pose's defaults apply."""
        nwbfile = mock_NWBFile()
        metadata = self.interface.get_metadata(use_new_metadata_format=True)
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        pose_estimation_container = nwbfile.processing["behavior"][self.pose_estimation_name]
        assert pose_estimation_container.description is None
        for keypoint_name in self.expected_keypoint_names:
            pose_estimation_series = pose_estimation_container.pose_estimation_series[
                f"PoseEstimationSeries{keypoint_name}"
            ]
            assert pose_estimation_series.unit == "pixels"
            assert pose_estimation_series.description == f"Pose estimation series for {keypoint_name}."
            assert pose_estimation_series.reference_frame == (
                "(0,0) is the top-left pixel of the video frame, with x increasing to the right "
                "and y increasing downward."
            )
            assert pose_estimation_series.confidence_definition is None

    def test_series_conversion_options_are_deprecated(self, setup_interface):
        """The deprecated conversion options are routed into every series entry."""
        reference_frame = "(0,0) corresponds to the top left corner of the video."
        confidence_definition = "Softmax output of the deep neural network."

        nwbfile = mock_NWBFile()
        metadata = self.interface.get_metadata(use_new_metadata_format=True)
        with pytest.warns(FutureWarning, match="conversion option"):
            self.interface.add_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                reference_frame=reference_frame,
                confidence_definition=confidence_definition,
            )

        pose_estimation_container = nwbfile.processing["behavior"][self.pose_estimation_name]
        for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
            assert pose_estimation_series.reference_frame == reference_frame
            assert pose_estimation_series.confidence_definition == confidence_definition


class TestLightningPoseDataInterfaceWithStubTest(PoseEstimationInterfaceTestMixin):
    data_interface_cls = LightningPoseDataInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.csv"),
        original_video_file_path=str(
            BEHAVIOR_DATA_PATH / "lightningpose" / "outputs/2023-11-09/10-14-37/video_preds/test_vid.mp4"
        ),
        metadata_key="lightning_pose_key",
    )

    conversion_options = dict(stub_test=True)
    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        """The stub option is what this class is for: every series is truncated to ten frames."""
        nwbfile = read_nwb(self.nwbfile_path)
        pose_estimation_container = nwbfile.processing["behavior"].data_interfaces["PoseEstimation"]
        for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
            assert pose_estimation_series.data.shape[0] == 10
            assert pose_estimation_series.confidence.shape[0] == 10
        nwbfile.read_io.close()


class TestSLEAPInterface(PoseEstimationInterfaceTestMixin):
    data_interface_cls = SLEAPInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp"),
        video_file_path=str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4"),
        track_name="track_0",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        """What the .slp file records about the run, which is the provenance block and the video."""
        container_entry = metadata["Pose"]["PoseEstimations"]["sleap_track_0"]
        assert container_entry["name"] == "PoseEstimationTrack0"
        assert container_entry["source_software"] == "SLEAP"
        assert container_entry["source_software_version"] == "1.2.7"
        assert container_entry["scorer"] == "TopDownPredictor"

        # The definition describes what this interface writes, so it is the same on every .slp.
        for series_entry in container_entry["PoseEstimationSeries"].values():
            assert series_entry["confidence_definition"].startswith("Height of the peak in the SLEAP network")

        skeleton_entry = metadata["Pose"]["Skeletons"]["sleap_track_0"]
        assert skeleton_entry["subject"] == "track_0"
        assert skeleton_entry["nodes"] == [
            "head",
            "thorax",
            "abdomen",
            "wingL",
            "wingR",
            "forelegL4",
            "forelegR4",
            "midlegL4",
            "midlegR4",
            "hindlegL4",
            "hindlegR4",
            "eyeL",
            "eyeR",
        ]


@pytest.mark.skipif(
    SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED,
    reason="SLEAP conversion is not yet supported on macOS Intel with Python 3.13.",
)
class TestSLEAPMultipleVideos:
    """A .slp assembled in the SLEAP GUI can label several recordings, which are separate sessions.

    Built rather than downloaded: every .slp in the test data holds one video, and what is under test is
    our own indexing, since ``frame_idx`` is only unique within a video.
    """

    @staticmethod
    def _write_two_video_file(file_path) -> None:
        import sleap_io

        skeleton = sleap_io.Skeleton(["head", "tail"])
        track = sleap_io.Track(name="track_0")
        videos = [sleap_io.Video(filename=f"recording_{index}.mp4") for index in range(2)]
        labeled_frames = []
        for video_index, video in enumerate(videos):
            for frame_index in range(3):
                instance = sleap_io.PredictedInstance.from_numpy(
                    points_data=np.array([[video_index * 100.0 + frame_index, 1.0], [2.0, 3.0]]),
                    point_scores=np.array([0.9, 0.8]),
                    score=0.9,
                    skeleton=skeleton,
                    track=track,
                )
                labeled_frames.append(sleap_io.LabeledFrame(video=video, frame_idx=frame_index, instances=[instance]))
        sleap_io.save_slp(
            sleap_io.Labels(labeled_frames=labeled_frames, videos=videos, skeletons=[skeleton], tracks=[track]),
            str(file_path),
        )

    @pytest.fixture
    def two_video_file_path(self, tmp_path):
        file_path = tmp_path / "two_recordings.slp"
        self._write_two_video_file(file_path=file_path)
        return str(file_path)

    def test_available_videos(self, two_video_file_path):
        assert SLEAPInterface.get_available_videos(file_path=two_video_file_path) == ["recording_0", "recording_1"]

    def test_naming_a_video_is_required(self, two_video_file_path):
        with pytest.raises(ValueError, match="holds 2 recordings"):
            SLEAPInterface(file_path=two_video_file_path, track_name="track_0", frames_per_second=1.0)

    def test_unknown_video_raises(self, two_video_file_path):
        with pytest.raises(ValueError, match="Video 'nowhere' is not in this file"):
            SLEAPInterface(
                file_path=two_video_file_path, track_name="track_0", video_name="nowhere", frames_per_second=1.0
            )

    def test_each_recording_writes_its_own_frames(self, two_video_file_path):
        """Frames of the two recordings share indices 0..2 and must not collapse onto each other."""
        for video_index, video_name in enumerate(["recording_0", "recording_1"]):
            interface = SLEAPInterface(
                file_path=two_video_file_path,
                track_name="track_0",
                video_name=video_name,
                frames_per_second=1.0,
            )
            nwbfile = mock_NWBFile()
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

            series = nwbfile.processing["behavior"]["PoseEstimationTrack0"].pose_estimation_series
            head = series["PoseEstimationSeriesHead"]
            assert head.data.shape == (3, 2)
            # The x coordinate encodes which recording the frame came from.
            assert_array_equal(head.data[:, 0], [video_index * 100.0 + frame for frame in range(3)])
            assert_array_equal(head.get_timestamps(), [0.0, 1.0, 2.0])


@pytest.mark.skipif(
    SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED,
    reason="SLEAP conversion is not yet supported on macOS Intel with Python 3.13.",
)
class TestSLEAPMultipleTracks:
    """A multi-animal .slp takes one interface per track, since an NWB file holds one subject."""

    file_path = str(BEHAVIOR_DATA_PATH / "sleap" / "predictions_1.2.7_provenance_and_tracking.slp")
    video_file_path = str(BEHAVIOR_DATA_PATH / "sleap" / "melanogaster_courtship.mp4")

    def test_writing_every_track_is_deprecated(self):
        """Not naming a track delegates to the pre-``track_name`` interface, behind a FutureWarning.

        The warning is raised where the choice is made, in the constructor, and the whole object is then
        the old one: it emits no pose metadata and writes into a per-video processing module.
        """
        with pytest.warns(FutureWarning, match="one interface per track"):
            interface = SLEAPInterface(file_path=self.file_path, video_file_path=self.video_file_path)

        assert sorted(interface.get_metadata()) == ["NWBFile"]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)
        processing_module = nwbfile.processing["SLEAP_VIDEO_000_20190128_113421"]
        assert set(processing_module.data_interfaces) == {"track=track_0", "track=track_1"}

    def test_unknown_track_raises(self):
        with pytest.raises(ValueError, match="Track 'nobody' is not in this file"):
            SLEAPInterface(file_path=self.file_path, track_name="nobody")

    def test_one_container_per_track(self):
        nwbfile = mock_NWBFile()
        for track_name in SLEAPInterface.get_available_tracks(file_path=self.file_path):
            interface = SLEAPInterface(
                file_path=self.file_path,
                video_file_path=self.video_file_path,
                track_name=track_name,
            )
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        behavior_module = nwbfile.processing["behavior"]
        assert "PoseEstimationTrack0" in behavior_module.data_interfaces
        assert "PoseEstimationTrack1" in behavior_module.data_interfaces
        assert set(behavior_module["Skeletons"].skeletons) == {
            "SkeletonPoseEstimationTrack0",
            "SkeletonPoseEstimationTrack1",
        }

    def test_aligning_a_named_track_round_trips(self):
        """What ``get_timestamps`` hands out is what ``set_aligned_timestamps`` takes back.

        Both are one time per labeled frame, not per video frame, so a shift applied through the base
        class does not re-index a vector that is already selected.
        """
        for track_name in SLEAPInterface.get_available_tracks(file_path=self.file_path):
            interface = SLEAPInterface(
                file_path=self.file_path, video_file_path=self.video_file_path, track_name=track_name
            )
            before = interface.get_timestamps()
            interface.set_aligned_starting_time(aligned_starting_time=1.23)
            after = interface.get_timestamps()
            assert len(after) == len(before)
            assert after[0] == pytest.approx(before[0] + 1.23)

    def test_timestamps_come_from_the_video(self):
        from neuroconv.datainterfaces.behavior.sleap.sleap_utils import extract_timestamps

        interface = SLEAPInterface(file_path=self.file_path, video_file_path=self.video_file_path, track_name="track_0")
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        # Not every video frame carries a prediction, so the written times are a subset of the video's.
        expected_timestamps = set(extract_timestamps(self.video_file_path))
        container = nwbfile.processing["behavior"]["PoseEstimationTrack0"]
        for series in container.pose_estimation_series.values():
            assert set(series.get_timestamps()).issubset(expected_timestamps)


@pytest.mark.skipif(
    SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED,
    reason="SLEAP conversion is not yet supported on macOS Intel with Python 3.13.",
)
class TestSLEAPHumanInstances(PoseEstimationInterfaceTestMixin):
    """A proofread .slp holds the network's instances and a person's corrections side by side.

    ``track_0`` of this recording carries both arrangements a correction can take: 41 frames where a
    human instance shares the track with a model one, and 6 where it is alone on the track because the
    network found nothing there. Reading the rows from the model's instances alone dropped the second
    kind while the timestamps still counted them, so the samples after one slid onto earlier frames'
    times.

    The counts below are properties of the file, recorded next to it in ``sleap/README.md`` on gin. They
    are written out rather than recomputed so that a fixture swapped underneath this fails loudly.
    """

    data_interface_cls = SLEAPInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH / "sleap" / "human_and_model_instances" / "solo_human_instances" / "remora_video_1.slp"
        ),
        track_name="track_0",
        frames_per_second=30.0,
    )
    save_directory = OUTPUT_PATH

    labeled_frames = 251  # every one writes a row, including the six the model missed

    def _rows(self):
        """The ``(human instance, model instance)`` behind each written row, read from the source.

        One entry per row the conversion produces, so an index here is a row index in every series. Only
        frames where this track has an instance of either kind produce a row.
        """
        import sleap_io

        track_name = self.interface_kwargs["track_name"]
        labels = sleap_io.load_slp(self.interface_kwargs["file_path"])
        rows = []
        for frame in sorted(labels.labeled_frames, key=lambda labeled_frame: labeled_frame.frame_idx):
            human = [i for i in frame.user_instances if i.track is not None and i.track.name == track_name]
            model = [i for i in frame.predicted_instances if i.track is not None and i.track.name == track_name]
            if human or model:
                rows.append((human[0] if human else None, model[0] if model else None))
        return rows

    def run_custom_checks(self):
        """What this file exists to prove, asserted against the file the conversion actually wrote."""
        nwbfile = read_nwb(self.nwbfile_path)
        container = nwbfile.processing["behavior"]["PoseEstimationTrack0"]
        rows = self._rows()
        assert len(rows) == self.labeled_frames

        # One row per labeled frame. Building the rows from the model's instances alone lost the frames
        # a person labeled where the network found nothing, and the times then belonged to other frames.
        for pose_estimation_series in container.pose_estimation_series.values():
            assert np.asarray(pose_estimation_series.data).shape[0] == self.labeled_frames
            assert len(pose_estimation_series.get_timestamps()) == self.labeled_frames

        # A person places a point rather than estimating it, so a human row carries 1.0, and a point the
        # annotator marked not visible carries NaN. Which rows those are comes from the source: SLEAP does
        # not clamp its own scores, 134 model points on this track exceed 1.0, and six sit within a
        # thousandth of it, so a confidence of exactly 1.0 does not identify a human point on its own.
        for index, keypoint_name in enumerate(container.skeleton.nodes):
            pose_estimation_series = container.pose_estimation_series[self._series_name(keypoint_name)]
            expected = []
            for human, model in rows:
                if human is None:
                    expected.append(model.numpy(scores=True)[index, 2])
                    continue
                placed = not np.isnan(human.numpy()[index, 0])
                expected.append(1.0 if placed else np.nan)
            assert_allclose(np.asarray(pose_estimation_series.confidence), expected, equal_nan=True)

        nwbfile.read_io.close()

    @staticmethod
    def _series_name(keypoint_name: str) -> str:
        """The container orders its series by name, so a keypoint index cannot be read off their order."""
        return f"PoseEstimationSeries{keypoint_name.title().replace('_', '')}"

    def test_a_human_instance_wins_over_the_model_one(self, setup_interface):
        """Proofreading means correcting the network, so the correction is what gets written.

        The expected coordinates come from ``sleap_io`` directly rather than from the interface, so the
        comparison is against the source and not against the writer's own reading of it.
        """
        rows = self._rows()
        row, (human, model) = next(
            (index, pair) for index, pair in enumerate(rows) if pair[0] is not None and pair[1] is not None
        )
        assert not np.allclose(human.numpy(), model.numpy(), equal_nan=True)

        nwbfile = mock_NWBFile()
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=self.interface.get_metadata())
        container = nwbfile.processing["behavior"]["PoseEstimationTrack0"]
        for index, keypoint_name in enumerate(container.skeleton.nodes):
            pose_estimation_series = container.pose_estimation_series[self._series_name(keypoint_name)]
            assert_array_equal(np.asarray(pose_estimation_series.data)[row], human.numpy()[index])

    def check_extracted_metadata(self, metadata: dict):
        """The definition states the direction that is true.

        A human point is written as 1.0, which does not make a 1.0 a human point: the network's own
        scores are not bounded by 1 and can reach it.
        """
        entries = metadata["Pose"]["PoseEstimations"][self.interface.metadata_key]["PoseEstimationSeries"]
        for entry in entries.values():
            definition = entry["confidence_definition"]
            assert definition.startswith("Height of the peak in the SLEAP network")
            assert "is not bounded by 1" in definition
            assert "written with a confidence of 1.0" in definition


@pytest.mark.skipif(
    SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED,
    reason="SLEAP conversion is not yet supported on macOS Intel with Python 3.13.",
)
class TestSLEAPEmptyTracksAndUntrackedInstances:
    """A .slp records the identities the tracking run created, not the ones that survived it.

    This recording declares four tracks and only ``track_0`` is ever populated, and it also carries 12
    human-placed instances in 9 frames that no track claims. Both are ordinary results of proofreading:
    clearing a track leaves the ``Track`` object behind, and an instance added where the model found
    nothing does not inherit an identity.
    """

    file_path = str(
        BEHAVIOR_DATA_PATH / "sleap" / "edge_cases" / "empty_tracks_and_untracked_instances" / "remora_video_2.slp"
    )

    def test_only_populated_tracks_are_offered(self):
        assert SLEAPInterface.get_available_tracks(file_path=self.file_path) == ["track_0"]

    def test_declared_but_empty_track_says_so(self):
        """A name the file declares is a different mistake from a name it does not."""
        with pytest.raises(ValueError, match=r"Track 'track_2' is declared .* Tracks that do: \['track_0'\]"):
            SLEAPInterface(file_path=self.file_path, track_name="track_2", frames_per_second=30.0)

    def test_unknown_track_says_so(self):
        with pytest.raises(ValueError, match="Track 'nobody' is not in this file"):
            SLEAPInterface(file_path=self.file_path, track_name="nobody", frames_per_second=30.0)

    def test_untracked_instances_are_reported_and_not_written(self):
        interface = SLEAPInterface(file_path=self.file_path, track_name="track_0", frames_per_second=30.0)
        nwbfile = mock_NWBFile()
        with pytest.warns(UserWarning, match="12 instances in 9 frames .* carry no track"):
            interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        container = nwbfile.processing["behavior"]["PoseEstimationTrack0"]
        series = next(iter(container.pose_estimation_series.values()))
        # One row per frame carrying a track_0 instance, and none for the 8 frames that hold only
        # untracked ones.
        assert series.data.shape[0] == 147


@pytest.mark.skipif(
    SLEAP_MACOS_INTEL_PYTHON_313_UNSUPPORTED,
    reason="SLEAP conversion is not yet supported on macOS Intel with Python 3.13.",
)
class TestSLEAPWithoutTracks:
    """A labeling project, or a single-animal recording that was never tracked, assigns no identities.

    SLEAP's own analysis export reads such a file as one individual (`tracks = labels.tracks or [None]`
    in ``sleap/info/write_tracking_h5.py``) and so does the interface. Built rather than downloaded,
    since every .slp in the test data is the output of a tracking run.
    """

    @staticmethod
    def _write_untracked_file(file_path, declared_track_name=None, instances_per_frame=1) -> None:
        import sleap_io

        skeleton = sleap_io.Skeleton(["head", "tail"])
        video = sleap_io.Video(filename="recording.mp4")
        labeled_frames = [
            sleap_io.LabeledFrame(
                video=video,
                frame_idx=frame_index,
                instances=[
                    sleap_io.Instance.from_numpy(
                        points_data=np.array([[float(frame_index), float(instance_index)], [2.0, 3.0]]),
                        skeleton=skeleton,
                    )
                    for instance_index in range(instances_per_frame)
                ],
            )
            for frame_index in range(3)
        ]
        tracks = [sleap_io.Track(name=declared_track_name)] if declared_track_name is not None else []
        sleap_io.save_slp(
            sleap_io.Labels(labeled_frames=labeled_frames, videos=[video], skeletons=[skeleton], tracks=tracks),
            str(file_path),
        )

    def test_no_tracks_declared_writes_one_individual(self, tmp_path):
        file_path = tmp_path / "labeling_project.slp"
        self._write_untracked_file(file_path=file_path)

        interface = SLEAPInterface(file_path=str(file_path), frames_per_second=1.0)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        container = nwbfile.processing["behavior"]["PoseEstimation"]
        head = container.pose_estimation_series["PoseEstimationSeriesHead"]
        assert_array_equal(head.data[:, 0], [0.0, 1.0, 2.0])

    def test_tracks_declared_but_all_empty_writes_one_individual(self, tmp_path):
        """A cleared track leaves the Track object behind, which does not make the file a tracked one."""
        file_path = tmp_path / "cleared_tracks.slp"
        self._write_untracked_file(file_path=file_path, declared_track_name="track_0")

        interface = SLEAPInterface(file_path=str(file_path), frames_per_second=1.0)
        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

        assert "PoseEstimation" in nwbfile.processing["behavior"].data_interfaces

    def test_naming_a_track_says_the_file_has_none(self, tmp_path):
        file_path = tmp_path / "labeling_project.slp"
        self._write_untracked_file(file_path=file_path)
        with pytest.raises(ValueError, match="no instance in this file carries a track"):
            SLEAPInterface(file_path=str(file_path), track_name="track_0", frames_per_second=1.0)

    def test_several_untracked_instances_in_a_frame_raises(self, tmp_path):
        """The multi-animal labeling project, which SLEAP writes into one slot with the last one winning."""
        file_path = tmp_path / "two_animals_labeled.slp"
        self._write_untracked_file(file_path=file_path, instances_per_frame=2)

        interface = SLEAPInterface(file_path=str(file_path), frames_per_second=1.0)
        with pytest.raises(ValueError, match="holds 2 instances and none of them carries a track"):
            interface.get_timestamps()


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
)
class TestDeepLabCutInterface(PoseEstimationInterfaceTestMixin):
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
        sampling_frequency=30.0,
        metadata_key="deep_lab_cut_key",
    )
    save_directory = OUTPUT_PATH

    # TODO: remove test_metadata_old_list_format and check_extracted_metadata_old_list_format when
    # the old list format is removed (then check_extracted_metadata is the only metadata hook).
    def test_metadata_old_list_format(self, setup_interface):
        metadata = self.interface.get_metadata(use_new_metadata_format=False)
        self.check_extracted_metadata_old_list_format(metadata)

    def check_extracted_metadata(self, metadata: dict):
        """The dict-based ("new") metadata shape, checked against a full expected dict.

        The equality is strict: provenance-first means ``get_metadata`` emits only source-derived
        values and object names (no ``description``/``unit`` defaults, those are applied by the
        writer), so any extra emitted field would fail the comparison. ``reference_frame`` is
        source-derived here: image coordinates are a property of the tracker's output rather than a
        stand-in for something the file failed to record.
        """
        metadata_key = "deep_lab_cut_key"
        bodyparts = ["snout", "leftear", "rightear", "tailbase"]

        # The legacy top-level "PoseEstimation" block must be gone in the dict-based shape.
        assert "PoseEstimation" not in metadata

        expected_pose_metadata = {
            "Skeletons": {
                metadata_key: {
                    "name": "SkeletonPoseEstimationDeepLabCut_Ind1",
                    "nodes": bodyparts,
                    "edges": [],
                    "subject": "ind1",
                },
            },
            "PoseEstimations": {
                metadata_key: {
                    "name": "PoseEstimationDeepLabCut",
                    "source_software": "DeepLabCut",
                    "scorer": "DLC_resnet50_openfieldAug20shuffle1_30000",
                    # No dimensions: the config's video_sets keys are absolute paths from the training
                    # machine, so the lookup misses and nothing invents a frame size. See issue #1046.
                    "dimensions": None,
                    "original_videos": None,
                    "skeleton_metadata_key": metadata_key,
                    "PoseEstimationSeries": {
                        bodypart: {
                            "name": f"PoseEstimationSeries{bodypart.capitalize()}",
                            "reference_frame": (
                                "(0,0) is the top-left pixel of the video frame, with x increasing "
                                "to the right and y increasing downward."
                            ),
                        }
                        for bodypart in bodyparts
                    },
                },
            },
        }

        # No Devices block: no pose format records a camera, so the writer supplies the one released
        # ndx-pose still requires alongside the frame dimensions and the video paths.
        assert "Devices" not in metadata
        assert metadata["Pose"] == expected_pose_metadata

    def check_extracted_metadata_old_list_format(self, metadata: dict):
        # Define expected values directly here
        expected_bodyparts = ["snout", "leftear", "rightear", "tailbase"]
        # The legacy shape names the container after the metadata_key, which is one of the things the
        # dict-based shape separates. It goes with the flag.
        container_name = self.interface_kwargs["metadata_key"]
        skeleton_name = f"Skeleton{container_name}_{self.interface_kwargs['subject_name'].capitalize()}"
        device_name = f"Camera{container_name}"

        assert "PoseEstimation" in metadata
        pose_metadata = metadata["PoseEstimation"]

        # Check Skeletons
        assert "Skeletons" in pose_metadata
        assert skeleton_name in pose_metadata["Skeletons"]
        skeleton = pose_metadata["Skeletons"][skeleton_name]
        assert skeleton["name"] == skeleton_name
        assert set(skeleton["nodes"]) == set(expected_bodyparts)

        # Check Devices
        assert "Devices" in pose_metadata
        assert device_name in pose_metadata["Devices"]
        device = pose_metadata["Devices"][device_name]
        assert device["name"] == device_name

        # Check PoseEstimationContainers
        assert "PoseEstimationContainers" in pose_metadata
        assert container_name in pose_metadata["PoseEstimationContainers"]
        container = pose_metadata["PoseEstimationContainers"][container_name]
        assert container["name"] == container_name
        assert container["source_software"] == "DeepLabCut"
        assert container["skeleton"] == skeleton_name
        assert container["devices"] == [device_name]

        # Check PoseEstimationSeries
        assert "PoseEstimationSeries" in container
        for bodypart in expected_bodyparts:
            assert bodypart in container["PoseEstimationSeries"]
            series = container["PoseEstimationSeries"][bodypart]
            assert "unit" in series
            assert series["unit"] == "pixels"

    def run_custom_checks(self):
        self.check_written_timing(nwbfile_path=self.nwbfile_path)

    def check_written_timing(self, nwbfile_path: str):
        """The interface was given a constant frame rate, so the series carry it rather than timestamps."""
        nwbfile = read_nwb(nwbfile_path)
        pose_estimation_container = nwbfile.processing["behavior"].data_interfaces["PoseEstimationDeepLabCut"]
        for pose_estimation_series in pose_estimation_container.pose_estimation_series.values():
            assert pose_estimation_series.starting_time == 0
            assert pose_estimation_series.rate == 30.0
        nwbfile.read_io.close()

    def test_conversion_new_metadata_format(self, setup_interface):
        """Run the conversion with the dict-based ("new") metadata format and read it back.

        The mixin's standard conversion checks only exercise the default (old) format; this runs
        ``add_to_nwbfile`` with ``get_metadata(use_new_metadata_format=True)`` so the new-format write
        path is covered, reusing ``check_read_nwb`` (the written NWB is the same for both formats).
        This is a DLC-local prototype of the generic mixin coverage planned for all migrated
        interfaces; remove it once the mixin runs the conversion checks in the new format too.
        """
        metadata = self.interface.get_metadata(use_new_metadata_format=True)
        metadata["NWBFile"].update(session_start_time=datetime.now(timezone.utc))
        nwbfile_path = str(self.save_directory / f"{self.data_interface_cls.__name__}_new_metadata_format.nwb")
        self.interface.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        self.check_read_nwb(nwbfile_path=nwbfile_path)

    def test_edges_come_from_the_project_config(self, setup_interface, tmp_path):
        """The config states the skeleton as bodypart names, which is the source that is actually there.

        The part affinity field graph the interface falls back to lives in a ``_meta.pickle`` beside the
        output file that DeepLabCut does not always write, and this repository's own test data has none, so
        without the config the skeleton is written with nodes and no edges.
        """
        import yaml

        config_file_path = Path(self.interface_kwargs["config_file_path"])
        config_dict = yaml.safe_load(config_file_path.read_text(encoding="utf-8"))
        config_dict["skeleton"] = [["snout", "leftear"], ["leftear", "rightear"]]
        config_with_skeleton_path = tmp_path / "config.yaml"
        config_with_skeleton_path.write_text(yaml.safe_dump(config_dict), encoding="utf-8")

        interface = DeepLabCutInterface(
            file_path=self.interface_kwargs["file_path"],
            config_file_path=str(config_with_skeleton_path),
            subject_name=self.interface_kwargs["subject_name"],
            sampling_frequency=self.interface_kwargs["sampling_frequency"],
        )

        metadata = interface.get_metadata()
        skeleton = metadata["Pose"]["Skeletons"]["deep_lab_cut_metadata_key"]
        assert skeleton["nodes"] == ["snout", "leftear", "rightear", "tailbase"]
        assert skeleton["edges"] == [[0, 1], [1, 2]]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        written_skeleton = nwbfile.processing["behavior"]["Skeletons"][skeleton["name"]]
        assert_array_equal(written_skeleton.edges[:], [[0, 1], [1, 2]])

    def test_a_config_naming_no_skeleton_writes_no_edges(self, setup_interface):
        """Which is this repository's test data: its config carries ``skeleton: []``."""
        metadata = self.interface.get_metadata()
        assert metadata["Pose"]["Skeletons"][self.interface.metadata_key]["edges"] == []

    def test_subject_not_linked(self, setup_interface):
        """
        Test that skeleton.subject is None if the subject_id in the metadata doesn't match the nwbfile.
        """

        nwbfile = mock_NWBFile()

        subject = mock_Subject(subject_id="MockSubject")
        nwbfile.subject = subject
        # Stated rather than left to default: no metadata means the legacy shape, which names its objects
        # after the metadata_key.
        self.interface.add_to_nwbfile(nwbfile=nwbfile, metadata=self.interface.get_metadata())

        skeletons = nwbfile.processing["behavior"]["Skeletons"]
        skeleton = skeletons[f"SkeletonPoseEstimationDeepLabCut_{self.interface.subject_name.capitalize()}"]
        assert skeleton.subject is None


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
)
class TestDeepLabCutInterfaceWithLandmarks(PoseEstimationInterfaceTestMixin):
    """A multi-animal project can also track landmarks, points of the scene rather than of a subject.

    DeepLabCut calls them unique bodyparts and files them under an ``individuals`` group named
    ``single``, so the keypoints in the file are the subjects' plus the landmarks and any one subject's
    are a strict subset. Reading the bodyparts from the whole file while the series came from one
    individual wrote a three-series container against a thirty-three node skeleton, silently.

    Leafcutter ants, two of them, three keypoints each, beside thirty arena landmarks whose names they
    share none of.
    """

    data_interface_cls = DeepLabCutInterface
    interface_kwargs = dict(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "multi_subject_h5"
            / "landmarks_and_subject_keypoints"
            / "ant_video_5DLC_dlcrnetms5_AntsFeb11shuffle1_100000_el.h5"
        ),
        subject_name="ant_1",
        sampling_frequency=10.0,  # no config.yaml is published with this data, so the rate is given here
    )
    save_directory = OUTPUT_PATH

    subject_bodyparts = ["ant_head", "ant_midbody", "ant_end"]

    def check_extracted_metadata(self, metadata: dict):
        """The skeleton is the subject's keypoints, not the file's."""
        skeleton_entry = metadata["Pose"]["Skeletons"][self.interface.metadata_key]
        assert skeleton_entry["nodes"] == self.subject_bodyparts

        series_entries = metadata["Pose"]["PoseEstimations"][self.interface.metadata_key]["PoseEstimationSeries"]
        assert list(series_entries) == self.subject_bodyparts

        # Read off the file rather than off its name, which carries the tracker suffix ``_el`` as well.
        assert metadata["Pose"]["PoseEstimations"][self.interface.metadata_key]["scorer"] == (
            "DLC_dlcrnetms5_AntsFeb11shuffle1_100000"
        )

    def run_custom_checks(self):
        """The written skeleton and the written series describe the same keypoints."""
        nwbfile = read_nwb(self.nwbfile_path)
        container = nwbfile.processing["behavior"].data_interfaces["PoseEstimationDeepLabCut"]

        assert list(container.skeleton.nodes) == self.subject_bodyparts
        assert len(container.pose_estimation_series) == len(self.subject_bodyparts)
        nwbfile.read_io.close()

    def test_the_file_holds_landmarks_this_subject_does_not(self):
        """The fixture only tests anything while the two sets differ, so state that they do."""
        file_bodyparts = pd.read_hdf(self.interface_kwargs["file_path"]).columns.get_level_values("bodyparts")
        assert set(self.subject_bodyparts) < set(file_bodyparts.unique())
        assert len(file_bodyparts.unique()) == 33

    def test_every_subject_gets_its_own_keypoints(self):
        """The other ant reads the same file and must not pick up the landmarks either."""
        interface = DeepLabCutInterface(
            file_path=self.interface_kwargs["file_path"], subject_name="drug_ant2", sampling_frequency=10.0
        )
        skeleton_entry = interface.get_metadata()["Pose"]["Skeletons"][interface.metadata_key]
        assert skeleton_entry["nodes"] == self.subject_bodyparts


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
)
class TestDeepLabCutInterfaceNoConfigFile(PoseEstimationInterfaceTestMixin):
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
        sampling_frequency=30.0,
        metadata_key="deep_lab_cut_key",
    )
    save_directory = OUTPUT_PATH


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
)
class TestDeepLabCutInterfaceSetTimestamps(PoseEstimationInterfaceTestMixin):
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
        sampling_frequency=30.0,
        metadata_key="deep_lab_cut_key",
    )

    save_directory = OUTPUT_PATH

    def run_custom_checks(self):
        self.check_custom_timestamps(nwbfile_path=self.nwbfile_path)

    def check_custom_timestamps(self, nwbfile_path: str):
        # This is irregular timestamps
        custom_timestamps = np.concatenate(
            (
                np.linspace(10, 110, 1000),
                np.linspace(150, 250, 1000),
                np.linspace(300, 400, 330),
            )
        )

        metadata = self.interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())

        self.interface.set_aligned_timestamps(custom_timestamps)
        assert len(self.interface._timestamps) == 2330

        self.interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)

        nwbfile = read_nwb(nwbfile_path)
        assert "behavior" in nwbfile.processing
        processing_module_interfaces = nwbfile.processing["behavior"].data_interfaces
        assert "PoseEstimationDeepLabCut" in processing_module_interfaces

        pose_estimation_series_in_nwb = processing_module_interfaces["PoseEstimationDeepLabCut"].pose_estimation_series

        for pose_estimation in pose_estimation_series_in_nwb.values():
            pose_timestamps = pose_estimation.timestamps
            np.testing.assert_array_equal(pose_timestamps, custom_timestamps)
        nwbfile.read_io.close()


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
)
class TestDeepLabCutInterfaceFromCSV(PoseEstimationInterfaceTestMixin):
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
        sampling_frequency=30.0,
    )
    save_directory = OUTPUT_PATH


@pytest.fixture
def clean_pose_extension_import():
    """Hide ndx_pose from the test, then put the process back the way it was found.

    Deleting the modules is only half of it. The re-import inside the interface builds a second
    generation of every ndx-pose container class, and hdmf's ``register_container_type`` evicts the first
    generation from its class to data type map when the second registers under the same name. Restoring
    ``sys.modules`` without restoring that registration would leave the process holding classes hdmf no
    longer recognises, and a later ``PoseEstimation`` build would be handed an ancestor's spec.
    """
    saved_modules = {name: module for name, module in sys.modules.items() if name.startswith("ndx_pose")}
    for name in saved_modules:
        del sys.modules[name]

    yield

    sys.modules.update(saved_modules)
    pose_module = saved_modules.get("ndx_pose")
    if pose_module is None:
        return

    from pynwb import get_type_map

    type_map = get_type_map(copy=False)
    for attribute_name in dir(pose_module):
        candidate = getattr(pose_module, attribute_name)
        if not isinstance(candidate, type) or not getattr(candidate, "__module__", "").startswith("ndx_pose"):
            continue
        # Selected by defining module rather than by the `namespace` class attribute, which hdmf rewrites:
        # every `merge` into a fresh type map re-registers shared class objects and stamps `namespace` and
        # `neurodata_type` onto them, so `PoseEstimation.namespace` can read `ndx-vame` in a process that
        # has imported ndx-vame.
        data_type = getattr(candidate, "neurodata_type", None)
        if data_type is not None:
            type_map.register_container_type("ndx-pose", data_type, candidate)


@pytest.mark.skipif(
    platform == "darwin" and python_version < version.parse("3.10") or ndx_pose_version < version.parse("0.2.0"),
    reason="Interface requires ndx-pose version >= 0.2.0",
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
        sampling_frequency=30.0,
    )

    interface = DeepLabCutInterface(**interface_kwargs)
    metadata = interface.get_metadata()
    metadata["NWBFile"]["session_start_time"] = datetime(2023, 7, 24, 9, 30, 55, 440600, tzinfo=timezone.utc)

    nwbfile_path = tmp_path / "test.nwb"
    interface.run_conversion(nwbfile_path=nwbfile_path, metadata=metadata, overwrite=True)
    read_nwbfile = read_nwb(nwbfile_path)
    pose_estimation_container = read_nwbfile.processing["behavior"]["PoseEstimationDeepLabCut"]

    assert len(pose_estimation_container.fields) > 0
    read_nwbfile.read_io.close()


def test_deep_lab_cut_refuses_to_write_without_timing():
    """Neither the output file nor the config records a frame rate, so writing has to be refused."""
    interface = DeepLabCutInterface(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
    )

    with pytest.raises(ValueError, match="No timing information is available"):
        interface.add_to_nwbfile(nwbfile=mock_NWBFile())


def test_deep_lab_cut_sampling_frequency_converts_frames_to_seconds():
    """A frame index is a time only once divided by the rate, which is what the argument is for."""
    interface = DeepLabCutInterface(
        file_path=str(
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        ),
        sampling_frequency=30.0,
    )

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile)

    pose_estimation = nwbfile.processing["behavior"]["PoseEstimationDeepLabCut"]
    series = next(iter(pose_estimation.pose_estimation_series.values()))

    # The fixture's index is a contiguous frame count, so frame / 30 Hz is a regular series and the
    # writer stores it as starting_time plus rate rather than as a timestamps vector.
    assert series.timestamps is None
    assert series.starting_time == 0.0
    assert series.rate == 30.0


class TestDeepLabCutInterfaceGetAvailableSubjects:
    """Test the get_available_subjects static method of DeepLabCutInterface."""

    default_subject_name = "ind1"

    def test_get_available_subjects_multi_subject_h5(self):
        """Test extracting subjects from a multi-subject H5 file."""
        file_path = (
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "multi_subject_h5"
            / "log07-20-2023(1-XFN1-XFN3).1DLC_resnet50_SocialWSep18shuffle5_100000_el_stubbed.h5"
        )

        subjects = DeepLabCutInterface.get_available_subjects(file_path)
        expected_subjects = ["rat 1", "rat 2"]

        assert isinstance(subjects, list)
        assert len(subjects) == 2
        assert set(subjects) == set(expected_subjects)

    def test_get_available_subjects_single_subject_h5(self):
        """Test extracting subjects from a single-subject H5 file."""
        file_path = (
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "open_field_without_video"
            / "m3v1mp4DLC_resnet50_openfieldAug20shuffle1_30000.h5"
        )

        subjects = DeepLabCutInterface.get_available_subjects(file_path)
        expected_subjects = [self.default_subject_name]

        assert isinstance(subjects, list)
        assert len(subjects) == 1
        assert subjects == expected_subjects

    def test_get_available_subjects_csv(self):
        """Test extracting subjects from a CSV file."""
        file_path = (
            BEHAVIOR_DATA_PATH
            / "DLC"
            / "SL18_csv"
            / "SL18_D19_S01_F01_BOX_SLP_20230503_112642.1DLC_resnet50_SubLearnSleepBoxRedLightJun26shuffle1_100000_stubbed.csv"
        )

        subjects = DeepLabCutInterface.get_available_subjects(file_path)
        expected_subjects = [self.default_subject_name]

        assert isinstance(subjects, list)
        assert len(subjects) == 1
        assert subjects == expected_subjects

    def test_get_available_subjects_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent files."""
        non_existent_file = Path("/non/existent/file.h5")

        with pytest.raises(FileNotFoundError, match="File .* does not exist"):
            DeepLabCutInterface.get_available_subjects(non_existent_file)

    def test_get_available_subjects_invalid_file(self, tmp_path):
        """Test that IOError is raised for invalid DLC files."""
        # Create a temporary file with invalid suffix
        invalid_file = tmp_path / "test_file.invalid_suffix"
        invalid_file.touch()

        with pytest.raises(IOError, match="not a valid DeepLabCut output data file"):
            DeepLabCutInterface.get_available_subjects(invalid_file)


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.3.0"),
    reason="Interface requires ndx-pose version >= 0.3.0",
)
class TestDANNCEInterface(DataInterfaceTestMixin, TemporalAlignmentMixin):
    data_interface_cls = DANNCEInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "dannce" / "save_data_MAX.mat"),
        sampling_rate=30.0,
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        metadata_key = "PoseEstimationDANNCE"
        skeleton_name = f"Skeleton{metadata_key}_Ind1"
        device_name = "Camera1"

        assert device_name in metadata["Devices"]

        pose_metadata = metadata["Behavior"]["Pose"]

        # Check Skeletons
        assert metadata_key in pose_metadata["Skeletons"]
        skeleton = pose_metadata["Skeletons"][metadata_key]
        assert skeleton["name"] == skeleton_name
        assert len(skeleton["nodes"]) == 23

        # Check PoseEstimations
        assert metadata_key in pose_metadata["PoseEstimations"]
        container = pose_metadata["PoseEstimations"][metadata_key]
        assert container["name"] == metadata_key
        assert container["source_software"] == "DANNCE"
        assert container["skeleton_metadata_key"] == metadata_key
        assert container["device_metadata_keys"] == [device_name]

        # Check PoseEstimationSeries
        series = container["PoseEstimationSeries"]
        assert len(series) == 23
        for landmark_meta in series.values():
            assert landmark_meta["unit"] == "millimeters"

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            assert "behavior" in nwbfile.processing
            behavior = nwbfile.processing["behavior"]
            assert "PoseEstimationDANNCE" in behavior.data_interfaces
            assert "Skeletons" in behavior.data_interfaces

            pe = behavior.data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            assert len(pe.pose_estimation_series) == 23
            assert pe.source_software == "DANNCE"

            for series in pe.pose_estimation_series.values():
                assert series.data.shape == (400, 3)
                assert series.confidence.shape == (400,)
                assert series.unit == "millimeters"

            # The camera device is linked via a per-camera PoseEstimation child.
            assert len(pe.pose_estimations) == 1
            camera_pose_estimation = next(iter(pe.pose_estimations.values()))
            assert camera_pose_estimation.device.name == "Camera1"

            skeleton = pe.skeleton
            assert len(skeleton.nodes[:]) == 23


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.3.0"),
    reason="Interface requires ndx-pose version >= 0.3.0",
)
class TestDANNCEInterfaceWithCalibration(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """Real-data coverage for the DANNCE-specific multi-camera + calibration-parsing path, which
    the plain `TestDANNCEInterface` above (single camera, no calibration) does not exercise."""

    data_interface_cls = DANNCEInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "dannce" / "save_data_MAX.mat"),
        sampling_rate=30.0,
        calibration_path=str(BEHAVIOR_DATA_PATH / "dannce" / "calibration"),
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert "Camera1" in metadata["Devices"]
        assert "Camera2" in metadata["Devices"]

        container = metadata["Behavior"]["Pose"]["PoseEstimations"]["PoseEstimationDANNCE"]
        assert container["device_metadata_keys"] == ["Camera1", "Camera2"]

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import CalibratedCamera, MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            pe = nwbfile.processing["behavior"].data_interfaces["PoseEstimationDANNCE"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            assert len(pe.pose_estimations) == 2

            for camera_name in ("Camera1", "Camera2"):
                device = nwbfile.devices[camera_name]
                assert isinstance(device, CalibratedCamera)
                assert device.intrinsic_matrix.shape == (3, 3)


@pytest.mark.skipif(
    ndx_pose_version < version.parse("0.3.0"),
    reason="Interface requires ndx-pose version >= 0.3.0",
)
class TestDANNCEInterfaceMultiAnimal(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """Real-data coverage for the multi-animal sDANNCE path (4D 'pred', selected via
    animal_index), which the plain `TestDANNCEInterface` above (3D 'pred') does not exercise."""

    data_interface_cls = DANNCEInterface
    interface_kwargs = dict(
        file_path=str(BEHAVIOR_DATA_PATH / "dannce" / "save_data_sdannce.mat"),
        sampling_rate=30.0,
        animal_index=1,
        subject_name="rat2",
        metadata_key="PoseEstimationRat2",
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        container = metadata["Behavior"]["Pose"]["PoseEstimations"]["PoseEstimationRat2"]
        assert container["name"] == "PoseEstimationRat2"
        skeleton = metadata["Behavior"]["Pose"]["Skeletons"]["PoseEstimationRat2"]
        assert skeleton["subject"] == "rat2"

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import MultiCameraPoseEstimation

        with NWBHDF5IO(path=nwbfile_path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            pe = nwbfile.processing["behavior"].data_interfaces["PoseEstimationRat2"]
            assert isinstance(pe, MultiCameraPoseEstimation)
            assert len(pe.pose_estimation_series) == 23
            for series in pe.pose_estimation_series.values():
                assert series.data.shape == (200, 3)
