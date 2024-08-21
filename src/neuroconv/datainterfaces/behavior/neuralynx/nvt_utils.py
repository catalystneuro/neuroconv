"""
Derived from https://www.mathworks.com/matlabcentral/fileexchange/26226-readnvt
"""

import os
from datetime import datetime
from shutil import copy
from typing import Union

import numpy as np
from pydantic import FilePath

HEADER_SIZE = 16 * 1024

RECORD_FORMAT = [
    ("swstx", "uint16"),
    ("swid", "uint16"),
    ("swdata_size", "uint16"),
    ("TimeStamp", "uint64"),
    ("dwPoints", "uint32", 400),
    ("sncrc", "int16"),
    ("Xloc", "int32"),
    ("Yloc", "int32"),
    ("Angle", "int32"),
    ("dntargets", "int32", 50),
]


def read_header(filename: str) -> dict[str, Union[str, datetime, float, int, list[int]]]:
    """
    Parses a Neuralynx NVT File Header and returns it as a dictionary.

    Parameters
    ----------
    filename : str
        Path to the NVT file.

    Returns
    -------
    dict
    """

    def nlx_date_parser(x):
        return datetime.strptime(x, "%Y/%m/%d %H:%M:%S")

    def parse_list_of_ints(x):
        return [int(v) for v in x.split()]

    def parse_bool(x):
        return x.lower() == "true"

    key_parsers = {
        "TimeCreated": nlx_date_parser,
        "TimeClosed": nlx_date_parser,
        "RecordSize": int,
        "IntensityThreshold": parse_list_of_ints,
        "RedThreshold": parse_list_of_ints,
        "GreenThreshold": parse_list_of_ints,
        "BlueThreshold": parse_list_of_ints,
        "Saturation": int,
        "Hue": int,
        "Brightness": int,
        "Contrast": int,
        "Sharpness": int,
        "DirectionOffset": int,
        "Resolution": parse_list_of_ints,
        "CameraDelay": int,
        "EnableFieldEstimation": parse_bool,
        "SamplingFrequency": float,
    }

    with open(filename, "rb") as file:
        out = dict()
        for line, _ in zip(file.readlines(), range(27)):
            line = line.decode()
            if line.startswith("-"):
                key, value = line[1:].split(" ", 1)
                value = value.strip()

                # Use the key-specific parser if available, otherwise use default parsing
                parser = key_parsers.get(key, lambda x: x)
                out[key] = parser(value)
    return out


def read_data(filename: str) -> dict[str, np.ndarray]:
    """
    Reads a NeuroLynx NVT file and returns its data.

    Example usage:
    >>> data = read_data("path_to_your_file.nvt")

    Parameters
    ----------
    filename : str
        Path to the NVT file.

    Returns
    -------
    dict[str, np.ndarray]
        Dictionary containing the parsed data.

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist.
    """

    # Check if file exists
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File {filename} not found.")

    # Reading and parsing data
    with open(filename, "rb") as file:
        file.seek(HEADER_SIZE)
        dtype = np.dtype(RECORD_FORMAT)
        records = np.fromfile(file, dtype=dtype)
        return {name: records[name].squeeze() for name, *_ in RECORD_FORMAT}


def truncate_file(source_filename: FilePath, dest_filename: str, n_records: int = 10) -> None:  # pragma: no cover
    """
    Creates a new .nvt file with the same header and truncated data. Useful for creating
    test files.

    Parameters
    ----------
    source_filename : str
        Path of source .nvt file
    dest_filename : str
        Path of new .nvt file
    n_records : int
        Number of records to keep in the truncated file


    """
    copy(source_filename, dest_filename)

    dtype = np.dtype(RECORD_FORMAT)
    itemsize = dtype.itemsize

    total_size = HEADER_SIZE + itemsize * n_records

    with open(dest_filename, "ab") as file:
        file.truncate(total_size)
