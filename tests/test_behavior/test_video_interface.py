from datetime import datetime

import numpy as np
import pytest
from dateutil.tz import gettz
from pynwb import NWBHDF5IO

from neuroconv import NWBConverter
from neuroconv.datainterfaces import VideoInterface


@pytest.fixture
def nwb_converter(video_files):
    """Create and return a test NWBConverter instance for external interface tests."""

    class VideoTestNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Video1=VideoInterface,
            Video2=VideoInterface,
        )

    source_data = dict(
        Video1=dict(
            file_paths=video_files[0:2],
            metadata_key_name="Video1",
        ),
        Video2=dict(
            file_paths=[video_files[2]],
            metadata_key_name="Video2",
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
    return tmp_path_session / "video_test.nwb"


@pytest.fixture
def aligned_segment_starting_times():
    """Return aligned segment starting times for tests."""
    return [0.0, 50.0]


# Tests for External Video Interface
def test_video_external_mode_multiple_file_paths_error(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when multiple file paths are provided without timing information."""
    conversion_opts = dict(
        Video1=dict(external_mode=True, starting_frames=[0, 4]),
        Video2=dict(external_mode=True),
    )
    with pytest.raises(ValueError, match="No timing information is specified and there are 2 total video files!"):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=conversion_opts,
            metadata=metadata,
        )


def test_video_external_mode(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times, video_files):
    """Test that external mode works correctly with timestamps."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    conversion_options = dict(Video1=dict(external_mode=True, starting_frames=[0, 4]))
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


def test_video_irregular_timestamps(nwb_converter, nwbfile_path, metadata, aligned_segment_starting_times):
    """Test that irregular timestamps are handled correctly."""
    aligned_timestamps = [np.array([1.0, 2.0, 4.0]), np.array([5.0, 6.0, 7.0])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=aligned_segment_starting_times)

    conversion_options = dict(Video1=dict(external_mode=True, starting_frames=[0, 4]))
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
            conversion_options=dict(Video1=dict(external_mode=True)),
            metadata=metadata,
        )


def test_starting_frames_value_error(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when the length of starting_frames doesn't match the number of file paths."""
    timestamps = [np.array([2.2, 2.4, 2.6]), np.array([3.2, 3.4, 3.6])]
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=timestamps)

    with pytest.raises(
        ValueError,
        match="Multiple paths .2. were specified for the ImageSeries, but the length of starting_frames .1. did not match the number of paths!",
    ):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            conversion_options=dict(Video1=dict(external_mode=True, starting_frames=[0])),
            metadata=metadata,
        )


# Fixtures for Internal Video Interface tests
@pytest.fixture
def internal_nwb_converter(video_files):
    """Create and return a test NWBConverter instance for internal interface tests."""

    class VideoTestNWBConverter(NWBConverter):
        data_interface_classes = dict(
            Video1=VideoInterface,
            Video2=VideoInterface,
        )

    source_data = dict(
        Video1=dict(
            file_paths=[video_files[0]],
            metadata_key_name="Video1",
        ),
        Video2=dict(
            file_paths=[video_files[2]],
            metadata_key_name="Video2",
        ),
    )
    return VideoTestNWBConverter(source_data=source_data)


@pytest.fixture
def internal_metadata(internal_nwb_converter):
    """Get and return metadata for the internal test converter."""
    metadata = internal_nwb_converter.get_metadata()
    metadata["NWBFile"].update(session_start_time=datetime.now(tz=gettz(name="US/Pacific")))
    return metadata


# Tests for Internal Video Interface
def test_save_video_to_custom_module_internal(internal_nwb_converter, nwbfile_path, internal_metadata):
    """Test that videos can be added to a custom module."""
    module_name = "behavior"
    module_description = "This is a test module."
    conversion_opts = dict(
        Video1=dict(
            external_mode=False,
            module_name=module_name,
            module_description=module_description,
        ),
        Video2=dict(
            external_mode=False,
            module_name=module_name,
            module_description=module_description,
        ),
    )
    internal_nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_opts,
        metadata=internal_metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert module_name in nwbfile.processing
        assert module_description == nwbfile.processing[module_name].description


def test_video_chunking_internal(internal_nwb_converter, nwbfile_path, internal_metadata):
    """Test that video chunking works correctly."""
    conversion_options = dict(
        Video1=dict(external_mode=False, stub_test=True, chunk_data=False),
        Video2=dict(external_mode=False, stub_test=True, chunk_data=False),
    )
    internal_nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=internal_metadata,
    )

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        metadata = internal_nwb_converter.get_metadata()
        for video_metadata in metadata["Behavior"]["Video1"]:
            video_interface_name = video_metadata["name"]
            assert mod[video_interface_name].data.chunks is not None  # TODO retrieve storage_layout of hdf5 dataset


def test_video_stub_internal(internal_nwb_converter, nwbfile_path, internal_metadata, aligned_segment_starting_times):
    """Test that stub mode works correctly."""
    aligned_timestamps = [np.array([1, 2, 4, 5, 6, 7, 8, 9, 10, 11])]
    interface = internal_nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)
    interface.set_aligned_segment_starting_times(aligned_segment_starting_times=[aligned_segment_starting_times[0]])

    conversion_options = dict(Video1=dict(external_mode=False, stub_test=True))
    internal_nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=internal_metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        metadata = internal_nwb_converter.get_metadata()
        for video_index in range(len(metadata["Behavior"]["Video1"])):
            video_interface_name = metadata["Behavior"]["Video1"][video_index]["name"]
            assert mod[video_interface_name].data.shape[0] == 10
            assert mod[video_interface_name].timestamps.shape[0] == 10
