from datetime import datetime

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import OptiTrackInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

OPTITRACK_DATA_PATH = BEHAVIOR_DATA_PATH / "optitrack" / "csv_export"


class _OptiTrackInterfaceTestMixin(DataInterfaceTestMixin):
    """Every object the metadata declares is in the file, of the type and name the metadata says.

    ``PoseEstimationInterfaceTestMixin`` checks ``PoseEstimation`` containers only, and an OptiTrack export
    writes ``MultiCameraPoseEstimation`` containers and the rigid bodies' series instead.
    """

    expected_temporal_alignment_keys = ("optitrack",)

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_pose import MultiCameraPoseEstimation
        from pynwb.behavior import SpatialSeries

        metadata = self.interface.get_metadata()
        nwbfile = read_nwb(nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        num_frames = len(self.interface.get_original_timestamps())

        for series_entry in metadata["SpatialSeries"].values():
            series = behavior_module[series_entry["name"]]
            assert isinstance(series, SpatialSeries)
            assert series.data.shape == (num_frames, 3)
            # An export with no length units has no `unit` in its entries and is written with "n.a.".
            assert series.unit == series_entry.get("unit", "n.a.")
        for series_entry in metadata["TimeSeries"].values():
            series = behavior_module[series_entry["name"]]
            assert series.data.shape[0] == num_frames
            assert series.unit == series_entry.get("unit", "n.a.")
        for container_metadata_key, container_entry in metadata["Pose"]["MultiCameraPoseEstimations"].items():
            container = behavior_module[container_entry["name"]]
            assert isinstance(container, MultiCameraPoseEstimation)
            skeleton_entry = metadata["Pose"]["Skeletons"][container_entry["skeleton_metadata_key"]]
            assert list(container.skeleton.nodes[:]) == skeleton_entry["nodes"]
            for series_entry in container_entry["PoseEstimationSeries"].values():
                assert container.pose_estimation_series[series_entry["name"]].data.shape == (num_frames, 3)
        nwbfile.read_io.close()


class TestOptiTrackInterfaceRigidBody(_OptiTrackInterfaceTestMixin):
    """A take with one rigid body, with YXZ Euler angles."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(
            OPTITRACK_DATA_PATH / "version_1_23" / "euler_angles_yxz_meters" / "Take 2023-03-15 08.25.25 AM.csv"
        )
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 3, 15, 8, 25, 25, 277000)

        position_entry = metadata["SpatialSeries"]["optitrack_rigid_body"]
        assert position_entry["name"] == "PositionRigidBody"
        assert position_entry["unit"] == "meters"
        assert position_entry["description"] == (
            "Position (x, y, z) of the pivot point of Rigid Body 'RigidBody', by default its markers' centroid."
        )

        orientation_entry = metadata["TimeSeries"]["optitrack_rigid_body_orientation"]
        assert orientation_entry["name"] == "OrientationRigidBody"
        assert orientation_entry["unit"] == "degrees"
        assert orientation_entry["description"] == (
            "Orientation of Rigid Body 'RigidBody' as intrinsic Euler angles in degrees (x, y, z), applied in "
            "Motive's YXZ rotation order, relative to the room axes, with zero at its pose when it was created "
            "(or last reset) in Motive."
        )

        # This export has no mean marker error column.
        assert list(metadata["TimeSeries"]) == ["optitrack_rigid_body_orientation"]

        # A rigid body is one object, so it is not written as pose estimation.
        assert not metadata["Pose"]["MultiCameraPoseEstimations"]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        position = behavior_module["PositionRigidBody"]
        assert position.rate == 120.0
        assert position.starting_time == 0.0
        # Frame 0 of the source, position X, Y, Z.
        assert_array_equal(position.data[0], [0.602826, 0.040212, 0.051992])
        # Frame 0 of the source, whose rotation columns are in the YXZ rotation order (179.202805, 1.807195,
        # -6.652088), written X, Y, Z.
        assert_array_equal(behavior_module["OrientationRigidBody"].data[0], [1.807195, 179.202805, -6.652088])
        nwbfile.read_io.close()


class TestOptiTrackInterfaceRigidBodiesWithMarkers(_OptiTrackInterfaceTestMixin):
    """A take with two rigid bodies, quaternions, their marker constraints, labeled and unlabeled markers."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(file_path=str(OPTITRACK_DATA_PATH / "version_1_23" / "quaternions_meters" / "block 2.csv"))
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert list(metadata["SpatialSeries"]) == ["optitrack_transmitter", "optitrack_reciver"]
        orientation_entry = metadata["TimeSeries"]["optitrack_transmitter_orientation"]
        assert orientation_entry["name"] == "OrientationTransmitter"
        assert orientation_entry["unit"] == "n.a."
        assert orientation_entry["description"].startswith(
            "Orientation of Rigid Body 'transmitter' as a unit quaternion in the Hamilton convention, scalar first"
        )

        error_entry = metadata["TimeSeries"]["optitrack_transmitter_mean_marker_error"]
        assert error_entry["name"] == "MeanMarkerErrorTransmitter"
        assert error_entry["unit"] == "meters"

        # The labeled markers of each rigid body are measured, so they are written, one container per owner. The
        # eight unlabeled markers are left out.
        containers_metadata = metadata["Pose"]["MultiCameraPoseEstimations"]
        assert list(containers_metadata) == ["optitrack_reciver", "optitrack_transmitter"]
        assert containers_metadata["optitrack_transmitter"]["name"] == "PoseEstimationTransmitter"
        assert list(containers_metadata["optitrack_transmitter"]["PoseEstimationSeries"]) == [
            "Marker1",
            "Marker2",
            "Marker3",
        ]
        assert metadata["Pose"]["Skeletons"]["optitrack_reciver"]["nodes"] == [
            "Marker1",
            "Marker2",
            "Marker3",
            "Marker4",
        ]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        # Frame 0 of the source, scalar first.
        assert_array_equal(
            behavior_module["OrientationTransmitter"].data[0], [0.999915, -0.004526, -0.011383, -0.004363]
        )
        # The measured `Marker` position, not the `Rigid Body Marker` position Motive computes, (1.332051, ...).
        series = behavior_module["PoseEstimationTransmitter"].pose_estimation_series["PoseEstimationSeriesMarker1"]
        assert_array_equal(series.data[0], [1.331559, 0.342979, 0.112971])
        # `reciver` is untracked, its cells empty, in 57 of the 100 frames, in its position and its orientation.
        assert np.isnan(behavior_module["PositionReciver"].data[:]).all(axis=1).sum() == 57
        assert np.isnan(behavior_module["OrientationReciver"].data[:]).all(axis=1).sum() == 57
        # Frame 0 of the source's `Mean Marker Error` column.
        assert behavior_module["MeanMarkerErrorTransmitter"].data[0] == 0.001009
        assert np.isnan(behavior_module["MeanMarkerErrorReciver"].data[:]).sum() == 57
        nwbfile.read_io.close()


@pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
class TestOptiTrackInterfaceSkeleton(_OptiTrackInterfaceTestMixin):
    """A take with one skeleton, its bones and its labeled markers."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(OPTITRACK_DATA_PATH / "version_1_24" / "euler_angles_xyz_meters" / "PID 5 LIGHT EXPECTED.csv")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert not metadata["SpatialSeries"]
        containers_metadata = metadata["Pose"]["MultiCameraPoseEstimations"]
        assert list(containers_metadata) == ["optitrack_skeleton_001"]
        assert containers_metadata["optitrack_skeleton_001"]["name"] == "PoseEstimationSkeleton001"
        nodes = metadata["Pose"]["Skeletons"]["optitrack_skeleton_001"]["nodes"]
        # Nine bones, the first the skeleton's root, named after the skeleton, then 19 of the 24 labeled markers:
        # five are never tracked.
        assert nodes[:3] == ["Skeleton 001", "LThigh", "LShin"]
        assert len(nodes) == 28
        series_entry = containers_metadata["optitrack_skeleton_001"]["PoseEstimationSeries"]["LThigh"]
        assert series_entry["description"] == "Position (x, y, z) of Bone 'Skeleton 001:LThigh'."

        # One orientation per bone, and none for the markers.
        assert len(metadata["TimeSeries"]) == 9
        orientation_entry = metadata["TimeSeries"]["optitrack_skeleton_001_l_thigh_orientation"]
        assert orientation_entry["name"] == "OrientationSkeleton001LThigh"
        assert orientation_entry["unit"] == "degrees"
        assert orientation_entry["description"].startswith(
            "Orientation of Bone 'Skeleton 001:LThigh' as intrinsic Euler angles"
        )

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        container = behavior_module["PoseEstimationSkeleton001"]
        assert container.pose_estimations is None or len(container.pose_estimations) == 0
        series = container.pose_estimation_series["PoseEstimationSeriesLThigh"]
        assert_array_equal(series.data[0], [-1.847731, 0.667991, -2.143483])
        # Frame 0 of the source, rotation X, Y, Z.
        assert_array_equal(behavior_module["OrientationSkeleton001LThigh"].data[0], [-64.154465, -3.826637, 20.860161])
        nwbfile.read_io.close()


@pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
@pytest.mark.filterwarnings("ignore:Could not parse 'Capture Start Time':UserWarning")
class TestOptiTrackInterfaceMarkerSets(_OptiTrackInterfaceTestMixin):
    """A take with six marker sets: a cellist, their bow and cello, a clapperboard, a stand and a table."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(OPTITRACK_DATA_PATH / "version_1_23" / "euler_angles_xyz_meters" / "P1_1.csv")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        containers_metadata = metadata["Pose"]["MultiCameraPoseEstimations"]
        assert [entry["name"] for entry in containers_metadata.values()] == [
            "PoseEstimationBodyCellist",
            "PoseEstimationBow",
            "PoseEstimationCello",
            "PoseEstimationClapperboard",
            "PoseEstimationStand",
            "PoseEstimationTable",
        ]
        # 18 markers on the cellist, one, `LHip`, never tracked.
        assert len(metadata["Pose"]["Skeletons"]["optitrack_body_cellist"]["nodes"]) == 17


class TestOptiTrackInterfaceFormat1_1RigidBody(_OptiTrackInterfaceTestMixin):
    """A take in format version 1.1, which records no length units, with one rigid body."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(OPTITRACK_DATA_PATH / "version_1_1" / "quaternions_rigid_body" / "test_data.csv")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2016, 2, 4, 19, 20, 44, 718000)
        # No length units in the export, so no `unit` in the metadata; it is filled where the series is built.
        assert "unit" not in metadata["SpatialSeries"]["optitrack_rigid_body_1"]
        assert metadata["TimeSeries"]["optitrack_rigid_body_1_orientation"]["unit"] == "n.a."
        # Named `Error Per Marker` in this format version.
        assert "unit" not in metadata["TimeSeries"]["optitrack_rigid_body_1_mean_marker_error"]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        assert_array_equal(behavior_module["PositionRigidBody1"].data[0], [-1.395789, 0.790427, 0.443426])
        assert_array_equal(behavior_module["OrientationRigidBody1"].data[0], [0.999966, 0.001154, 0.007851, -0.002402])
        assert behavior_module["PositionRigidBody1"].unit == "n.a."
        assert behavior_module["MeanMarkerErrorRigidBody1"].unit == "n.a."
        assert behavior_module["MeanMarkerErrorRigidBody1"].data[0] == 0.000296
        nwbfile.read_io.close()


class TestOptiTrackInterfaceFormat1_1MarkersOnly(_OptiTrackInterfaceTestMixin):
    """A take in format version 1.1 with one labeled marker that belongs to no skeleton or marker set."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(
            OPTITRACK_DATA_PATH / "version_1_1" / "quaternions_markers_only" / "Take 2016-04-06 08.06.07 PM.csv"
        )
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert not metadata["SpatialSeries"]
        container_entry = metadata["Pose"]["MultiCameraPoseEstimations"]["optitrack_markers"]
        assert container_entry["name"] == "PoseEstimationMarkers"
        series_entry = container_entry["PoseEstimationSeries"]["Marker_10302"]
        assert series_entry["description"] == "Position (x, y, z) of Marker 'Marker_10302'."
        assert "unit" not in series_entry

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        container = nwbfile.processing["behavior"]["PoseEstimationMarkers"]
        series = container.pose_estimation_series["PoseEstimationSeriesMarker10302"]
        assert_array_equal(series.data[0], [-3.410486, 1.415261, 3.989416])
        # Without the fill, ndx-pose would write its default unit, pixels.
        assert series.unit == "n.a."
        nwbfile.read_io.close()


