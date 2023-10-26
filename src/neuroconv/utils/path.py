import re
from pathlib import Path, PureWindowsPath
from typing import Union


def infer_path(path: str) -> Union[PureWindowsPath, Path]:
    """
    Infers and returns the appropriate path object based on the path string.

    Parameters
    ----------
    path : str
        The file path string to be inferred.

    Returns
    -------
    Union[PureWindowsPath, Path]
        Returns a ``PureWindowsPath`` object if the string is in Windows format,
        else returns a ``Path`` object.

    Examples
    --------
    >>> infer_path(r'C:\\Users\\anon\\Desktop\\file.txt')
    PureWindowsPath('C:/Users/anon/Desktop/file.txt')

    >>> infer_path('/Users/anon/Desktop/file.txt')
    PosixPath('/Users/anon/Desktop/file.txt')
    """
    if re.match(r"^[A-Za-z]:\\", path) or "\\" in path:
        return PureWindowsPath(path)
    else:
        return Path(path)
