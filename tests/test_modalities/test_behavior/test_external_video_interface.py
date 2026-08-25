import re
import warnings
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from dateutil.tz import gettz
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.video.externalvideointerface import (
    ExternalVideoInterface,
)
from neuroconv.tools.testing.mock_interfaces import MockExternalVideoInterface
from neuroconv.utils import dict_deep_update


class TestMockExternalVideoInterface:
    """The mock writes what ``ExternalVideoInterface`` writes with no video file behind its paths."""

    def test_writes_without_a_file_on_disk(self, tmp_path):
        """The frame count backing ``num_samples`` comes from the argument rather than from a file."""
        file_path = tmp_path / "never_written.mp4"
        interface = MockExternalVideoInterface(file_paths=[file_path], num_frames=5000, frame_rate=30.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        assert image_series.num_samples == 5000
        assert image_series.rate == 30.0
        assert image_series.starting_time == 0.0
        assert list(image_series.external_file) == [file_path]
        assert not file_path.exists()

    def test_segments_run_consecutively(self):
        """Several paths describe one continuous recording, so the starting frames follow the counts."""
        interface = MockExternalVideoInterface(
            file_paths=["segment1.mp4", "segment2.mp4", "segment3.mp4"], num_frames=10, frame_rate=30.0
        )

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        assert image_series.num_samples == 30
        assert image_series.starting_frame == [0, 10, 20]
        assert image_series.rate == 30.0

    def test_placing_the_files_scans_none_of_them(self):
        """The files are placed on the session clock through the times the mock holds, opening nothing."""
        interface = MockExternalVideoInterface(
            file_paths=["segment1.mp4", "segment2.mp4"], num_frames=4, frame_rate=2.0
        )

        # Untouched, the files read as one gapless recording split in two, while each file's own times
        # start at zero the way the container timestamps of a real video do.
        np.testing.assert_array_equal(
            np.concatenate([interface.alignment[key].get_times() for key in interface.alignment.keys()]),
            np.arange(8) / 2.0,
        )
        for original_timestamps in interface.get_original_timestamps():
            np.testing.assert_array_equal(original_timestamps, np.arange(4) / 2.0)

        for segment_key, starting_time in zip(interface.alignment.keys(), [10.0, 100.0]):
            _place(interface, segment_key, starting_time)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        # The gap between the files makes the series irregular, so the times are written out rather than a rate.
        np.testing.assert_array_equal(image_series.timestamps[:], [10.0, 10.5, 11.0, 11.5, 100.0, 100.5, 101.0, 101.5])
        assert image_series.starting_frame == [0, 4]


class TestExternalVideoAlignment:
    """The alignment surface: one addressable time-bearing object per video file, keyed by file stem."""

    def test_each_file_is_named_by_its_stem(self):
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi", "trial_3.avi"])

        assert interface.alignment.keys() == ("trial_1", "trial_2", "trial_3")

    def test_files_sharing_a_stem_raise(self):
        """The stem is the address, so two files that share one cannot both be reached."""
        with pytest.raises(ValueError, match="These are used more than once"):
            MockExternalVideoInterface(file_paths=["day_1/video.avi", "day_2/video.avi"])

    def test_untouched_files_run_on_from_each_other(self):
        """A recording split in place: each file starts where the one before it ended."""
        interface = MockExternalVideoInterface(file_paths=["part_1.avi", "part_2.avi"], num_frames=4, frame_rate=2.0)

        np.testing.assert_array_equal(interface.alignment["part_1"].get_times(), [0.0, 0.5, 1.0, 1.5])
        np.testing.assert_array_equal(interface.alignment["part_2"].get_times(), [2.0, 2.5, 3.0, 3.5])

    def test_several_files_with_no_times_warn_and_write_contiguously(self):
        """The only reading several files support on their own, taken but not silently."""
        interface = MockExternalVideoInterface(
            file_paths=["trial_1.avi", "trial_2.avi"],
            num_frames=2,
            frame_rate=2.0,
            segment_timing="unset",
        )
        assert not interface.alignment.is_fine_aligned

        nwbfile = mock_NWBFile()
        with pytest.warns(UserWarning, match="as one recording split in place"):
            interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        assert image_series.starting_time == 0.0
        assert image_series.starting_frame == [0, 2]

    @pytest.mark.parametrize("segment_timing", ["contiguous", "gapped"])
    def test_segments_with_times_of_their_own_do_not_warn(self, segment_timing):
        """Times of their own are what the warning asks for, however they were given."""
        interface = MockExternalVideoInterface(
            file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0, segment_timing=segment_timing
        )
        assert interface.alignment.is_fine_aligned

        nwbfile = mock_NWBFile()
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            interface.add_to_nwbfile(nwbfile=nwbfile)

    def test_a_shift_alone_does_not_count_as_setting_the_segments(self, video_files):
        """A shift moves the whole interface at once, so it says nothing about any one segment."""
        interface = ExternalVideoInterface(file_paths=video_files[0:2])
        interface.alignment.shift_times(123.0)

        nwbfile = mock_NWBFile()
        with pytest.warns(UserWarning, match="as one recording split in place"):
            interface.add_to_nwbfile(nwbfile=nwbfile)

    def test_the_warning_names_only_the_segments_without_times(self, video_files):
        """Setting some of them narrows the warning rather than removing it."""
        interface = ExternalVideoInterface(file_paths=video_files[0:2])
        _place(interface, Path(video_files[0]).stem, 0.0)

        nwbfile = mock_NWBFile()
        with pytest.warns(UserWarning, match=Path(video_files[1]).stem):
            interface.add_to_nwbfile(nwbfile=nwbfile)

    def test_files_placed_contiguously_write_a_starting_time_and_a_rate(self, video_files):
        """A recording split in place, put back together from the frame counts and rates."""
        interface = ExternalVideoInterface(file_paths=video_files[0:2])
        _place_contiguously(interface)
        interface.alignment.shift_times(123.0)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        assert image_series.starting_time == 123.0
        assert image_series.num_samples == sum(interface.get_frame_counts())
        # Placed files go through the times array, so the rate is fitted back out of it rather than stated,
        # which costs the last digits. The compact path only survives for a video nothing has re-timed.
        assert image_series.rate == pytest.approx(interface.get_frame_rates()[0])

    def test_starting_times_are_absolute(self):
        """Placement replaces rather than accumulates, which is what the deprecated setter got wrong."""
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0)

        for _ in range(2):
            for segment_key, starting_time in zip(interface.alignment.keys(), [10.0, 100.0]):
                _place(interface, segment_key, starting_time)

        np.testing.assert_array_equal(interface.alignment["trial_1"].get_times(), [10.0, 10.5])
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [100.0, 100.5])

    def test_setting_the_times_of_one_file_leaves_the_others(self):
        """A pulse per frame is set on the file it belongs to."""
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0)
        for segment_key, starting_time in zip(interface.alignment.keys(), [10.0, 100.0]):
            _place(interface, segment_key, starting_time)

        interface.alignment["trial_2"].set_times([100.1, 100.7])

        np.testing.assert_array_equal(interface.alignment["trial_1"].get_times(), [10.0, 10.5])
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [100.1, 100.7])

    def test_shift_moves_every_file(self):
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0)
        for segment_key, starting_time in zip(interface.alignment.keys(), [10.0, 100.0]):
            _place(interface, segment_key, starting_time)

        interface.alignment.shift_times(5.0)

        np.testing.assert_array_equal(interface.alignment["trial_1"].get_times(), [15.0, 15.5])
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [105.0, 105.5])

    def test_a_placement_and_measured_times_supersede_each_other(self):
        """Both say where one file is, so the later call wins rather than the two combining."""
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0)

        _place(interface, "trial_2", 100.0)
        interface.alignment["trial_2"].set_times([100.1, 100.7])
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [100.1, 100.7])

        _place(interface, "trial_2", 50.0)
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [50.0, 50.5])

    def test_overlapping_files_raise_on_write(self):
        """One ImageSeries carries one timeline, so files that run into each other describe no file."""
        interface = MockExternalVideoInterface(
            file_paths=["trial_1.avi", "trial_2.avi"], num_frames=100, frame_rate=30.0
        )
        for segment_key, starting_time in zip(interface.alignment.keys(), [0.0, 1.0]):
            _place(interface, segment_key, starting_time)

        nwbfile = mock_NWBFile()
        with pytest.raises(ValueError, match="do not merge into a single increasing timeline"):
            interface.add_to_nwbfile(nwbfile=nwbfile)

    def test_a_shifted_video_keeps_its_exact_frame_rate(self):
        """Where nothing has re-timed the frames the rate is stated, not fitted back out of the times."""
        interface = MockExternalVideoInterface(file_paths=["session.avi"], num_frames=300, frame_rate=30.0)
        interface.alignment.shift_times(12.5)

        nwbfile = mock_NWBFile()
        interface.add_to_nwbfile(nwbfile=nwbfile)

        image_series = nwbfile.acquisition[interface._default_name]
        assert image_series.starting_time == 12.5
        assert image_series.rate == 30.0
        assert image_series.timestamps is None

    def test_remap_times_moves_every_file(self):
        """A camera clock is one clock, so the correction is not addressed to a single file."""
        interface = MockExternalVideoInterface(file_paths=["trial_1.avi", "trial_2.avi"], num_frames=2, frame_rate=2.0)

        # The camera's own clock runs at half the reference clock's speed.
        interface.alignment.remap_times(local_sync_times=[0.0, 2.0], reference_sync_times=[0.0, 4.0])

        np.testing.assert_array_equal(interface.alignment["trial_1"].get_times(), [0.0, 1.0])
        np.testing.assert_array_equal(interface.alignment["trial_2"].get_times(), [2.0, 3.0])


