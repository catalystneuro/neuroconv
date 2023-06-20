from typing import Literal, Optional
from warnings import warn

from hdmf.backends.hdf5 import H5DataIO
from pynwb import NWBFile

from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.utils import ArrayType


def add_acoustic_waveform_series(
    acoustic_series: ArrayType,
    nwbfile: NWBFile,
    rate: float,
    metadata: dict,
    starting_time: float = 0.0,
    write_as: Literal["stimulus", "acquisition"] = "stimulus",
    iterator_options: Optional[dict] = None,
    compression_options: Optional[dict] = None,
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
    write_as : {'stimulus', 'acquisition'}
        The acoustic waveform series can be added to the NWB file either as
        "stimulus" or as "acquisition".
    iterator_options : dict, optional
        Dictionary of options for the SliceableDataChunkIterator.
    compression_options : dict, optional
        Dictionary of options for compressing the data for H5DataIO.

    Returns
    -------
        The nwbfile passed as an input with the AcousticWaveformSeries added.
    """
    from ndx_sound import AcousticWaveformSeries

    assert write_as in [
        "stimulus",
        "acquisition",
    ], "Acoustic series can be written either as 'stimulus' or 'acquisition'."

    compression_options = compression_options or dict(compression="gzip")
    iterator_options = iterator_options or dict()

    container = nwbfile.acquisition if write_as == "acquisition" else nwbfile.stimulus
    # Early return if acoustic waveform series with this name already exists in NWBFile
    if metadata["name"] in container:
        warn(f"{metadata['name']} already in nwbfile")
        return nwbfile

    acoustic_waveform_series_kwargs = dict(
        rate=float(rate),
        starting_time=starting_time,
        data=H5DataIO(SliceableDataChunkIterator(data=acoustic_series, **iterator_options), **compression_options),
    )

    # Add metadata
    acoustic_waveform_series_kwargs.update(**metadata)

    # Create AcousticWaveformSeries with ndx-sound
    acoustic_waveform_series = AcousticWaveformSeries(**acoustic_waveform_series_kwargs)

    # Add audio recording to nwbfile as acquisition or stimuli
    if write_as == "acquisition":
        nwbfile.add_acquisition(acoustic_waveform_series)
    elif write_as == "stimulus":
        nwbfile.add_stimulus(acoustic_waveform_series)