class TestOptiTrackInterfaceFormat1_2Markers(_OptiTrackInterfaceTestMixin):
    """A take in format version 1.2 with 20 labeled markers, named by number, that belong to no marker set."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(OPTITRACK_DATA_PATH / "version_1_2" / "quaternions_meters" / "choque mesa algodon.csv")
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 11, 30, 16, 42, 0, 269000)
        containers_metadata = metadata["Pose"]["MultiCameraPoseEstimations"]
        assert list(containers_metadata) == ["optitrack_markers"]
        nodes = metadata["Pose"]["Skeletons"]["optitrack_markers"]["nodes"]
        assert nodes[:3] == ["20", "19", "7"]
        assert len(nodes) == 20
        assert containers_metadata["optitrack_markers"]["PoseEstimationSeries"]["20"]["unit"] == "meters"

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        container = nwbfile.processing["behavior"]["PoseEstimationMarkers"]
        assert_array_equal(
            container.pose_estimation_series["PoseEstimationSeries20"].data[0], [-0.090862, 0.122597, 0.341246]
        )
        nwbfile.read_io.close()


class TestOptiTrackInterfaceCentimeters(_OptiTrackInterfaceTestMixin):
    """A take in centimeters with two rigid bodies, with XYZ Euler angles."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(
            OPTITRACK_DATA_PATH / "version_1_23" / "euler_angles_xyz_centimeters" / "Take 2023-06-14 02.04.57 PM.csv"
        )
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2023, 6, 14, 14, 4, 57, 740000)
        assert list(metadata["SpatialSeries"]) == ["optitrack_spm", "optitrack_cf"]
        assert metadata["SpatialSeries"]["optitrack_cf"]["unit"] == "centimeters"
        assert not metadata["Pose"]["MultiCameraPoseEstimations"]

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        assert_array_equal(behavior_module["PositionCf"].data[0], [141.860336, 7.704064, 236.266907])
        assert_array_equal(behavior_module["OrientationCf"].data[0], [31.581804, 83.743637, -32.609104])
        nwbfile.read_io.close()


@pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
class TestOptiTrackInterfaceFormat1_25(_OptiTrackInterfaceTestMixin):
    """A take in format version 1.25, whose asset header has a sixth row, `Parent`, with five rigid bodies."""

    data_interface_cls = OptiTrackInterface
    interface_kwargs = dict(
        file_path=str(
            OPTITRACK_DATA_PATH / "version_1_25" / "quaternions_millimeters" / "Take 2025-07-16 03.07.31 PM.csv"
        )
    )
    save_directory = OUTPUT_PATH

    def check_extracted_metadata(self, metadata: dict):
        assert metadata["NWBFile"]["session_start_time"] == datetime(2025, 7, 16, 15, 7, 32, 261000)
        # `C1`, `C2` and `C3` are never tracked.
        assert list(metadata["SpatialSeries"]) == ["optitrack_huge_tri1", "optitrack_h1"]
        # The measured markers of `H1`; its `Rigid Body Marker` columns and the unlabeled markers are left out.
        containers_metadata = metadata["Pose"]["MultiCameraPoseEstimations"]
        assert list(containers_metadata) == ["optitrack_h1"]
        assert len(containers_metadata["optitrack_h1"]["PoseEstimationSeries"]) == 6

    def run_custom_checks(self):
        nwbfile = read_nwb(self.nwbfile_path)
        behavior_module = nwbfile.processing["behavior"]
        assert_array_equal(behavior_module["PositionHugeTri1"].data[0], [-28.668865, 176.640991, 54.732651])
        assert_array_equal(behavior_module["OrientationHugeTri1"].data[0], [0.853485, -0.006954, 0.0132, -0.520905])
        series = behavior_module["PoseEstimationH1"].pose_estimation_series["PoseEstimationSeriesMarker001"]
        assert_array_equal(series.data[0], [-259.117096, 818.038208, 119.310852])
        nwbfile.read_io.close()


