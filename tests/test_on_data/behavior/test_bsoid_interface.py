"""Tests for BSOiDInterface against the labels files of the B-SOiD app and of bsoid_umap."""

import re
import shutil
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from pynwb import read_nwb
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.datainterfaces import (
    BSOiDInterface,
    DeepLabCutInterface,
    MoseqKeyPointsInterface,
)
from neuroconv.tools.testing.data_interface_mixins import DataInterfaceTestMixin

try:
    from ..setup_paths import BEHAVIOR_DATA_PATH
except ImportError:
    from setup_paths import BEHAVIOR_DATA_PATH

BSOID_PATH = BEHAVIOR_DATA_PATH / "bsoid"
POSE_FILE_STEM = "2019-04-22_12-00-37cut0_30minDeepCut_resnet50_OpenFieldHighResApr8shuffle1_1030000"
APP_1_4_FOLDER = BSOID_PATH / "app" / "version_1_4" / "pose_input_format" / "deeplabcut_csv"
APP_1_5_FOLDER = BSOID_PATH / "app" / "version_1_5" / "pose_input_format"


def expected_bouts(labels, timestamps, frame_period):
    """Run-length-encode labels into (start_time, stop_time, label) tuples, written out by hand."""
    bouts = []
    run_start = 0
    for frame in range(1, len(labels) + 1):
        if frame == len(labels) or labels[frame] != labels[run_start]:
            bouts.append((timestamps[run_start], timestamps[frame - 1] + frame_period, int(labels[run_start])))
            run_start = frame
    return bouts


def read_labels_and_timestamps(file_path, label_rows, frame_index_column, frame_rows, sampling_frequency_hz):
    """Read the labels and the frame times from the rows a test class names, with plain pandas.

    Each class states by hand which rows hold the labels and the frame indices, so the alignment the interface
    infers is checked against one written out for that file.
    """
    table = pd.read_csv(file_path, low_memory=False)
    labels = table["B-SOiD labels"].iloc[label_rows].astype(int).to_numpy()
    frame_indices = table[frame_index_column].iloc[frame_rows].astype(int).to_numpy()
    return labels, frame_indices / sampling_frequency_hz


# The expected numbers of bouts are the row counts of the run-length files B-SOiD wrote beside each labels file
# (`bout_lengths` or `bsoid_runlen`).


