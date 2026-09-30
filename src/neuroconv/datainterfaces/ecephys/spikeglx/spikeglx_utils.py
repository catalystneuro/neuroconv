"""Utilities used by the SpikeGLX interfaces."""

import warnings
from datetime import datetime
from pathlib import Path

from pydantic import FilePath


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
    file_path : FilePath
        The file_path of spikelgx file.

    Returns
    -------
    str
        the stream_id
    """
    import warnings

    warnings.warn(
        "fetch_stream_id_for_spikelgx_file is deprecated and deprecated and will be removed by the end of 2025. "
        "This function was used to dtermine the stream_id for a filename to initialize the stream from a file_path. "
        "But after file_path is removed from the SpikeGLXRecordingInterface init, this function is no longer needed.",
        FutureWarning,
        stacklevel=2,
    )

    suffixes = Path(file_path).suffixes
    device = next(suffix for suffix in suffixes if "imec" in suffix or "nidq" in suffix)
    signal_kind = ""
    if "imec" in device:
        signal_kind = next(suffix for suffix in suffixes if "ap" in suffix or "lf" in suffix)

    stream_id = device[1:] + signal_kind

    return stream_id
