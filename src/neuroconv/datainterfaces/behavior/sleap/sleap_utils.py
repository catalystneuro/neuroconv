from ....tools import get_package
from ....utils import FilePathType


def extract_timestamps(video_file_path: FilePathType) -> list:
    """Extract the timestamps using pyav

    Parameters
    ----------
    video_file_path : FilePathType
        The path to the multimedia video

    Returns
    -------
    list
        The timestamps
    """
    av = get_package(package_name="av")

    container = av.open(str(video_file_path))
    stream = container.streams.video[0]
    timestamps = [frame.time for frame in container.decode(stream)]
    container.close()

    return timestamps
