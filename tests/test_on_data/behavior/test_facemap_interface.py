import numpy as np
from numpy.testing import assert_array_equal
from pynwb import read_nwb
from pynwb.behavior import EyeTracking, PupilTracking

from neuroconv.datainterfaces import FacemapInterface
from neuroconv.tools.testing.data_interface_mixins import (
    DataInterfaceTestMixin,
    TemporalAlignmentMixin,
)

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH, OUTPUT_PATH

FACEMAP_DATA_PATH = BEHAVIOR_DATA_PATH / "facemap" / "motion_svd" / "matlab_gui"
FIRST_N_COMPONENTS = 3


class FacemapInterfaceMixin(DataInterfaceTestMixin, TemporalAlignmentMixin):
    """Checks shared by the two containers a Facemap MATLAB-GUI file is written in.

    Both fixtures are the same session, so every number below holds for both and a
    difference between them is a bug in the reader rather than in the data.
    """

    data_interface_cls = FacemapInterface
    conversion_options = dict(first_n_components=FIRST_N_COMPONENTS)
    save_directory = OUTPUT_PATH

    eye_com_expected_metadata = dict(
        name="eye_center_of_mass",
        description="The position of the eye measured in degrees.",
        reference_frame="unknown",
        unit="degrees",
    )
    pupil_area_expected_metadata = dict(name="pupil_area", description="Area of pupil.", unit="unknown")
    pupil_area_raw_expected_metadata = dict(
        name="pupil_area_raw", description="Raw unprocessed area of pupil.", unit="unknown"
    )
    motion_masks_expected_metadata = dict(name="MotionSVDMasks", description="Motion masks")
    motion_series_expected_metadata = dict(name="MotionSVDSeries", description="Motion SVD components")

    # Boxes and frame geometry are properties of the session and survive stubbing.
    multivideo_mask_coordinates = [49, 0, 294, 287]
    roi1_mask_coordinates = [147, 112, 279, 240]
    processed_frame_dimension = [295, 288]
    downsampling_factor = 4.0

    def _read_proc(self):
        from neuroconv.datainterfaces.behavior.facemap.facemapdatainterface import (
            _ProcFile,
        )

        with _ProcFile(self.interface_kwargs["mat_file_path"]) as proc:
            return dict(
                com=proc.pupil("com"),
                area=proc.pupil("area"),
                area_raw=proc.pupil("area_raw"),
                frames=proc.motion_svd(0).shape[0],
            )

    def check_extracted_metadata(self, metadata: dict):
        behavior = metadata["Behavior"]
        assert behavior["EyeTracking"][0] == self.eye_com_expected_metadata
        assert behavior["PupilTracking"][0] == self.pupil_area_expected_metadata
        assert behavior["PupilTracking"][1] == self.pupil_area_raw_expected_metadata
        assert behavior["MotionSVDMasks"] == self.motion_masks_expected_metadata
        assert behavior["MotionSVDSeries"] == self.motion_series_expected_metadata

    def check_read_nwb(self, nwbfile_path: str):
        from ndx_facemap_motionsvd import MotionSVDMasks, MotionSVDSeries

        expected = self._read_proc()

        nwbfile = read_nwb(nwbfile_path)
        try:
            assert "behavior" in nwbfile.processing
            containers = nwbfile.processing["behavior"].data_interfaces

            eye_tracking = containers["EyeTracking"]
            assert isinstance(eye_tracking, EyeTracking)
            assert_array_equal(eye_tracking.spatial_series["eye_center_of_mass"].data[:], expected["com"])

            pupil_tracking = containers["PupilTracking"]
            assert isinstance(pupil_tracking, PupilTracking)
            assert_array_equal(pupil_tracking.time_series["pupil_area"].data[:], expected["area"])
            assert_array_equal(pupil_tracking.time_series["pupil_area_raw"].data[:], expected["area_raw"])

            for name, mask_coordinates in (
                ("Multivideo", self.multivideo_mask_coordinates),
                ("ROI1", self.roi1_mask_coordinates),
            ):
                masks = containers[f"MotionSVDMasks{name}"]
                assert isinstance(masks, MotionSVDMasks)
                assert_array_equal(masks.mask_coordinates[:], mask_coordinates)
                assert_array_equal(masks.processed_frame_dimension[:], self.processed_frame_dimension)
                assert masks.downsampling_factor == self.downsampling_factor
                assert masks["image_mask"].shape[0] == FIRST_N_COMPONENTS

                series = containers[f"MotionSVDSeries{name}"]
                assert isinstance(series, MotionSVDSeries)
                assert series.data.shape == (expected["frames"], FIRST_N_COMPONENTS)
        finally:
            nwbfile.read_io.close()


class TestFacemapInterfaceHDF5Container(FacemapInterfaceMixin):
    """The container `saveROI.m` writes: `save(savepath, '-v7.3', 'proc')`."""

    interface_kwargs = dict(
        mat_file_path=str(
            FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5" / "11222019_grabAM05_spont_proc.mat"
        ),
        video_file_path=str(
            FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5" / "11222019_grabAM05_spont.avi"
        ),
    )


class TestFacemapInterfaceMatlab5Container(FacemapInterfaceMixin):
    """The same session resaved as plain MATLAB 5.0, which h5py cannot open."""

    interface_kwargs = dict(
        mat_file_path=str(
            FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_matlab5" / "11222019_grabAM05_spont_proc.mat"
        ),
        video_file_path=str(
            FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_matlab5" / "11222019_grabAM05_spont.avi"
        ),
    )


def test_pupil_only_file_has_no_motion_svd(tmp_path):
    """A run with a pupil ROI and no motion SVD must still convert.

    Facemap writes `motSVD`, `uMotMask`, `avgmot`, `avgframe` and `avgmotion`
    whether or not an SVD was computed, leaving them empty when it was not, so the
    presence of those keys says nothing about whether they hold data.

    This fixture ships without its video, which is not public, so the timestamps
    are supplied directly. The video handed to the constructor is never read once
    `set_aligned_timestamps` has been called.
    """
    from pynwb.testing.mock.file import mock_NWBFile

    mat_file_path = FACEMAP_DATA_PATH / "pupil_only" / "single_video_hdf5" / "face_video_proc.mat"
    video_file_path = (
        FACEMAP_DATA_PATH / "whole_frame_and_one_roi" / "single_video_hdf5" / "11222019_grabAM05_spont.avi"
    )

    interface = FacemapInterface(mat_file_path=str(mat_file_path), video_file_path=str(video_file_path), verbose=False)
    interface.set_aligned_timestamps(np.arange(100) / 30.0)

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=interface.get_metadata())

    containers = nwbfile.processing["behavior"].data_interfaces
    assert isinstance(containers["EyeTracking"], EyeTracking)
    assert isinstance(containers["PupilTracking"], PupilTracking)
    assert not [name for name in containers if name.startswith("MotionSVD")]