def _place(interface, segment_key, starting_time):
    """Give one segment the times its onset implies, which is what a caller writes without a lazy setter."""
    file_index = list(interface.alignment.keys()).index(segment_key)
    frame_count = interface.get_frame_counts()[file_index]
    frame_rate = interface.get_frame_rates()[file_index]
    interface.alignment[segment_key].set_times(starting_time + np.arange(frame_count) / frame_rate)


def _place_contiguously(interface):
    """Place every file where the one before it ended, which is what a recording split in place needs."""
    durations = np.array(interface.get_frame_counts()) / np.array(interface.get_frame_rates())
    starting_times = np.concatenate([[0.0], np.cumsum(durations)[:-1]])
    for segment_key, starting_time in zip(interface.alignment.keys(), starting_times):
        _place(interface, segment_key, starting_time)


def test_initialization_without_metadata(video_files):

    nwbfile = mock_NWBFile()
    interface = ExternalVideoInterface(file_paths=[video_files[0]])

    interface.add_to_nwbfile(nwbfile=nwbfile)


def test_adding_two_videos_without_name(video_files):
    """Test that two interfaces can be added without the user having to specify a different name for each"""

    nwbfile = mock_NWBFile()

    file_path1 = Path(video_files[0])
    file_path2 = Path(video_files[1])
    interface1 = ExternalVideoInterface(file_paths=[file_path1])
    interface2 = ExternalVideoInterface(file_paths=[file_path2])

    # This should not raise an error
    interface1.add_to_nwbfile(nwbfile=nwbfile)
    interface2.add_to_nwbfile(nwbfile=nwbfile)

    assert len(nwbfile.acquisition) == 2
    assert f"Video {file_path1.stem}" in nwbfile.acquisition
    assert f"Video {file_path2.stem}" in nwbfile.acquisition


