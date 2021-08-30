"""Authors: Steffen Buergers"""
import os
import dateutil
import numpy as np
from pathlib import Path
from typing import Union

import spikeextractors as se
from pynwb import NWBFile
from pynwb.behavior import Position, SpatialSeries

from ....utils.json_schema import get_schema_from_method_signature, FilePathType
from ....basedatainterface import BaseDataInterface
from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ..baselfpextractorinterface import BaseLFPExtractorInterface
from ....utils.conversion_tools import get_module


# Helper functions for AxonaRecordingExtractorInterface
def parse_generic_header(filename: FilePathType, params: Union[list, set]):
    """
    Given a binary file with phrases and line breaks, enters the
    first word of a phrase as dictionary key and the following
    string (without linebreaks) as value. Returns the dictionary.

    INPUT
    filename (str): .set file path and name.
    params (list or set): parameter names to search for.

    OUTPUT
    header (dict): dictionary with keys being the parameters that
                   were found & values being strings of the data.

    EXAMPLE
    parse_generic_header('myset_file.set', ['experimenter', 'trial_time'])
    """
    header = dict()
    if params is not None:
        params = set(params)
    with open(filename, "rb") as f:
        for bin_line in f:
            if b"data_start" in bin_line:
                break
            line = bin_line.decode("cp1252").replace("\r\n", "").replace("\r", "").strip()
            parts = line.split(" ")
            key = parts[0]
            if params is None or key in params:
                header[key] = " ".join(parts[1:])

    return header


def read_axona_iso_datetime(set_file: FilePathType):
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


class AxonaRecordingExtractorInterface(BaseRecordingExtractorInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor"""

    RX = se.AxonaRecordingExtractor

    def __init__(self, filename: FilePathType):
        super().__init__(filename=filename)

    def get_metadata(self):

        # Extract information for specific parameters from .set file
        params_of_interest = ["experimenter", "comments", "duration", "sw_version"]
        set_file = self.source_data["filename"].split(".")[0] + ".set"
        par = parse_generic_header(set_file, params_of_interest)

        # Extract information from AxonaRecordingExtractor
        elec_group_names = self.recording_extractor.get_channel_groups()
        unique_elec_group_names = set(elec_group_names)

        # Add available metadata
        metadata = super().get_metadata()
        metadata["NWBFile"] = dict(
            session_start_time=read_axona_iso_datetime(set_file),
            session_description=par["comments"],
            experimenter=[par["experimenter"]],
        )

        metadata["Ecephys"] = dict(
            Device=[
                dict(
                    name="Axona",
                    description="Axona DacqUSB, sw_version={}".format(par["sw_version"]),
                    manufacturer="Axona",
                ),
            ],
            ElectrodeGroup=[
                dict(
                    name=f"{group_name}",
                    location="",
                    device="Axona",
                    description=f"Group {group_name} electrodes.",
                )
                for group_name in unique_elec_group_names
            ],
        )

        return metadata


class AxonaUnitRecordingExtractorInterface(AxonaRecordingExtractorInterface):
    """Primary data interface class for converting a AxonaRecordingExtractor"""

    RX = se.AxonaUnitRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        return dict(
            required=["filename"],
            properties=dict(
                filename=dict(
                    type="string",
                    format="file",
                    description="Path to Axona file",
                ),
                noise_std=dict(type="number"),
            ),
            type="object",
        )

    def __init__(self, filename: FilePathType, noise_std: float = 3.5):
        super().__init__(filename=filename)
        self.recording_extractor = se.AxonaUnitRecordingExtractor(filename=filename, noise_std=noise_std)


# Helper functions for AxonaPositionDataInterface
def get_header_bstring(file: FilePathType):
    """
    Scan file for the occurrence of 'data_start' and return the header
    as byte string

    Parameters
    ----------
    file (str or path): file to be loaded

    Returns
    -------
    str: header byte content
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


def read_bin_file_position_data(bin_filename: FilePathType):
    """
    Read position data from Axona `.bin` file (if present).

    Parameters:
    -------
    bin_filename (Path or Str):
        Full filename of Axona file with any extension.

    Returns:
    -------
    np.array
        Columns are time (ms), X, Y, x, y, PX, px, tot_px, unused

    Notes:
    ------
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
        filename=bin_filename,
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
    set_file = bin_filename.split(".")[0] + ".set"
    sr_ecephys = int(parse_generic_header(set_file, ["rawRate"])["rawRate"])

    packets_per_ms = sr_ecephys / 3000
    pos_data[:, 0] = pos_data[:, 0] / packets_per_ms

    # Select only every second sample
    # Note that we do not lowpass filter, since other processing steps done by
    # TINT would no longer work properly.
    pos_data = pos_data[::2]

    return pos_data


def read_pos_file_position_data(pos_filename: FilePathType):
    """
    Read position data from Axona `.pos` file.

    Parameters:
    -------
    pos_filename (Path or Str):
        Full filename of Axona file with any extension.

    Returns:
    -------
    np.array
        Columns are time (ms), X, Y, x, y, PX, px, tot_px, unused
    """

    pos_filename = pos_filename.split(".")[0] + ".pos"

    bytes_packet = 20
    footer_size = len("\r\ndata_end\r\n")
    header_size = len(get_header_bstring(pos_filename))
    num_bytes = os.path.getsize(pos_filename) - header_size - footer_size
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
        filename=pos_filename,
        dtype=pos_dt,
        mode="r",
        offset=len(get_header_bstring(pos_filename)),
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
    set_file = pos_filename.split(".")[0] + ".set"
    dur_ecephys = float(parse_generic_header(set_file, ["duration"])["duration"])

    pos_data = np.hstack(
        (np.linspace(start=0, stop=dur_ecephys * 1000, num=pos_data.shape[0]).astype(int).reshape((-1, 1)), pos_data)
    )

    return pos_data


def get_position_object(filename: FilePathType):
    """
    Read position data from .bin or .pos file and convert to
    pynwb.behavior.SpatialSeries objects. If possible it should always
    be preferred to read position data from the `.bin` file to ensure
    samples are locked to ecephys time courses.

    Parameters:
    ----------
    filename (Path or Str):
        Full filename of Axona file with any extension.

    Returns:
    -------
    position (pynwb.behavior.Position)
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

    if Path(filename).suffix == ".bin":
        position_data = read_bin_file_position_data(filename)
    else:
        position_data = read_pos_file_position_data(filename)

    position_timestamps = position_data[:, 0]

    for ichan in range(0, position_data.shape[1]):

        spatial_series = SpatialSeries(
            name=position_channel_names[ichan],
            timestamps=position_timestamps,
            data=position_data[:, ichan],
            reference_frame="start of raw acquisition (.bin file)",
        )
        position.add_spatial_series(spatial_series)

    return position


class AxonaPositionDataInterface(BaseDataInterface):
    """Primary data interface class for converting Axona position data"""

    @classmethod
    def get_source_schema(cls):
        return get_schema_from_method_signature(cls.__init__)

    def __init__(self, filename: str):
        super().__init__(filename=filename)

    def run_conversion(self, nwbfile: NWBFile, metadata: dict):
        """
        Run conversion for this data interface.

        Parameters
        ----------
        nwbfile : NWBFile
        metadata : dict
        """
        filename = self.source_data["filename"]

        # Create or update processing module for behavioral data
        behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="behavioral data")
        behavior_module.add(get_position_object(filename))


