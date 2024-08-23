"""Utilities used by the SpikeGLX interfaces."""

import json
from datetime import datetime
from pathlib import Path

from pydantic import FilePath


def add_recording_extractor_properties(recording_extractor) -> None:
    """Utility functions for setting some properties on the recording extractor"""
    probe = recording_extractor.get_probe()
    channel_ids = recording_extractor.get_channel_ids()

    # Should follow pattern 'Imec0', 'Imec1', etc.
    probe_name = recording_extractor.stream_id[:5].capitalize()

    if probe.get_shank_count() > 1:
        shank_ids = probe.shank_ids
        recording_extractor.set_property(key="shank_ids", values=shank_ids)
        group_name = [f"{probe_name}{shank_id}" for shank_id in shank_ids]
    else:
        group_name = [f"{probe_name}"] * len(channel_ids)

    recording_extractor.set_property(key="group_name", ids=channel_ids, values=group_name)

    contact_shapes = probe.contact_shapes  # The geometry of the contact shapes
    recording_extractor.set_property(key="contact_shapes", ids=channel_ids, values=contact_shapes)

    contact_ids = probe.contact_ids  # s{shank_number}e{electrode_number} or e{electrode_number}
    recording_extractor.set_property(key="contact_ids", ids=channel_ids, values=contact_ids)


def get_session_start_time(recording_metadata: dict) -> datetime:
    """
    Fetches the session start time from the recording_metadata dictionary.

    Parameters
    ----------
    recording_metadata : dict
        The metadata dictionary as obtained from the Spikelgx recording.

    Returns
    -------
    datetime or None
        the session start time in datetime format.
    """
    session_start_time = recording_metadata.get("fileCreateTime", None)
    if session_start_time.startswith("0000-00-00"):
        # date was removed. This sometimes happens with human data to protect the
        # anonymity of medical patients.
        return
    if session_start_time:
        session_start_time = datetime.fromisoformat(session_start_time)
    return session_start_time


def fetch_stream_id_for_spikelgx_file(file_path: FilePath) -> str:
    """
    Returns the stream_id for a spikelgx file.

    Example of file name structure:
    Consider the filenames: `Noise4Sam_g0_t0.nidq.bin` or `Noise4Sam_g0_t0.imec0.lf.bin`
    The filenames consist of 3 or 4 parts separated by `.`
      1. "Noise4Sam_g0_t0" will be the `name` variable. This chosen by the user at recording time.
      2. "_gt0_" will give the `seg_index` (here 0)
      3. "nidq" or "imec0" will give the `device` variable
      4. "lf" or "ap" will be the `signal_kind` variable (for nidq the signal kind is an empty string)

    stream_id is the concatenation of `device.signal_kind`

    Parameters
    ----------
    file_path : FilePathType
        The file_path of spikelgx file.

    Returns
    -------
    str
        the stream_id
    """
    suffixes = Path(file_path).suffixes
    device = next(suffix for suffix in suffixes if "imec" in suffix or "nidq" in suffix)
    signal_kind = ""
    if "imec" in device:
        signal_kind = next(suffix for suffix in suffixes if "ap" in suffix or "lf" in suffix)

    stream_id = device[1:] + signal_kind

    return stream_id


def get_device_metadata(meta) -> dict:
    """Returns a device with description including the metadata as described here
    # https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_30.html

    Returns
    -------
    dict
        a dict containing the metadata necessary for creating the device
    """
    # TODO, get probe metadata from spikeinterface
    metadata_dict = dict()
    if "imDatPrb_type" in meta:
        probe_type_to_probe_description = {
            "0": "NP1.0",
            "21": "NP2.0(1-shank)",
            "24": "NP2.0(4-shank)",
            "1030": "NP1.0 NHP",
        }
        probe_type = str(meta["imDatPrb_type"])
        probe_type_description = probe_type_to_probe_description.get(probe_type, "Unknown SpikeGLX probe type.")
        metadata_dict.update(probe_type=probe_type, probe_type_description=probe_type_description)

    if "imDatFx_pn" in meta:
        metadata_dict.update(flex_part_number=meta["imDatFx_pn"])

    if "imDatBsc_pn" in meta:
        metadata_dict.update(connected_base_station_part_number=meta["imDatBsc_pn"])

    description_string = "A Neuropixel probe of unknown subtype."
    if metadata_dict:
        description_string = json.dumps(metadata_dict)
    device_metadata = dict(name="NeuropixelImec", description=description_string, manufacturer="Imec")

    return device_metadata