@pytest.fixture
def nwb_converter(video_files):
    """Create and return a test NWBConverter instance."""

    class VideoTestNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Video1=ExternalVideoInterface,
            Video2=ExternalVideoInterface,
        )

    source_data = dict(
        Video1=dict(
            file_paths=video_files[0:2],
            metadata_key="video_test1",
        ),
        Video2=dict(
            file_paths=[video_files[2]],
            metadata_key="video_test3",
        ),
    )
    return VideoTestNWBConverter(source_data=source_data)


@pytest.fixture
def metadata(nwb_converter):
    """Get and return metadata for the test converter."""
    metadata = nwb_converter.get_metadata()
    metadata["NWBFile"].update(session_start_time=datetime.now(tz=gettz(name="US/Pacific")))
    return metadata


@pytest.fixture
def nwbfile_path(tmp_path_session):
    """Return path for the test NWB file."""
    return tmp_path_session / "external_video_test.nwb"


@pytest.fixture
def aligned_segment_starting_times():
    """Return aligned segment starting times for tests."""
    return [0.0, 50.0]


def test_multiple_file_paths_warns(nwb_converter, nwbfile_path, metadata):
    """Test that a warning is raised when multiple file paths are provided without timing information."""
    with pytest.warns(UserWarning, match="as one recording split in place"):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
        )