# Helper functions for AxonaLFPDataInterface
def get_eeg_sampling_frequency(filename: FilePathType):
    """
    Read sampling frequency from .eegX or .egfX file header.

    Parameters:
    -----------
    filename : Path or str
        Full filename of Axona `.eegX` or `.egfX` file.

    Returns:
    --------
    Fs : int
        Sampling frequency
    """
    Fs_entry = parse_generic_header(filename, ["sample_rate"])
    Fs = int(float(Fs_entry.get("sample_rate").split(" ")[0]))

    return Fs


def read_eeg_file_lfp_data(filename: FilePathType):
    """
    Read LFP data from Axona `.eegX` or `.egfX` file.

    Parameters:
    -------
    filename (Path or Str):
        Full filename of Axona `.eegX` or `.egfX` file.

    Returns:
    -------
    np.memmap (nobs x 1)
    """

    lfp_dtype = ">i1"
    footer_size = len("\r\ndata_end\r\n")
    header_size = len(get_header_bstring(filename))
    num_bytes = os.path.getsize(filename) - header_size - footer_size

    # .eeg files are int8, .egf files are int16
    if str(filename).split(".")[1][0:3] == "egf":
        lfp_dtype = ">i2"
        num_bytes = num_bytes // 2

    eeg_data = np.memmap(
        filename=filename,
        dtype=lfp_dtype,
        mode="r",
        offset=len(get_header_bstring(filename)),
        shape=(1, num_bytes),
    )

    return eeg_data


def get_all_filenames(filename: FilePathType):
    """
    Read LFP filenames of `.eeg` or `.egf` files in filename's directory.
    E.g. if filename='/my/directory/my_file.eeg', all .eeg channels will be
    appended to the output.

    Parameters:
    -----------
    filename : path-like
        Full filename of either .egg or .egf file

    Returns:
    --------
    path_list : list
        List of filenames
    """

    suffix = Path(filename).suffix[0:4]
    current_path = Path(filename).parent

    path_list = [cur_path.name for cur_path in Path(filename).parent.rglob("*" + suffix + "*")]

    return path_list


def read_all_eeg_file_lfp_data(filename: FilePathType):
    """
    Read LFP data from all Axona `.eeg` or `.egf` files in filename's directory.
    E.g. if filename='/my/directory/my_file.eeg', all .eeg channels will be conactenated
    to a single np.array (chans x nobs). For .egf files substitude the file suffix.

    Parameters:
    -------
    filename (Path or Str):
        Full filename of Axona `.eeg` or `.egf` file.

    Returns:
    -------
    np.array (chans x obs)
    """

    filename_list = get_all_filenames(filename)
    parent_path = Path(filename).parent

    eeg_memmaps = list()
    sampling_rates = set()
    for fname in filename_list:

        sampling_rates.add(get_eeg_sampling_frequency(parent_path / fname))

        eeg_memmaps.append(read_eeg_file_lfp_data(parent_path / fname))

    assert len(sampling_rates) < 2, "File headers specify different sampling rates. Cannot combine EEG data."

    eeg_data = np.concatenate(eeg_memmaps, axis=0)

    return eeg_data


class AxonaLFPDataInterface(BaseLFPExtractorInterface):
    """..."""

    RX = se.AxonaRecordingExtractor

    @classmethod
    def get_source_schema(cls):
        return dict(
            required=["filename"],
            properties=dict(filename=dict(type="string")),
            type="object",
            additionalProperties=False,
        )

    def __init__(self, filename: FilePathType):
        self.recording_extractor = se.NumpyRecordingExtractor(
            timeseries=read_all_eeg_file_lfp_data(filename),
            sampling_frequency=get_eeg_sampling_frequency(filename),
        )
        self.subset_channels = None
        self.source_data = dict(filename=filename)
