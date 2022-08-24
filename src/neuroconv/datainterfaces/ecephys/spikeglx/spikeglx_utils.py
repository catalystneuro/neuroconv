from datetime import datetime
from pathlib import Path

from ....utils import FilePathType


def _assert_single_shank_for_spike_extractors(recording):
    """Raises an exception for a se.SpikeGLXRecordingExtractor object intialized in a file
    with complex geometry as this is not (and will not be )supported in the old spikeextractors API.

    Parameters
    ----------
    recording : se.SpikeGLXRecordingExtractor
        a newly instantiated version of the spikeextractors object

    Raises
    ------
    NotImplementedError
        Raises a not implemented error.
    """
    meta = recording._meta
    # imDatPrb_type 0 and 21 correspond to single shank channels
    # see https://billkarsh.github.io/SpikeGLX/help/imroTables/
    imDatPrb_type = meta["imDatPrb_type"]
    if imDatPrb_type not in ["0", "21"]:
        raise NotImplementedError(
            "More than a single shank is not supported in spikeextractors, use the new spikeinterface."
        )


def _fetch_metadata_dic_for_spikextractors_spikelgx_object(recording) -> dict:
    """
    fetches the meta file from a se.SpikeGLXRecordingExtractor object.
    Parameters
    ----------
    recording : se.SpikeGLXRecordingExtractor
        a newly instantiated version of the spikeextractors object


    Returns
    -------
    dict
        a dictionary with the metadadata concerning the recording
    """
    from spikeextractors import SubRecordingExtractor

    if isinstance(recording, SubRecordingExtractor):
        recording_metadata = recording._parent_recording._meta
    else:
        recording_metadata = recording._meta

    return recording_metadata


def get_session_start_time(recording_metadata: dict) -> datetime:
    """Fetches the session start time from the recording_metadata dic
    Parameters
    ----------
    recording_metadata : dict
        the metadata dic as obtained from the Spikelgx recording.

    Returns
    -------
    datetime
        the session start time in datetime format.
    """

    session_start_time = recording_metadata.get("fileCreateTime", None)
    if session_start_time:
        session_start_time = datetime.fromisoformat(session_start_time)

    return session_start_time


def fetch_stream_id_for_spikelgx_file(file_path: FilePathType) -> str:
    """Returns the stream_id for a spikelgx file

    Example of file name structure:
    Consider the filenames: `Noise4Sam_g0_t0.nidq.bin` or `Noise4Sam_g0_t0.imec0.lf.bin`
    The filenames consist of 3 or 4 parts separated by `.`
    1. "Noise4Sam_g0_t0" will be the `name` variable. This choosen by the user at recording time.
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
