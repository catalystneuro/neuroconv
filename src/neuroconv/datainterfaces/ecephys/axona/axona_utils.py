import os
from pathlib import Path
from typing import Union

import dateutil
import numpy as np
from pydantic import FilePath
from pynwb.behavior import Position, SpatialSeries


def get_eeg_sampling_frequency(file_path: FilePath) -> float:
    """
    Read sampling frequency from .eegX or .egfX file header.

    Parameters
    ----------
    file_path : Path or str
        Full file_path of Axona `.eegX` or `.egfX` file.

    Returns
    -------
    float
        The sampling frequency in Hz extracted from the file header's sample_rate field.
    """
    Fs_entry = parse_generic_header(file_path, ["sample_rate"])
    Fs = float(Fs_entry.get("sample_rate").split(" ")[0])

    return Fs


# Helper functions for AxonaLFPDataInterface
def read_eeg_file_lfp_data(file_path: FilePath) -> np.memmap:
    """
    Read LFP data from Axona `.eegX` or `.egfX` file.

    Parameters:
    -------
    file_path : FilePath
        Full file_path of Axona `.eegX` or `.egfX` file.

    Returns:
    -------
    np.memmap (nobs x 1)
    """

    lfp_dtype = ">i1"
    footer_size = len("\r\ndata_end\r\n")
    header_size = len(get_header_bstring(file_path))
    num_bytes = os.path.getsize(file_path) - header_size - footer_size

    # .eeg files are int8, .egf files are int16
    if str(file_path).split(".")[1][0:3] == "egf":
        lfp_dtype = ">i2"
        num_bytes = num_bytes // 2
    eeg_data = np.memmap(
        filename=file_path,
        dtype=lfp_dtype,
        mode="r",
        offset=len(get_header_bstring(file_path)),
        shape=(1, num_bytes),
    )

    return eeg_data


def get_all_file_paths(file_path: FilePath) -> list:
    """
    Read LFP file_paths of `.eeg` or `.egf` files in file_path's directory.
    E.g. if file_path='/my/directory/my_file.eeg', all .eeg channels will be
    appended to the output.

    Parameters
    ----------
    file_path : FilePath
        Full file_path of either .egg or .egf file

    Returns
    -------
    list
        List of file paths for all .eeg or .egf files found in the same directory
        as the input file path.
    """

    suffix = Path(file_path).suffix[0:4]
    current_path = Path(file_path).parent

    path_list = [cur_path.name for cur_path in current_path.rglob("*" + suffix + "*")]

    return path_list


def read_all_eeg_file_lfp_data(file_path: FilePath) -> np.ndarray:
    """
    Read LFP data from all Axona `.eeg` or `.egf` files in file_path's directory.
    E.g. if file_path='/my/directory/my_file.eeg', all .eeg channels will be conactenated
    to a single np.array (chans x nobs). For .egf files substitute the file suffix.

    Parameters
    ---------
    file_path FilePath
        Full file_path of Axona `.eeg` or `.egf` file.

    Returns
    -------
    np.array (chans x obs)
    """

    file_path_list = get_all_file_paths(file_path)
    parent_path = Path(file_path).parent

    eeg_memmaps = list()
    sampling_rates = set()
    for fname in file_path_list:
        sampling_rates.add(get_eeg_sampling_frequency(parent_path / fname))

        eeg_memmaps.append(read_eeg_file_lfp_data(parent_path / fname))
    assert len(sampling_rates) < 2, "File headers specify different sampling rates. Cannot combine EEG data."

    eeg_data = np.concatenate(eeg_memmaps, axis=0)

    return eeg_data


