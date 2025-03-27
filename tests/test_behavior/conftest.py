import numpy as np
import pytest


# Common fixtures for all video tests
@pytest.fixture(scope="session")
def tmp_path_session(tmp_path_factory):
    """Create a session-scoped temporary directory."""
    return tmp_path_factory.mktemp("session")


@pytest.fixture(scope="session")
def video_files(tmp_path_session):
    """Create test video files and return their paths."""
    cv2 = pytest.importorskip("cv2")
    video_file1 = str(tmp_path_session / "test1.avi")
    video_file2 = str(tmp_path_session / "test2.avi")
    video_file3 = str(tmp_path_session / "test3.avi")
    number_of_frames = 30
    number_of_rows = 64
    number_of_columns = 48
    frameSize = (number_of_columns, number_of_rows)  # This is give in x,y images coordinates (x is columns)
    fps = 25
    # Standard code for specifying image formats
    fourcc_specification = ("M", "J", "P", "G")
    # Utility to transform the four code specification to OpenCV specification
    fourcc = cv2.VideoWriter_fourcc(*fourcc_specification)

    writer1 = cv2.VideoWriter(
        filename=video_file1,
        fourcc=fourcc,
        fps=fps,
        frameSize=frameSize,
    )
    writer2 = cv2.VideoWriter(
        filename=video_file2,
        fourcc=fourcc,
        fps=fps,
        frameSize=frameSize,
    )
    writer3 = cv2.VideoWriter(
        filename=video_file3,
        fourcc=fourcc,
        fps=fps,
        frameSize=frameSize,
    )

    for frame in range(number_of_frames):
        writer1.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
        writer2.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))
        writer3.write(np.random.randint(0, 255, (number_of_rows, number_of_columns, 3)).astype("uint8"))

    writer1.release()
    writer2.release()
    writer3.release()

    return [video_file1, video_file2, video_file3]
