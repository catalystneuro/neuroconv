from pydantic import FilePath

from ....tools import get_package


def extract_timestamps(video_file_path: FilePath) -> list:
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

    with av.open(str(video_file_path)) as container:
        stream = container.streams.video[0]
        timestamps = [frame.time for frame in container.decode(stream)]

    return timestamps
