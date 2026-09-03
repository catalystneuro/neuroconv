"""Tests for MoseqKeyPointsInterface against keypoint-MoSeq ``results.h5`` files."""

from datetime import datetime

import h5py
import numpy as np
import pytest
from numpy.testing import assert_array_equal
from pydantic import ValidationError
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces import MoseqKeyPointsInterface
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH


def expected_bouts(labels, timestamps, frame_period):
    """Run-length-encode labels into (start_time, stop_time, label) tuples, written out by hand."""
    bouts = []
    run_start = 0
    for frame in range(1, len(labels) + 1):
        if frame == len(labels) or labels[frame] != labels[run_start]:
            bouts.append((timestamps[run_start], timestamps[frame - 1] + frame_period, int(labels[run_start])))
            run_start = frame
    return bouts


class TestMoseqKeyPointsInterfaceTwoDimensional(DataInterfaceTestMixin):
    """A recording from a run on 2D pose, whose centroid is (T, 2).

    Its group names carry the scorer suffix DeepLabCut appended to the file the keypoints came from.
    """

    file_path = str(BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "two_dimensional" / "results.h5")
    recording_name = "21_11_8_one_mouse.top.irDLC_resnet50_moseq_exampleAug21shuffle1_500000"
    sampling_frequency_hz = 30.0

    data_interface_cls = MoseqKeyPointsInterface
    interface_kwargs = dict(
        file_path=file_path,
        recording_name=recording_name,
        sampling_frequency_hz=sampling_frequency_hz,
    )

    def _read_source_dataset(self, dataset_name):
        """Return one dataset of this class's recording, straight out of the source file.

        Read with plain h5py rather than through the interface, so the comparison is not circular.
        """
        with h5py.File(self.file_path, "r") as file:
            return file[self.recording_name][dataset_name][:]

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior = nwbfile.processing["behavior"]

        centroid = behavior["Position"]["MoseqKeyPointsCentroid"]
        assert centroid.data.shape == (700, 2)
        assert_array_equal(centroid.data[:], self._read_source_dataset("centroid"))
        assert centroid.rate == self.sampling_frequency_hz

        heading = behavior["CompassDirection"]["MoseqKeyPointsHeading"]
        assert heading.data.shape == (700,)
        assert heading.unit == "radians"

        latent_state = behavior["MoseqKeyPointsLatentState"]
        assert latent_state.data.shape == (700, 4)

        bouts = behavior["MoseqKeyPointsEthogramBouts"]
        assert bouts.labeling_method == "automated"
        assert bouts.source_software == "keypoint-MoSeq"
        assert behavior["MoseqKeyPointsEthogram"] is not None


