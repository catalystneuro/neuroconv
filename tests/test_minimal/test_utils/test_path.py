import os.path
from pathlib import Path, PureWindowsPath

from neuroconv.utils.path import infer_path


def test_windows_path():
    win_path = r"C:\Users\anon\Desktop\Data 2 Move\21-48\2023-05-15_10-35-15\VT1.nvt"
    result = infer_path(win_path)
    assert isinstance(result, PureWindowsPath)
    assert result.parts[0] == "C:\\"


def test_unix_path():
    unix_path = "/Users/anon/Desktop/file.txt"
    result = infer_path(unix_path)
    assert isinstance(result, Path)
    assert result.parts[0] == os.path.sep


def test_mixed_path():
    # If a path somehow has both Unix and Windows features, it should default to the system's convention.
    # In this case, backslashes in the string on a Unix system will make it infer a Windows path.
    mixed_path = "/Users/anon\\Desktop\\file.txt"
    result = infer_path(mixed_path)
    assert isinstance(result, PureWindowsPath)