class TestBSOiDUmap(DataInterfaceTestMixin):
    """bsoid_umap leaves the label of the two DeepLabCut header rows blank, so the first label is on the first frame."""

    data_interface_cls = BSOiDInterface
    file_path = str(
        BSOID_PATH
        / "bsoid_umap"
        / "pose_input_format"
        / "deeplabcut_csv"
        / f"bsoid_labels_60Hz_20240101_0000{POSE_FILE_STEM}.csv"
    )
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(2, 902)
    frame_index_column = "scorer"
    frame_rows = slice(2, 902)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 60.0
    expected_number_of_bouts = 253
    expected_first_bout_start_time = 0.0
    expected_first_label = "30"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts_table = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"]
        assert bouts_table.bout_concurrency == "partition"
        bouts = bouts_table.to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestBSOiDAppVersion14(DataInterfaceTestMixin):
    """The app of version 1.4 leaves the header rows blank as bsoid_umap does."""

    data_interface_cls = BSOiDInterface
    file_path = str(APP_1_4_FOLDER / "BSOID" / f"labels_pose_60Hz_20261116_1454_{POSE_FILE_STEM}.csv")
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(2, 902)
    frame_index_column = "scorer"
    frame_rows = slice(2, 902)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 60.0
    expected_number_of_bouts = 275
    expected_first_bout_start_time = 0.0
    expected_first_label = "30"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestBSOiDAppVersion15DeepLabCutCsv(DataInterfaceTestMixin):
    """The app of version 1.5 labels the two header rows, so each label sits two rows before its frame."""

    data_interface_cls = BSOiDInterface
    file_path = str(APP_1_5_FOLDER / "deeplabcut_csv" / "BSOID" / f"Jan-01-2024labels_pose_60Hz{POSE_FILE_STEM}.csv")
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(0, 900)
    frame_index_column = "scorer"
    frame_rows = slice(2, 902)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 60.0
    expected_number_of_bouts = 197
    expected_first_bout_start_time = 0.0
    expected_first_label = "28"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestBSOiDAppVersion15DeepLabCutH5(DataInterfaceTestMixin):
    """From a DeepLabCut `.h5` the file has no header rows and the unnamed index holds the frame index."""

    data_interface_cls = BSOiDInterface
    file_path = str(APP_1_5_FOLDER / "deeplabcut_h5" / "BSOID" / f"Jan-01-2024labels_pose_60Hz{POSE_FILE_STEM}.csv")
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(0, 900)
    frame_index_column = "Unnamed: 0"
    frame_rows = slice(0, 900)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 60.0
    expected_number_of_bouts = 288
    expected_first_bout_start_time = 0.0
    expected_first_label = "31"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestBSOiDAppVersion15SleapAnalysisH5(DataInterfaceTestMixin):
    """From a SLEAP analysis `.h5`, with a free-text prefix and frames without pose that still carry a label."""

    data_interface_cls = BSOiDInterface
    file_path = str(
        APP_1_5_FOLDER / "sleap_analysis_h5" / "BSOID" / "epm_sleap_labels_pose_30HzSLEAP_single-mouse_EPM.analysis.csv"
    )
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(0, 1800)
    frame_index_column = "Unnamed: 0"
    frame_rows = slice(0, 1800)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 30.0
    expected_number_of_bouts = 625
    expected_first_bout_start_time = 0.0
    expected_first_label = "0"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestBSOiDFrameIndexFrom300(DataInterfaceTestMixin):
    """A DeepLabCut CSV trimmed before prediction, whose frame index starts at 300, so the first bout starts at 12 s.

    Exported without the run-length file, so the number of bouts is counted from its labels.
    """

    data_interface_cls = BSOiDInterface
    file_path = str(
        BSOID_PATH
        / "app"
        / "version_1_5"
        / "time_structure"
        / "frame_index_from_300"
        / "Feb-22-2023labels_pose_25Hz10_01_A_190507141248DeepCut_resnet50_Blockcourse1May9shuffle1_1030000.csv"
    )
    interface_kwargs = dict(file_path=file_path)
    label_rows = slice(0, 500)
    frame_index_column = "scorer"
    frame_rows = slice(2, 502)

    expected_temporal_alignment_keys = ("bsoid",)
    expected_sampling_frequency_hz = 25.0
    expected_number_of_bouts = 128
    expected_first_bout_start_time = 12.0
    expected_first_label = "4"

    def check_read_nwb(self, nwbfile_path: str):
        labels, timestamps = read_labels_and_timestamps(
            self.file_path,
            self.label_rows,
            self.frame_index_column,
            self.frame_rows,
            self.expected_sampling_frequency_hz,
        )
        expected = expected_bouts(labels, timestamps, 1.0 / self.expected_sampling_frequency_hz)

        bouts = read_nwb(nwbfile_path).processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()
        assert len(bouts) == self.expected_number_of_bouts
        assert bouts["start_time"].iloc[0] == self.expected_first_bout_start_time
        assert bouts["label"].iloc[0] == self.expected_first_label
        np.testing.assert_allclose(bouts["start_time"], [bout[0] for bout in expected])
        np.testing.assert_allclose(bouts["stop_time"], [bout[1] for bout in expected])
        assert list(bouts["label"]) == [str(bout[2]) for bout in expected]


class TestAgreementWithTheBoutLengthsFile:
    """The app writes `bout_lengths` from its labels before padding them, so it locates every bout independently.

    It covers the first 894 of the 900 frames, so every bout but the last has to start on the frame it names.
    """

    def test_app_version_1_5_from_deeplabcut_csv(self):
        folder_path = APP_1_5_FOLDER / "deeplabcut_csv" / "BSOID"
        labels_file_path = folder_path / f"Jan-01-2024labels_pose_60Hz{POSE_FILE_STEM}.csv"
        bout_lengths = pd.read_csv(folder_path / f"Jan-01-2024bout_lengths_60Hz{POSE_FILE_STEM}.csv")
        expected_start_times = bout_lengths["Start time (frames)"].to_numpy()[:-1] / 60.0
        expected_labels = [str(label) for label in bout_lengths["B-SOiD labels"]]

        nwbfile = mock_NWBFile()
        BSOiDInterface(file_path=labels_file_path).add_to_nwbfile(nwbfile=nwbfile)
        bouts = nwbfile.processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()

        np.testing.assert_allclose(bouts["start_time"].to_numpy()[:-1], expected_start_times)
        assert list(bouts["label"]) == expected_labels

    def test_app_version_1_4(self):
        folder_path = APP_1_4_FOLDER / "BSOID"
        labels_file_path = folder_path / f"labels_pose_60Hz_20261116_1454_{POSE_FILE_STEM}.csv"
        bout_lengths = pd.read_csv(folder_path / f"bout_lengths_60Hz_20261116_1454_{POSE_FILE_STEM}.csv")
        expected_start_times = bout_lengths["Start time (frames)"].to_numpy()[:-1] / 60.0
        expected_labels = [str(label) for label in bout_lengths["B-SOiD labels"]]

        nwbfile = mock_NWBFile()
        BSOiDInterface(file_path=labels_file_path).add_to_nwbfile(nwbfile=nwbfile)
        bouts = nwbfile.processing["behavior"]["BSOiDEthogramBouts"].to_dataframe()

        np.testing.assert_allclose(bouts["start_time"].to_numpy()[:-1], expected_start_times)
        assert list(bouts["label"]) == expected_labels


