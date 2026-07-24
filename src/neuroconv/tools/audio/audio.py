from typing import Literal
from warnings import warn

from pynwb import NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.utils import ArrayType


def add_acoustic_waveform_series(
    acoustic_series: ArrayType,
    nwbfile: NWBFile,
    rate: float,
    metadata: dict,
    starting_time: float = 0.0,
    write_as: Literal["stimulus", "acquisition"] | None = None,
    iterator_options: dict | None = None,
    *,
    parent_container: Literal["stimulus", "acquisition"] = "stimulus",
) -> NWBFile:
    """

    Adds the audio and its metadata to the NWB file either as stimulus or acquisition.
    The neurodata type that is used is an AcousticWaveformSeries object which holds a
    single or multichannel acoustic series.

    Parameters
    ----------
    acoustic_series : ArrayType
        The acoustic series to add to the NWB file.
    rate : float
        The sampling rate of the acoustic series.
    nwbfile : NWBFile
        The previously defined -in memory- NWBFile.
    metadata : dict
        The metadata for this acoustic series.
    starting_time : float, default: 0.0
        The starting time in seconds for this acoustic series relative to the
        start time of the session.
    parent_container : {'stimulus', 'acquisition'}
        The acoustic waveform series can be added to the NWB file either as
        "stimulus" or as "acquisition".
    iterator_options : dict, optional
        Dictionary of options for the SliceableDataChunkIterator.
    write_as : {'stimulus', 'acquisition'}, optional
        Deprecated. Use ``parent_container`` instead. Will be removed on or after December 2026.

    Returns
    -------
        The nwbfile passed as an input with the AcousticWaveformSeries added.
    """
    from ndx_sound import AcousticWaveformSeries

    if write_as is not None:
        warn(
            "The 'write_as' parameter of add_acoustic_waveform_series is deprecated and will be removed "
            "on or after December 2026. Use 'parent_container' instead.",
            FutureWarning,
            stacklevel=2,
        )
        parent_container = write_as

    assert parent_container in [
        "stimulus",
        "acquisition",
    ], "Acoustic series can be written either as 'stimulus' or 'acquisition'."

    iterator_options = iterator_options or dict()

    container = nwbfile.acquisition if parent_container == "acquisition" else nwbfile.stimulus
    # Early return if acoustic waveform series with this name already exists in NWBFile
    if metadata["name"] in container:
        warn(f"{metadata['name']} already in nwbfile")
        return nwbfile

    acoustic_waveform_series_kwargs = dict(
        rate=float(rate),
        starting_time=starting_time,
        data=SliceableDataChunkIterator(data=acoustic_series, **iterator_options),
    )

    # Add metadata
    acoustic_waveform_series_kwargs.update(**metadata)

    # Create AcousticWaveformSeries with ndx-sound
    acoustic_waveform_series = AcousticWaveformSeries(**acoustic_waveform_series_kwargs)

    # Add audio recording to nwbfile as acquisition or stimuli
    if parent_container == "acquisition":
        nwbfile.add_acquisition(acoustic_waveform_series)
    elif parent_container == "stimulus":
        nwbfile.add_stimulus(acoustic_waveform_series)
