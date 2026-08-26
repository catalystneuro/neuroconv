"""What a ``.ppd`` header states about the session, the subject and the timing of its signals."""

from datetime import datetime

from neuroconv.datainterfaces import PyPhotometryFiberPhotometryInterface

try:
    from ..setup_paths import OPHYS_DATA_PATH
except ImportError:
    from setup_paths import OPHYS_DATA_PATH

PYPHOTOMETRY_PATH = OPHYS_DATA_PATH / "fiber_photometry_datasets" / "pyphotometry"
STROBED_FILE_PATH = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "one_colour_time_division.ppd"
CONTINUOUS_FILE_PATH = PYPHOTOMETRY_PATH / "mode_named_in_prose" / "two_colour_continuous.ppd"


def test_session_start_time_comes_from_the_header():
    """Unlike most fiber photometry formats, a ``.ppd`` records when the session started."""
    interface = PyPhotometryFiberPhotometryInterface(file_path=STROBED_FILE_PATH)

    metadata = interface.get_metadata()

    assert metadata["NWBFile"]["session_start_time"] == datetime(2021, 6, 8, 16, 52, 48)


def test_subject_id_comes_from_the_header():
    """The identifier typed into the acquisition GUI, and all a ``.ppd`` says about the animal."""
    interface = PyPhotometryFiberPhotometryInterface(file_path=STROBED_FILE_PATH)

    metadata = interface.get_metadata()

    assert metadata["Subject"]["subject_id"] == "FFC_AF50-202"


def test_strobed_recordings_carry_no_timing_note():
    """The stagger of a strobed recording is exact, so it is in the start time and needs no prose."""
    interface = PyPhotometryFiberPhotometryInterface(file_path=STROBED_FILE_PATH)

    metadata = interface.get_metadata()

    assert "description" not in metadata["FiberPhotometry"][interface.metadata_key]


def test_continuous_recordings_say_why_they_share_the_headers_timebase():
    """The lag is real in a continuous mode but its size is not in the file, so it is said in prose."""
    interface = PyPhotometryFiberPhotometryInterface(file_path=CONTINUOUS_FILE_PATH)

    description = interface.get_metadata()["FiberPhotometry"][interface.metadata_key]["description"]

    assert "sequentially" in description
    assert "213 microseconds" in description