def test_external_mode_with_timestamps(
    nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times, video_files
):
    """Test that external mode works correctly with timestamps."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        module = nwbfile.acquisition
        assert list(module["Video test1"].external_file[:]) == video_files[0:2]
        assert list(module["Video test3"].external_file[:]) == [video_files[2]]


def test_external_mode_with_starting_time(nwb_converter, nwbfile_path, metadata, video_files):
    """Test that external mode works correctly with starting time."""
    interface = nwb_converter.data_interface_objects["Video1"]
    # Several files have to be placed before a shift can move them; these run on from each other.
    _place_contiguously(interface)
    interface.set_aligned_starting_time(aligned_starting_time=123.0)

    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        module = nwbfile.acquisition
        assert list(module["Video test1"].external_file[:]) == video_files[0:2]
        assert list(module["Video test3"].external_file[:]) == [video_files[2]]
        assert module["Video test1"].starting_time == 123.0


def test_irregular_timestamps(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that irregular timestamps are handled correctly."""
    aligned_timestamps = [np.array([1.0, 2.0, 4.0]), np.array([5.0, 6.0, 7.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )

    expected_timestamps = np.array([1.0, 2.0, 4.0, 55.0, 56.0, 57.0])
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        np.testing.assert_array_equal(expected_timestamps, nwbfile.acquisition["Video test1"].timestamps[:])


def test_starting_frames_computed_from_video_files(nwb_converter, nwbfile_path, metadata):
    """Test that starting_frames is computed from the video frame counts when it is not provided."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)

    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        metadata=metadata,
    )

    number_of_frames_per_file = 30  # Each of the test video files holds 30 frames
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        starting_frame = nwbfile.acquisition["Video test1"].starting_frame
        np.testing.assert_array_equal(starting_frame, [0, number_of_frames_per_file])


def test_starting_frames_value_error(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when the length of starting_frames doesn't match the number of file paths."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)

    conversion_options = dict(Video1=dict(starting_frames=[0]))
    with pytest.raises(
        ValueError,
        match="Multiple paths .2. were specified for the ImageSeries, but the length of starting_frames .1. did not match the number of paths!",
    ):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=metadata,
        )


def test_always_write_timestamps(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that always_write_timestamps forces the use of timestamps even when timestamps are regular."""
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])

    # Run conversion with always_write_timestamps=True
    conversion_options = dict(Video1=dict(starting_frames=[0, 4], always_write_timestamps=True))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )

    # Verify that timestamps were written
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        # Check that timestamps exist in the ImageSeries
        assert nwbfile.acquisition["Video test1"].timestamps is not None
        # Verify timestamps are not None and have the expected length
        assert len(nwbfile.acquisition["Video test1"].timestamps[:]) > 0


def test_custom_module(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that videos can be added to a custom module."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    parent_container = "processing/behavior"
    module_description = "This is a test module."
    conversion_options = dict(
        Video1=dict(
            starting_frames=[0, 4],
            parent_container=parent_container,
            module_description=module_description,
        ),
        Video2=dict(
            parent_container=parent_container,
            module_description=module_description,
        ),
    )
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert "behavior" in nwbfile.processing
        assert module_description == nwbfile.processing["behavior"].description
        assert "Video test1" in nwbfile.processing["behavior"].data_interfaces
        assert "Video test3" in nwbfile.processing["behavior"].data_interfaces


def test_set_aligned_segment_starting_times_alone(nwb_converter):
    """Test that setting segment_starting_times without setting aligned timestamps automatically sets the timestamps."""
    interface = nwb_converter.data_interface_objects["Video1"]

    interface._timestamps = None
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[10.0, 20.0])

    original_timestamps = interface.get_original_timestamps()
    expected_timestamps = [
        timestamps + starting_time for timestamps, starting_time in zip(original_timestamps, [10.0, 20.0])
    ]
    for (
        original,
        expected,
        starting_time,
    ) in zip(original_timestamps, expected_timestamps, [10.0, 20.0]):
        np.testing.assert_array_equal(original + starting_time, expected)


