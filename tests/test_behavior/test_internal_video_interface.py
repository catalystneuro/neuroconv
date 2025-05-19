from copy import deepcopy
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from dateutil.tz import gettz
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.video.internalvideointerface import (
    InternalVideoInterface,
)
from neuroconv.utils import dict_deep_update

from .conftest import test_video_parameters


def test_initialization_without_metadata(video_files):

    nwbfile = mock_NWBFile()
    interface = InternalVideoInterface(file_path=video_files[0])

    interface.add_to_nwbfile(nwbfile=nwbfile)


def test_adding_two_videos_without_name(video_files):
    """Test that two interfaces can be added without the user having to specify a different name for each"""

    nwbfile = mock_NWBFile()

    file_path1 = Path(video_files[0])
    file_path2 = Path(video_files[1])
    interface1 = InternalVideoInterface(file_path=file_path1)
    interface2 = InternalVideoInterface(file_path=file_path2)

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
            Video1=InternalVideoInterface,
            Video2=InternalVideoInterface,
        )

    source_data = dict(
        Video1=dict(
            file_path=video_files[0],
            video_name="Video test1",
        ),
        Video2=dict(
            file_path=video_files[1],
            video_name="Video test2",
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
    return tmp_path_session / "internal_video_test.nwb"


@pytest.fixture
def aligned_starting_time():
    """Return aligned starting time for tests."""
    return 10.0


def test_save_video_to_custom_module(nwb_converter, nwbfile_path, metadata):
    """Test that videos can be added to a custom module."""
    module_description = "This is a test module."
    conversion_opts = dict(
        Video1=dict(
            parent_container="processing/behavior",
            module_description=module_description,
        ),
        Video2=dict(
            parent_container="processing/behavior",
            module_description=module_description,
        ),
    )
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_opts,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        assert "behavior" in nwbfile.processing
        assert module_description == nwbfile.processing["behavior"].description
        assert "Video test1" in nwbfile.processing["behavior"].data_interfaces
        assert "Video test2" in nwbfile.processing["behavior"].data_interfaces


def test_video_chunking(nwb_converter, nwbfile_path, metadata):
    """Test that video chunking works correctly."""

    conversion_options = dict(
        Video1=dict(buffer_data=True),
        Video2=dict(buffer_data=False),
    )
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )

    num_frames = test_video_parameters["number_of_frames"]
    num_rows = test_video_parameters["number_of_rows"]
    num_columns = test_video_parameters["number_of_columns"]
    num_channels = test_video_parameters["number_of_channels"]
    expected_video_shape = (num_frames, num_rows, num_columns, num_channels)
    # We chunk each channel separately  and this dataset is small enough that each
    # chunk covers all the frames
    expected_chunking = (num_frames, num_rows, num_columns, 1)

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition

        # Verify that chunking is applied
        video_written_with_iterator = mod["Video test1"]
        assert video_written_with_iterator.data.shape == expected_video_shape  # Chunked data
        assert video_written_with_iterator.data.chunks == expected_chunking  # Chunked data

        video_written_without_iterator = mod["Video test2"]
        assert video_written_without_iterator.data.shape == expected_video_shape
        assert video_written_without_iterator.data.chunks == expected_chunking


def test_video_stub(nwb_converter, nwbfile_path, metadata):
    """Test that stub mode works correctly."""
    conversion_options = dict(Video1=dict(stub_test=True))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        mod = nwbfile.acquisition
        # Verify that stub test limits the frames
        assert mod["Video test1"].data.shape[0] == 10


def test_aligned_timestamps(nwb_converter, nwbfile_path, metadata):
    """Test that aligned timestamps are correctly applied."""
    aligned_timestamps = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 20.0])
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

    conversion_options = dict(Video1=dict(stub_test=True))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        np.testing.assert_array_equal(aligned_timestamps, nwbfile.acquisition["Video test1"].timestamps[:])


def test_always_write_timestamps(nwb_converter, nwbfile_path, metadata):
    """Test that always_write_timestamps forces the use of timestamps even when timestamps are regular."""
    interface = nwb_converter.data_interface_objects["Video1"]
    # Set regular timestamps
    aligned_timestamps = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    interface.set_aligned_timestamps(aligned_timestamps=aligned_timestamps)

    # Run conversion with always_write_timestamps=True
    conversion_options = dict(Video1=dict(stub_test=True, always_write_timestamps=True))
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