class TestOptiTrackInterfaceFileVariants:
    """How the interface reads the export layouts and edge cases in the OptiTrack test data."""

    euler_file_path = OPTITRACK_DATA_PATH / "version_1_23" / "euler_angles_xyz_millimeters" / "block 2.csv"
    blank_cells_file_path = (
        OPTITRACK_DATA_PATH / "version_1_21" / "quaternions_meters" / "Take 2022-02-28 10.23.34 AM.csv"
    )
    zeros_file_path = OPTITRACK_DATA_PATH / "edge_cases" / "zeros_instead_of_blanks" / "V4_throw_003.csv"
    format_1_22_file_path = (
        OPTITRACK_DATA_PATH / "version_1_22" / "euler_angles_yxz_meters" / "Take 2023-01-24 09.35.03 AM.csv"
    )
    without_header_file_path = (
        OPTITRACK_DATA_PATH / "without_header" / "quaternions_millimeters" / "Take 2017-02-19 05.39.28 PM_batch.csv"
    )
    localized_file_path = OPTITRACK_DATA_PATH / "edge_cases" / "localized_am_pm_marker" / "test_markers_enabled.csv"
    legacy_file_path = OPTITRACK_DATA_PATH / "legacy_row_typed" / "version_1_1" / "Take 2020-02-06 01.34.46 PM.csv"
    local_coordinates_file_path = (
        OPTITRACK_DATA_PATH / "version_1_25" / "quaternions_meters_local_coordinates" / "Take_001.csv"
    )
    skeleton_file_path = OPTITRACK_DATA_PATH / "version_1_24" / "euler_angles_xyz_meters" / "PID 5 LIGHT EXPECTED.csv"

    def test_millimeters_are_the_unit(self):
        interface = OptiTrackInterface(file_path=self.euler_file_path)
        metadata = interface.get_metadata()
        for series_entry in metadata["SpatialSeries"].values():
            assert series_entry["unit"] == "millimeters"
        for container_entry in metadata["Pose"]["MultiCameraPoseEstimations"].values():
            for series_entry in container_entry["PoseEstimationSeries"].values():
                assert series_entry["unit"] == "millimeters"

    def test_an_asset_never_tracked_is_left_out_with_a_warning(self):
        interface = OptiTrackInterface(file_path=self.blank_cells_file_path)
        with pytest.warns(UserWarning, match="Rigid Body 'RigidBody 2'"):
            rigid_bodies = interface._get_rigid_bodies()
        assert list(rigid_bodies) == ["drone_stein"]

    def test_position_at_the_origin_is_written_as_nan(self):
        """`V4Glider` is at position 0,0,0 in frames 0 to 85, before it was first tracked."""
        interface = OptiTrackInterface(file_path=self.zeros_file_path)
        rigid_body = interface._get_rigid_bodies()["V4Glider"]
        assert np.isnan(rigid_body["position"][:86]).all()
        assert not np.isnan(rigid_body["position"][86:]).any()
        for values in rigid_body["orientation"].values():
            assert np.isnan(values[:86]).all()

    def test_format_1_22_reads_without_a_session_start_time(self):
        """Its `Capture Start Time` is a 1969 date, an overflow that is not read."""
        interface = OptiTrackInterface(file_path=self.format_1_22_file_path)
        assert list(interface._get_rigid_bodies()) == ["RigidBody 01"]
        with pytest.warns(UserWarning, match="Could not parse 'Capture Start Time'"):
            metadata = interface.get_metadata()
        assert "session_start_time" not in metadata["NWBFile"]
        assert len(interface.get_original_timestamps()) == 1000

    def test_export_without_header_raises(self):
        """An export with 'Header information' turned off holds only the frame rows, so there are no asset names,
        units, rotation type or rate to read the columns by."""
        with pytest.raises(ValueError, match="exported with 'Header information' turned off"):
            OptiTrackInterface(file_path=self.without_header_file_path)

    def test_localized_am_pm_marker_is_not_read(self):
        """Its `Capture Start Time` ends in a localized marker, `DU.`, where Motive in English writes `PM`."""
        interface = OptiTrackInterface(file_path=self.localized_file_path)
        with pytest.warns(UserWarning, match=r"Could not parse 'Capture Start Time'.*DU\."):
            assert interface._get_session_start_time() is None

    def test_export_of_unlabeled_markers_only_raises(self):
        """Every marker in this export is unlabeled, so no asset is written."""
        interface = OptiTrackInterface(file_path=self.localized_file_path)
        with pytest.raises(ValueError, match="nothing to write"):
            interface._get_labeled_points()

    def test_row_typed_export_raises(self):
        with pytest.raises(ValueError, match="row-typed layout"):
            OptiTrackInterface(file_path=self.legacy_file_path)

    def test_export_in_local_coordinates_raises(self):
        """Each bone of its skeleton is relative to its parent bone, written as `Offset` instead of `Position`."""
        interface = OptiTrackInterface(file_path=self.local_coordinates_file_path)
        with pytest.raises(ValueError, match="local coordinates"):
            interface.get_metadata()

    def test_metadata_schema_declares_the_series(self):
        """NWB GUIDE builds its metadata forms from the schema."""
        interface = OptiTrackInterface(file_path=self.euler_file_path)
        metadata_schema = interface.get_metadata_schema()
        for registry in ("SpatialSeries", "TimeSeries"):
            series_schema = metadata_schema["properties"][registry]["additionalProperties"]
            assert series_schema["required"] == ["name", "description"]

    @pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
    def test_metadata_template(self):
        interface = OptiTrackInterface(file_path=self.skeleton_file_path)
        template = interface.get_metadata_template()

        skeleton = template["Pose"]["Skeletons"]["optitrack_skeleton_001"]
        assert skeleton["name"] == "SkeletonSkeleton001"
        assert skeleton["subject"] is None
        container = template["Pose"]["MultiCameraPoseEstimations"]["optitrack_skeleton_001"]
        assert container["name"] == "PoseEstimationSkeleton001"
        assert container["description"] is None
        assert container["source_software"] == "Motive"
        assert container["source_software_version"] is None
        assert list(container["PoseEstimationSeries"]) == skeleton["nodes"]
        for series in container["PoseEstimationSeries"].values():
            assert series["unit"] == "meters"
            assert series["reference_frame"] is None

    @pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
    def test_metadata_template_writes(self):
        """The template, with its reference frames filled, writes a file."""
        interface = OptiTrackInterface(file_path=self.skeleton_file_path)
        template = interface.get_metadata_template()
        container = template["Pose"]["MultiCameraPoseEstimations"]["optitrack_skeleton_001"]
        for series in container["PoseEstimationSeries"].values():
            series.update(reference_frame="Origin at the center of the capture volume.")

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=template)

        pose_estimation = nwbfile.processing["behavior"]["PoseEstimationSkeleton001"]
        for series in pose_estimation.pose_estimation_series.values():
            assert series.reference_frame == "Origin at the center of the capture volume."

    @pytest.mark.filterwarnings("ignore:Not tracked in any frame:UserWarning")
    def test_deleting_an_entry_leaves_the_object_out(self):
        interface = OptiTrackInterface(file_path=self.skeleton_file_path)
        metadata = interface.get_metadata()
        del metadata["Pose"]["MultiCameraPoseEstimations"]["optitrack_skeleton_001"]
        del metadata["TimeSeries"]["optitrack_skeleton_001_l_thigh_orientation"]

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

        data_interfaces = nwbfile.processing["behavior"].data_interfaces
        assert "PoseEstimationSkeleton001" not in data_interfaces
        assert "OrientationSkeleton001LThigh" not in data_interfaces
        assert len(data_interfaces) == 8