def test_get_original_timestamps_stub(nwb_converter):
    """Test that get_original_timestamps respects stub_test parameter."""
    interface = nwb_converter.data_interface_objects["Video2"]  # Using Video2 which has a single file

    # Get stub timestamps
    stub_timestamps = interface.get_original_timestamps(stub_test=True)

    # Stub should have exactly 10 timestamps in the first array
    assert len(stub_timestamps[0]) == 10

    # Get full timestamps
    full_timestamps = interface.get_original_timestamps(stub_test=False)

    # Full should have more timestamps
    assert len(full_timestamps[0]) > len(stub_timestamps[0])


def test_add_to_nwbfile_with_custom_metadata(nwb_converter, nwbfile_path, metadata):
    """Test adding to NWBFile with custom metadata."""
    metadata_copy = deepcopy(metadata)
    custom_metadata = {
        "Devices": {
            "custom_device": {
                "name": "CustomDevice",
                "description": "Custom device description",
            },
        },
        "Behavior": {
            "ExternalVideos": {
                "video_test1": {
                    "description": "Custom description",
                    "unit": "CustomUnit",
                    "device_metadata_key": "custom_device",
                }
            }
        },
    }
    metadata_copy = dict_deep_update(metadata_copy, custom_metadata)

    # Set up the interface for conversion
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])

    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata_copy,
    )

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert nwbfile.acquisition["Video test1"].description == "Custom description"
        assert nwbfile.acquisition["Video test1"].unit == "CustomUnit"
        assert nwbfile.devices["CustomDevice"].description == "Custom device description"
        assert nwbfile.acquisition["Video test1"].device == nwbfile.devices["CustomDevice"]


def test_device_propagation(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that devices are properly created and linked to videos."""
    # Setup interface with timing information to allow conversion
    timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    # Run conversion with multiple cameras
    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )

    # Verify device creation and linking
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        # Check devices exist
        assert "Video test1 Camera Device" in nwbfile.devices
        assert "Video test3 Camera Device" in nwbfile.devices

        # Check videos are linked to correct devices
        assert nwbfile.acquisition["Video test1"].device == nwbfile.devices["Video test1 Camera Device"]
        assert nwbfile.acquisition["Video test3"].device == nwbfile.devices["Video test3 Camera Device"]


def test_device_model_propagation(nwb_converter, nwbfile_path, metadata):
    """A camera Device that names its model gets that DeviceModel written and linked."""
    custom_metadata = {
        "DeviceModels": {"camera_model": {"name": "CameraModel"}},
        "Devices": {"custom_device": {"name": "CustomDevice", "device_model_metadata_key": "camera_model"}},
        "Behavior": {"ExternalVideos": {"video_test1": {"device_metadata_key": "custom_device"}}},
    }
    metadata_copy = dict_deep_update(deepcopy(metadata), custom_metadata)

    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=[np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])])

    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=dict(Video1=dict(starting_frames=[0, 4])),
        metadata=metadata_copy,
    )

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert nwbfile.acquisition["Video test1"].device.model == nwbfile.device_models["CameraModel"]
        # 'manufacturer' is required by NWB and absent from the metadata, so it is filled at write time
        assert nwbfile.device_models["CameraModel"].manufacturer == "unknown"


def test_no_device(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that no device is created when the metadata doesn't have a device."""
    # Setup interface with timing information to allow conversion
    timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    metadata["Behavior"]["ExternalVideos"]["video_test1"].pop("device_metadata_key")  # Unlink the device

    # Run conversion with multiple cameras
    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()

        assert "Video test1 Camera Device" not in nwbfile.devices
        assert nwbfile.acquisition["Video test1"].device is None


def test_dangling_device_metadata_key_raises(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """A device_metadata_key with no matching Devices entry raises instead of silently dropping the device."""
    timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)
    metadata["Behavior"]["ExternalVideos"]["video_test1"]["device_metadata_key"] = "missing_camera"

    conversion_options = dict(Video1=dict(starting_frames=[0, 4]))
    expected_message = (
        "device_metadata_key 'missing_camera' was not found in metadata['Devices'] "
        "(available keys: ['video_test1_camera', 'video_test3_camera'])."
    )
    with pytest.raises(ValueError, match=re.escape(expected_message)):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_options,
            metadata=metadata,
        )


def test_invalid_device_metadata(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when the device metadata is invalid."""
    # Setup interface with timing information to allow conversion
    timestamps = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)

    # Modify metadata to have invalid device information
    metadata["Behavior"]["ExternalVideos"]["video_test1"]["device"] = {"description": "missing required name"}

    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
        )  # Run conversion with modified metadata