# Helper functions for AxonaPositionDataInterface
def parse_generic_header(file_path: FilePath, params: Union[list, set]) -> dict:
    """
    Given a binary file with phrases and line breaks, enters the
    first word of a phrase as dictionary key and the following
    string (without linebreaks) as value. Returns the dictionary.

    Parameters
    ----------
    file_path : FilePath
        Full file_path of Axona `.eeg` or `.egf` file.
    params : list or set
        Parameter names to search for.

    Returns
    -------
    header : dict
        keys are the parameters that were found & values are strings of the data.

    Examples
    --------
    >> parse_generic_header('myset_file.set', ['experimenter', 'trial_time'])
    """
    header = dict()
    if params is not None:
        params = set(params)
    with open(file_path, "rb") as f:
        for bin_line in f:
            if b"data_start" in bin_line:
                break
            line = bin_line.decode("cp1252").replace("\r\n", "").replace("\r", "").strip()
            parts = line.split(" ")
            key = parts[0]
            if params is None or key in params:
                header[key] = " ".join(parts[1:])
    return header


def read_axona_iso_datetime(set_file: FilePath) -> str:
    """
    Creates datetime object (y, m, d, h, m, s) from .set file header
    and converts it to ISO 8601 format
    """
    with open(set_file, "r", encoding="cp1252") as f:
        for line in f:
            if line.startswith("trial_date"):
                date_string = line[len("trial_date") + 1 :].replace("\n", "")
            if line.startswith("trial_time"):
                time_string = line[len("trial_time") + 1 :].replace("\n", "")
    return dateutil.parser.parse(date_string + " " + time_string).isoformat()


def get_header_bstring(file: FilePath) -> bytes:
    """
    Scan file for the occurrence of 'data_start' and return the header
    as byte string

    Parameters
    ----------
    file (str or path) : file to be loaded

    Returns
    -------
    bytes
        The header content as bytes, including everything from the start of the file
        up to and including the 'data_start' marker.
    """
    header = b""
    with open(file, "rb") as f:
        for bin_line in f:
            if b"data_start" in bin_line:
                header += b"data_start"
                break
            else:
                header += bin_line
    return header


def read_bin_file_position_data(bin_file_path: FilePath) -> np.ndarray:
    """
    Read position data from Axona `.bin` file (if present).

    Parameters
    ----------
    bin_file_path : FilePath
        Full file_path of Axona file with any extension.

    Returns
    -------
    np.ndarray
        Columns are time (ms), X, Y, x, y, PX, px, tot_px, unused

    Notes
    -----
    To obtain the correct column order we pairwise flip the 8 int16 columns
    described in the file format manual. In addition, note that `.bin` data is
    little endian (read right to left), as opposed to `.pos` file data, which is
    big endian.
    """
    pos_dt_se = np.dtype(
        [
            ("t", "<i4"),
            ("X", "<i2"),
            ("Y", "<i2"),
            ("x", "<i2"),
            ("y", "<i2"),
            ("PX", "<i2"),
            ("px", "<i2"),
            ("tot_px", "<i2"),
            ("unused", "<i2"),
        ]
    )

    bin_dt = np.dtype(
        [
            ("id", "S4"),
            ("packet", "<i4"),
            ("di", "<i2"),
            ("si", "<i2"),
            ("pos", pos_dt_se),
            ("ephys", np.byte, 384),
            ("trailer", np.byte, 16),
        ]
    )

    np_bin = np.memmap(
        filename=bin_file_path,
        dtype=bin_dt,
        mode="r",
    )

    # Only packets with the ADU2 flag contain position data
    pos_mask = np.where([np_bin["id"] == b"ADU2"])[1]
    pos_data = np_bin["pos"][pos_mask]

    # Rearrange columns of coordinates and pixels to conform with pos data
    # description in file format manual
    pos_data = np.vstack(
        (
            pos_data["Y"],
            pos_data["X"],
            pos_data["y"],
            pos_data["x"],
            pos_data["px"],
            pos_data["PX"],
            pos_data["unused"],
            pos_data["tot_px"],
        )
    ).T

    # Add timestamp as first column
    pos_data = np.hstack((pos_mask.reshape((-1, 1)), pos_data))

    # Create timestamps from position of samples in `.bin` file to ensure
    # alignment with ecephys data
    set_file = bin_file_path.split(".")[0] + ".set"
    sr_ecephys = int(parse_generic_header(set_file, ["rawRate"])["rawRate"])

    packets_per_ms = sr_ecephys / 3000
    pos_data[:, 0] = pos_data[:, 0] / packets_per_ms

    # Select only every second sample
    # Note that we do not lowpass filter, since other processing steps done by
    # TINT would no longer work properly.
    pos_data = pos_data[::2]

    return pos_data


