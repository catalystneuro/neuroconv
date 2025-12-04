"""Utilities used by the SpikeGLX interfaces."""

import json
import warnings
from datetime import datetime


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

    warnings.warn(
        "get_session_start_time is deprecated and will be removed in May 2026 or later.",
        FutureWarning,
        stacklevel=2,
    )

    session_start_time = recording_metadata.get("fileCreateTime", None)
    if session_start_time.startswith("0000-00-00"):
        # date was removed. This sometimes happens with human data to protect the
        # anonymity of medical patients.
        return
    if session_start_time:
        session_start_time = datetime.fromisoformat(session_start_time)
    return session_start_time


def get_device_metadata(meta) -> dict:
    """Returns a device with description including the metadata as described here
    # https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_30.html

    This function is deprecated and will be removed in May 2026 or later.
    Use SpikeGLXRecordingInterface._get_device_metadata_from_probe() instead,
    which extracts device metadata directly from probe information.

    Parameters
    ----------
    meta : dict
        The metadata dictionary containing SpikeGLX probe information.

    Returns
    -------
    dict
        a dict containing the metadata necessary for creating the device
    """
    import warnings

    warnings.warn(
        "get_device_metadata is deprecated and will be removed in May 2026 or later. "
        "Use SpikeGLXRecordingInterface._get_device_metadata_from_probe() instead.",
        FutureWarning,
        stacklevel=2,
    )
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