class TestSamplingFrequency:
    """B-SOiD writes the frame rate only into the file name, which depositors sometimes rename."""

    labels_file_path = APP_1_4_FOLDER / "BSOID" / f"labels_pose_60Hz_20261116_1454_{POSE_FILE_STEM}.csv"

    def test_raises_when_a_renamed_file_does_not_carry_the_rate(self, tmp_path):
        renamed_file_path = tmp_path / "labels.csv"
        shutil.copy(self.labels_file_path, renamed_file_path)
        expected_message = (
            "The name of 'labels.csv' does not carry the frame rate B-SOiD writes into it "
            "(`labels_pose_<fps>Hz` or `bsoid_labels_<fps>Hz`), so pass sampling_frequency_hz."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BSOiDInterface(file_path=renamed_file_path)

    def test_the_argument_gives_the_rate_of_a_renamed_file(self, tmp_path):
        renamed_file_path = tmp_path / "labels.csv"
        shutil.copy(self.labels_file_path, renamed_file_path)
        sampling_frequency_hz = 30.0
        expected_second_frame_time = 1 / sampling_frequency_hz

        interface = BSOiDInterface(file_path=renamed_file_path, sampling_frequency_hz=sampling_frequency_hz)

        assert interface.temporal_alignment["bsoid"].get_times()[1] == expected_second_frame_time


class TestFilesThatAreNotLabelsFiles:
    def test_raises_on_the_output_of_the_matlab_code(self):
        file_path = BSOID_PATH / "matlab" / "pose_input_format" / "deeplabcut_csv" / "MsActionGrps.mat"
        expected_message = (
            "'MsActionGrps.mat' is a MATLAB file. BSOiDInterface reads the CSV labels files of the Python versions of "
            "B-SOiD (1.3 and later), not the output of its MATLAB code (versions 1.0 to 1.2). If you need it, please "
            "open an issue at https://github.com/catalystneuro/neuroconv/issues"
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            BSOiDInterface(file_path=file_path)


class TestPoseLink:
    def test_the_bouts_link_to_the_pose_named_in_metadata(self):
        folder_path = APP_1_5_FOLDER / "deeplabcut_csv"
        pose_estimation_metadata_key = "deep_lab_cut_metadata_key"
        pose_interface = DeepLabCutInterface(file_path=folder_path / f"{POSE_FILE_STEM}.csv", sampling_frequency=60.0)
        bsoid_interface = BSOiDInterface(
            file_path=folder_path / "BSOID" / f"Jan-01-2024labels_pose_60Hz{POSE_FILE_STEM}.csv"
        )
        converter = ConverterPipe(data_interfaces=dict(DLC=pose_interface, BSOiD=bsoid_interface))

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2019, 4, 22).astimezone()
        pose_estimation_metadata = metadata["Pose"]["PoseEstimations"][pose_estimation_metadata_key]
        # The body part `Butt/Proximal Tail` would name a series with a slash, which NWB does not allow.
        for series_metadata in pose_estimation_metadata["PoseEstimationSeries"].values():
            series_metadata["name"] = series_metadata["name"].replace("/", "_")
        metadata["Behavior"]["EthogramBouts"]["bsoid"]["source_pose_metadata_key"] = pose_estimation_metadata_key
        expected_pose_estimation_name = pose_estimation_metadata["name"]

        nwbfile = converter.create_nwbfile(metadata=metadata)

        bouts = nwbfile.processing["behavior"]["BSOiDEthogramBouts"]
        assert bouts.source_pose.name == expected_pose_estimation_name


class TestConverterWithAnotherEthogramWriter:
    def test_metadata_of_a_converter_with_keypoint_moseq_validates(self):
        bsoid_interface = BSOiDInterface(
            file_path=APP_1_5_FOLDER / "deeplabcut_csv" / "BSOID" / f"Jan-01-2024labels_pose_60Hz{POSE_FILE_STEM}.csv"
        )
        moseq_interface = MoseqKeyPointsInterface(
            file_path=BEHAVIOR_DATA_PATH / "moseq" / "keypoint_moseq" / "two_dimensional" / "results.h5",
            recording_name="21_11_8_one_mouse.top.irDLC_resnet50_moseq_exampleAug21shuffle1_500000",
            sampling_frequency_hz=30.0,
        )
        converter = ConverterPipe(data_interfaces=dict(BSOiD=bsoid_interface, MoSeq=moseq_interface))

        metadata = converter.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2019, 4, 22).astimezone()

        converter.validate_metadata(metadata=metadata)
