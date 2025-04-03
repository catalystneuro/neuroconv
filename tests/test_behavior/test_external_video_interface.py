from copy import deepcopy
from datetime import datetime

import numpy as np
import pytest
from dateutil.tz import gettz
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.video.externalvideointerface import (
    ExternalVideoInterface,
)
from neuroconv.utils import dict_deep_update


def test_initialization_without_metadata(video_files):
    from pynwb.testing.mock.file import mock_NWBFile

    nwbfile = mock_NWBFile()
    interface = ExternalVideoInterface(file_paths=[video_files[0]])

    interface.add_to_nwbfile(nwbfile=nwbfile)


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
            video_name="Video test1",
        ),
        Video2=dict(
            file_paths=[video_files[2]],
            video_name="Video test3",
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


def test_multiple_file_paths_error(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when multiple file paths are provided without timing information."""
    with pytest.raises(ValueError, match="No timing information is specified and there are 2 total video files!"):
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


def test_starting_frames_type_error(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when starting_frames is not provided for multiple file paths."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)

    with pytest.raises(
        TypeError, match="Multiple paths were specified for the ImageSeries, but no starting_frames were specified!"
    ):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
        )


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
        "Behavior": {"ExternalVideos": {"Video test1": {"description": "Custom description", "unit": "CustomUnit"}}}
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
