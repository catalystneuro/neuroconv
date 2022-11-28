from datetime import datetime
from pathlib import Path

import numpy as np

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


def get_events_from_nidq_channel(recording_nidq, event_channel_id: int) -> np.ndarray:
    """
    Estimate the pulse timing of each event from the NIDQ channel.

    Parameters
    ----------
    recording_nidq: SpikeGLXRecordingExtractor
        An extractor that can read from the NIDQ streams.
    event_channel: int
        The channel id correponding to the event message signal
    Returns
    -------
    trial_times: list
        List with t_start and t_stop for each trial
    """
    hex_base = 16  # In case it's not a simple on/off pulse type but a hex-coded signal
    voltage_range = 4.5 * 1e6

    tr_events = recording_nidq.get_traces(channel_ids=[event_channel_id])[0]
    scaled_tr_events = tr_events * (hex_base - 1) / voltage_range
    scaled_tr_events = (scaled_tr_events - min(scaled_tr_events)) / np.ptp(scaled_tr_events) * (hex_base - 1)

    tr_events_bin = np.zeros(tr_events.shape, dtype=int)
    tr_events_bin[tr_events > np.max(tr_events) // 2] = 1

    t_start_idxs = np.where(np.diff(tr_events_bin) > 0)[0]
    t_stop_idxs = np.where(np.diff(tr_events_bin) < 0)[0]

    # discard first stop event if it comes before a start event
    if t_stop_idxs[0] < t_start_idxs[0]:
        print("Discarding first trial")
        t_stop_idxs = t_stop_idxs[1:]

    # discard last start event if it comes after last stop event
    if t_start_idxs[-1] > t_stop_idxs[-1]:
        print("Discarding last trial")
        t_start_idxs = t_start_idxs[:-1]

    assert len(t_start_idxs) == len(t_stop_idxs), "Found a different number of start and stop indices!"

    trial_times = []
    for t in range(len(t_start_idxs)):
        start_idx = t_start_idxs[t]
        stop_idx = t_stop_idxs[t]

        trial_times.append(recording_nidq.frame_to_time(np.array([start_idx, stop_idx])))

    return np.array(trial_times)