def test_aligned_starting_time(nwb_converter, nwbfile_path, metadata, aligned_starting_time):
    """Test that aligned starting time is correctly applied."""
    interface = nwb_converter.data_interface_objects["Video1"]
    interface.set_aligned_starting_time(aligned_starting_time=aligned_starting_time)

    conversion_options = dict(Video1=dict(stub_test=True))
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        conversion_options=conversion_options,
        metadata=metadata,
    )
    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()
        # Verify that starting time is applied
        assert nwbfile.acquisition["Video test1"].starting_time == aligned_starting_time


def test_timestamp_shifting(nwb_converter):
    """Test that timestamps are correctly shifted when setting aligned starting time."""
    interface = nwb_converter.data_interface_objects["Video1"]
    original_timestamps = np.array([1.0, 2.0, 3.0])
    interface.set_aligned_timestamps(aligned_timestamps=original_timestamps)

    # Add a starting time offset
    offset = 5.0
    interface.set_aligned_starting_time(aligned_starting_time=offset)

    # Verify timestamps are shifted
    expected_timestamps = original_timestamps + offset
    np.testing.assert_array_equal(interface.get_timestamps(), expected_timestamps)


def test_set_aligned_timestamps_after_starting_time_error(nwb_converter):
    """Test that setting timestamps after starting time raises an error."""
    interface = nwb_converter.data_interface_objects["Video1"]

    # First set starting time
    interface.set_aligned_starting_time(aligned_starting_time=10.0)

    # Now try to set timestamps - should raise an assertion error
    with pytest.raises(AssertionError):
        interface.set_aligned_timestamps(aligned_timestamps=np.array([1.0, 2.0, 3.0]))


def test_get_original_timestamps_stub(nwb_converter):
    """Test that get_original_timestamps respects stub_test parameter."""
    interface = nwb_converter.data_interface_objects["Video1"]

    # Get stub timestamps
    stub_timestamps = interface.get_original_timestamps(stub_test=True)

    # Get full timestamps
    full_timestamps = interface.get_original_timestamps(stub_test=False)

    # Stub should have exactly 10 timestamps
    assert len(stub_timestamps) == 10
    assert len(full_timestamps) > len(stub_timestamps)


def test_add_to_nwbfile_with_custom_metadata(nwb_converter, nwbfile_path, metadata):
    """Test adding to NWBFile with custom metadata."""
    metadata_copy = deepcopy(metadata)
    custom_metadata = {
        "Behavior": {
            "InternalVideos": {
                "Video test1": {
                    "description": "Custom description",
                    "unit": "CustomUnit",
                    "device": {
                        "name": "CustomDevice",
                        "description": "Custom device description",
                    },
                }
            }
        }
    }
    metadata_copy = dict_deep_update(metadata_copy, custom_metadata)

    conversion_options = dict(Video1=dict(stub_test=True))
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


def test_device_propagation(nwb_converter, nwbfile_path, metadata):
    """Test that devices are properly created and linked to videos."""
    # Run conversion with multiple cameras
    conversion_options = dict(
        Video1=dict(stub_test=True),
        Video2=dict(stub_test=True),
    )
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
        assert "Video test2 Camera Device" in nwbfile.devices

        # Check videos are linked to correct devices
        assert nwbfile.acquisition["Video test1"].device == nwbfile.devices["Video test1 Camera Device"]
        assert nwbfile.acquisition["Video test2"].device == nwbfile.devices["Video test2 Camera Device"]


def test_no_device(nwb_converter, nwbfile_path, metadata):
    """Test that no device is created when the metadata doesn't have a device."""
    metadata["Behavior"]["InternalVideos"]["Video test1"].pop("device")  # Remove device from metadata

    # Run conversion
    nwb_converter.run_conversion(
        nwbfile_path=nwbfile_path,
        overwrite=True,
        metadata=metadata,
    )

    with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
        nwbfile = io.read()

        assert "Video test1 Camera Device" not in nwbfile.devices
        assert nwbfile.acquisition["Video test1"].device is None


def test_invalid_device_metadata(nwb_converter, nwbfile_path, metadata):
    """Test that an error is raised when the device metadata is invalid."""
    # Modify metadata to have invalid device information
    metadata["Behavior"]["InternalVideos"]["Video test1"]["device"] = {"description": "missing required name"}

    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        nwb_converter.run_conversion(
            nwbfile_path=nwbfile_path,
            overwrite=True,
            metadata=metadata,
        )  # Run conversion with modified metadata