def read_pos_file_position_data(pos_file_path: FilePath) -> np.ndarray:
    """
    Read position data from Axona `.pos` file.

    Parameters
    ----------
    pos_file_path: FilePath
        Full file_path of Axona file with any extension.

    Returns
    -------
    np.ndarray
        Columns are time (ms), X, Y, x, y, PX, px, tot_px, unused
    """

    pos_file_path = pos_file_path.split(".")[0] + ".pos"

    bytes_packet = 20
    footer_size = len("\r\ndata_end\r\n")
    header_size = len(get_header_bstring(pos_file_path))
    num_bytes = os.path.getsize(pos_file_path) - header_size - footer_size
    num_packets = num_bytes // bytes_packet

    pos_dt = np.dtype(
        [
            ("t", ">i4"),
            ("X", ">i2"),
            ("Y", ">i2"),
            ("x", ">i2"),
            ("y", ">i2"),
            ("PX", ">i2"),
            ("px", ">i2"),
            ("tot_px", ">i2"),
            ("unused", ">i2"),
        ]
    )

    pos_data = np.memmap(
        filename=pos_file_path,
        dtype=pos_dt,
        mode="r",
        offset=len(get_header_bstring(pos_file_path)),
        shape=(num_packets,),
    )

    # Convert structured memory mapped array to np array
    pos_data = np.vstack(
        (
            pos_data["X"],
            pos_data["Y"],
            pos_data["x"],
            pos_data["Y"],
            pos_data["PX"],
            pos_data["px"],
            pos_data["tot_px"],
            pos_data["unused"],
        )
    ).T

    # Create time column in ms assuming regularly sampled data starting from 0
    set_file = pos_file_path.split(".")[0] + ".set"
    dur_ecephys = float(parse_generic_header(set_file, ["duration"])["duration"])

    pos_data = np.hstack(
        (np.linspace(start=0, stop=dur_ecephys * 1000, num=pos_data.shape[0]).astype(int).reshape((-1, 1)), pos_data)
    )

    return pos_data


def get_position_object(file_path: FilePath) -> Position:
    """
    Read position data from .bin or .pos file and convert to
    pynwb.behavior.SpatialSeries objects. If possible it should always
    be preferred to read position data from the `.bin` file to ensure
    samples are locked to ecephys time courses.

    Parameters
    ----------
    file_path : Path or str
        Full file_path of Axona file with any extension.

    Returns
    -------
    pynwb.behavior.Position
        Position object containing multiple SpatialSeries, one for each position
        channel (time, X, Y, x, y, PX, px, px_total, unused). Each series contains
        timestamps and corresponding position data. The timestamps are in milliseconds
        and are aligned to the start of raw acquisition if reading from a .bin file.
    """
    position = Position()

    position_channel_names = [
        "time(ms)",
        "X",
        "Y",
        "x",
        "y",
        "PX",
        "px",
        "px_total",
        "unused",
    ]

    if Path(file_path).suffix == ".bin":
        position_data = read_bin_file_position_data(file_path)
    else:
        position_data = read_pos_file_position_data(file_path)
    position_timestamps = position_data[:, 0]

    for ichan in range(position_data.shape[1]):
        spatial_series = SpatialSeries(
            name=position_channel_names[ichan],
            timestamps=position_timestamps,
            data=position_data[:, ichan],
            reference_frame="start of raw acquisition (.bin file)",
        )
        position.add_spatial_series(spatial_series)
    return position
