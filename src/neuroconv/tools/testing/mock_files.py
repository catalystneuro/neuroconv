from pathlib import Path
from typing import Optional


def generate_path_expander_demo_ibl(folder_path: Optional[str] = None) -> None:
    """
    Partially replicate the file structure of IBL data with dummy files for
    experimentation with `LocalPathExpander`. Specifically, it recreates the
    directory tree for the video files of the Steinmetz Lab's data.

    Parameters
    ----------
    folder_path : str, optional
        Path to folder where the files are to be generated.
        If None, the current working directory will be used.
    """
    folder_path = Path(folder_path or Path.cwd())

    with open(Path(__file__).parent / "_path_expander_demo_ibl_filepaths.txt", "r") as video_file_paths:
        for line in video_file_paths.readlines():
            if line.strip():
                video_file_path = folder_path / line.strip()
                video_file_path.parent.mkdir(parents=True, exist_ok=True)  # make directory if needed
                video_file_path.touch()  # make dummy file