class TestMoseqKeyPointsInterfaceThreeDimensional(DataInterfaceTestMixin):
    """A recording from a run on 3D pose, whose centroid is (T, 3) in a different coordinate space.

    Its group names are bare, since the keypoints came from a plain coordinates file.
    """

    file_path = str(BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5")
    recording_name = "21_11_8_one_mouse"
    sampling_frequency_hz = 30.0

    data_interface_cls = MoseqKeyPointsInterface
    interface_kwargs = dict(
        file_path=file_path,
        recording_name=recording_name,
        sampling_frequency_hz=sampling_frequency_hz,
    )

    def _read_source_dataset(self, dataset_name):
        """Return one dataset of this class's recording, straight out of the source file.

        Read with plain h5py rather than through the interface, so the comparison is not circular.
        """
        with h5py.File(self.file_path, "r") as file:
            return file[self.recording_name][dataset_name][:]

    def check_read_nwb(self, nwbfile_path: str):
        nwbfile = read_nwb(nwbfile_path)
        behavior = nwbfile.processing["behavior"]

        centroid = behavior["Position"]["MoseqKeyPointsCentroid"]
        assert centroid.data.shape == (700, 3)
        assert_array_equal(centroid.data[:], self._read_source_dataset("centroid"))


class TestRecordingSelection:
    """One results.h5 holds several recordings, and the interface writes exactly one of them."""

    two_dimensional_file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "two_dimensional" / "results.h5"
    three_dimensional_file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    sampling_frequency_hz = 30.0

    # Group names come from the input filename, so the 2D run carries the scorer suffix DeepLabCut
    # appended to its own file while the 3D run, fitted on a plain coordinates file, does not.
    deeplabcut_suffix = ".top.irDLC_resnet50_moseq_exampleAug21shuffle1_500000"
    two_dimensional_recordings = [
        f"21_11_8_one_mouse{deeplabcut_suffix}",
        f"21_12_10_def6a_1_1{deeplabcut_suffix}",
        f"21_12_10_def6a_3{deeplabcut_suffix}",
    ]
    three_dimensional_recordings = ["21_11_8_one_mouse", "21_12_10_def6a_1_1", "21_12_10_def6a_3"]
    frame_counts = [700, 500, 350]

    def test_lists_recordings_with_the_deeplabcut_suffix(self):
        available = MoseqKeyPointsInterface.get_available_recordings(self.two_dimensional_file_path)
        assert available == self.two_dimensional_recordings

    def test_lists_bare_recording_names(self):
        available = MoseqKeyPointsInterface.get_available_recordings(self.three_dimensional_file_path)
        assert available == self.three_dimensional_recordings

    def test_raises_when_recording_name_is_omitted_and_the_file_holds_several(self):
        with pytest.raises(ValueError, match="holds 3 recordings, so recording_name is required"):
            MoseqKeyPointsInterface(
                file_path=self.two_dimensional_file_path, sampling_frequency_hz=self.sampling_frequency_hz
            )

    def test_raises_on_an_unknown_recording_name(self):
        with pytest.raises(ValueError, match="No recording named 'not_a_recording'"):
            MoseqKeyPointsInterface(
                file_path=self.two_dimensional_file_path,
                recording_name="not_a_recording",
                sampling_frequency_hz=self.sampling_frequency_hz,
            )

    @pytest.mark.parametrize("recording_name, number_of_frames", list(zip(three_dimensional_recordings, frame_counts)))
    def test_each_recording_keeps_its_own_frame_count(self, recording_name, number_of_frames):
        interface = MoseqKeyPointsInterface(
            file_path=self.three_dimensional_file_path,
            recording_name=recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )
        nwbfile = mock_NWBFile(session_start_time=datetime.now().astimezone())
        interface.add_to_nwbfile(nwbfile=nwbfile)

        heading = nwbfile.processing["behavior"]["CompassDirection"]["MoseqKeyPointsHeading"]
        assert heading.data.shape == (number_of_frames,)


class TestTimeBase:
    """keypoint-MoSeq records no time base, so the frame rate has to be supplied."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    recording_name = "21_11_8_one_mouse"

    def test_the_frame_rate_is_required(self):
        with pytest.raises(ValidationError, match="sampling_frequency_hz"):
            MoseqKeyPointsInterface(file_path=self.file_path, recording_name=self.recording_name)

    def test_the_frame_rate_sets_the_rate_of_every_series(self):
        interface = MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=60.0,
        )
        nwbfile = mock_NWBFile(session_start_time=datetime.now().astimezone())
        interface.add_to_nwbfile(nwbfile=nwbfile)

        behavior = nwbfile.processing["behavior"]
        assert behavior["Position"]["MoseqKeyPointsCentroid"].rate == 60.0
        assert behavior["CompassDirection"]["MoseqKeyPointsHeading"].rate == 60.0
        assert behavior["MoseqKeyPointsLatentState"].rate == 60.0


class TestEthogram:
    """The syllable sequence, run-length-encoded into the curated ndx-ethogram product."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    recording_name = "21_11_8_one_mouse"
    sampling_frequency_hz = 30.0

    def _read_source_dataset(self, dataset_name):
        """Return one dataset of this class's recording, straight out of the source file.

        Read with plain h5py rather than through the interface, so the comparison is not circular.
        """
        with h5py.File(self.file_path, "r") as file:
            return file[self.recording_name][dataset_name][:]

    @pytest.fixture
    def written_behavior_module(self):
        interface = MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )
        nwbfile = mock_NWBFile(session_start_time=datetime.now().astimezone())
        interface.add_to_nwbfile(nwbfile=nwbfile)
        return nwbfile.processing["behavior"]

    def test_bouts_are_the_syllables_run_length_encoded(self, written_behavior_module):
        syllables = self._read_source_dataset("syllable")
        timestamps = np.arange(len(syllables)) / self.sampling_frequency_hz
        expected = expected_bouts(syllables, timestamps, 1.0 / self.sampling_frequency_hz)

        bouts = written_behavior_module["MoseqKeyPointsEthogramBouts"].to_dataframe()
        assert len(bouts) == len(expected)
        np.testing.assert_allclose(bouts["start_time"].values, [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"].values, [bout[1] for bout in expected])
        assert list(bouts["label"].values) == [str(bout[2]) for bout in expected]

    def test_the_first_bout_covers_the_padded_frames(self, written_behavior_module):
        # The first three frames of every recording are the model's edge padding, repeated from the
        # first real syllable, so they fall inside the first bout rather than forming one of their own.
        syllables = self._read_source_dataset("syllable")
        bouts = written_behavior_module["MoseqKeyPointsEthogramBouts"].to_dataframe()

        assert bouts["start_time"].values[0] == 0.0
        assert bouts["label"].values[0] == str(syllables[0])
        assert bouts["stop_time"].values[0] > 3 / self.sampling_frequency_hz

    def test_catalogue_holds_the_non_contiguous_ids_present(self, written_behavior_module):
        syllables = self._read_source_dataset("syllable")
        catalogue = written_behavior_module["MoseqKeyPointsEthogram"].to_dataframe()

        # This recording uses 0-6, 8, 9, 11 and 28 of the 100 states the fit was configured with.
        assert list(catalogue["native_code"].values) == [int(value) for value in np.unique(syllables)]
        assert 28 in catalogue["native_code"].values
        assert 7 not in catalogue["native_code"].values

    def test_bouts_link_to_the_latent_trajectory_they_came_from(self, written_behavior_module):
        bouts = written_behavior_module["MoseqKeyPointsEthogramBouts"]
        assert bouts.source is written_behavior_module["MoseqKeyPointsLatentState"]
        assert bouts.ethogram is written_behavior_module["MoseqKeyPointsEthogram"]


class TestCentroidWidthTwoDimensional:
    """The centroid is the only array whose width follows the input pose."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "two_dimensional" / "results.h5"
    recording_name = "21_12_10_def6a_1_1.top.irDLC_resnet50_moseq_exampleAug21shuffle1_500000"
    sampling_frequency_hz = 30.0
    expected_width = 2

    def test_width_is_read_off_the_array(self):
        interface = MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )
        nwbfile = mock_NWBFile(session_start_time=datetime.now().astimezone())
        interface.add_to_nwbfile(nwbfile=nwbfile)

        centroid = nwbfile.processing["behavior"]["Position"]["MoseqKeyPointsCentroid"]
        assert centroid.data.shape == (500, self.expected_width)


class TestCentroidWidthThreeDimensional(TestCentroidWidthTwoDimensional):
    """The same animal fitted on 3D pose, which widens the centroid to three columns."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    recording_name = "21_12_10_def6a_1_1"
    expected_width = 3


class TestMetadata:
    """get_metadata reports what results.h5 records, and nothing it does not."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    recording_name = "21_11_8_one_mouse"
    sampling_frequency_hz = 30.0

    @pytest.fixture
    def interface(self):
        return MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )

    def test_registries_are_keyed_by_the_metadata_key(self, interface):
        metadata = interface.get_metadata()
        moseq_metadata = metadata["Behavior"]["MoseqKeyPoints"]

        assert set(moseq_metadata) == {"Centroids", "Headings", "LatentStates"}
        for registry in moseq_metadata.values():
            assert list(registry) == ["keypoint_moseq"]
        assert list(metadata["Behavior"]["Ethograms"]) == ["keypoint_moseq"]

    def test_centroid_reports_no_unit_or_reference_frame(self, interface):
        centroid_metadata = interface.get_metadata()["Behavior"]["MoseqKeyPoints"]["Centroids"]["keypoint_moseq"]
        assert "unit" not in centroid_metadata
        assert "reference_frame" not in centroid_metadata

    def test_metadata_key_renames_every_entry(self):
        interface = MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
            metadata_key="second_recording",
        )
        metadata = interface.get_metadata()
        assert list(metadata["Behavior"]["MoseqKeyPoints"]["Centroids"]) == ["second_recording"]
        assert list(metadata["Behavior"]["Ethograms"]) == ["second_recording"]


class TestDataToWrite:
    """The conversion option selecting which of the two outputs is written."""

    file_path = BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "three_dimensional" / "results.h5"
    recording_name = "21_11_8_one_mouse"
    sampling_frequency_hz = 30.0

    def build_behavior_module(self, data_to_write):
        interface = MoseqKeyPointsInterface(
            file_path=self.file_path,
            recording_name=self.recording_name,
            sampling_frequency_hz=self.sampling_frequency_hz,
        )
        nwbfile = mock_NWBFile(session_start_time=datetime.now().astimezone())
        interface.add_to_nwbfile(nwbfile=nwbfile, data_to_write=data_to_write)
        return nwbfile.processing["behavior"]

    def test_algorithm_output_writes_the_series_without_the_ethogram(self):
        behavior = self.build_behavior_module("algorithm_output")
        assert set(behavior.data_interfaces) == {"Position", "CompassDirection", "MoseqKeyPointsLatentState"}

    def test_ethogram_writes_the_bouts_without_the_series(self):
        behavior = self.build_behavior_module("ethogram")
        assert set(behavior.data_interfaces) == {"MoseqKeyPointsEthogramBouts", "MoseqKeyPointsEthogram"}

    def test_ethogram_alone_drops_the_source_link(self):
        behavior = self.build_behavior_module("ethogram")
        bouts = behavior["MoseqKeyPointsEthogramBouts"]
        assert bouts.source is None
        assert bouts.ethogram is behavior["MoseqKeyPointsEthogram"]

    def test_both_writes_everything_and_keeps_the_source_link(self):
        behavior = self.build_behavior_module("both")
        assert set(behavior.data_interfaces) == {
            "Position",
            "CompassDirection",
            "MoseqKeyPointsLatentState",
            "MoseqKeyPointsEthogramBouts",
            "MoseqKeyPointsEthogram",
        }
        assert behavior["MoseqKeyPointsEthogramBouts"].source is behavior["MoseqKeyPointsLatentState"]
