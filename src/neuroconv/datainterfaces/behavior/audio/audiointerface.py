from pathlib import Path
from typing import List, Literal, Optional
from warnings import warn

import numpy as np
from pynwb import NWBFile, TimeSeries
from scipy.io.wavfile import read

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.audio import add_acoustic_waveform_series
from neuroconv.tools.nwb_helpers import make_or_load_nwbfile
from neuroconv.utils import FilePathType, get_base_schema, get_schema_from_hdmf_class


def _check_file_paths(file_paths, metadata: dict):
    number_of_file_paths = len(file_paths)
    assert len(metadata) == number_of_file_paths, (
        f"Incomplete metadata, the number of metadata for Audio is ({len(metadata)}) "
        f"is not equal to the number of expected metadata ({number_of_file_paths})."
    )


def _check_audio_names_are_unique(metadata: dict):
    neurodata_names = [neurodata["name"] for neurodata in metadata]
    neurodata_names_are_unique = len(set(neurodata_names)) == len(neurodata_names)
    assert neurodata_names_are_unique, f"Some of the names for Audio metadata are not unique."


def _check_starting_times(starting_times: list, metadata: List[dict]) -> list:
    if starting_times is not None:
        assert isinstance(starting_times, list) and all(
            [isinstance(x, float) for x in starting_times]
        ), "Argument 'starting_times' must be a list of floats."

    if len(metadata) == 1 and starting_times is None:
        warn("starting_times not provided, setting to 0.0")
        starting_times = [0.0]

    assert len(starting_times) == len(metadata), (
        f"The number of entries in 'starting_times' ({len(starting_times)}) must be equal to number of unique "
        f"AcousticWaveformSeries ({len(metadata)}). \n"
        f"'starting_times' provided as input {starting_times}."
    )
    return starting_times


class AudioInterface(BaseDataInterface):
    def __init__(self, file_paths: list, verbose: bool = False):
        """
        Data interface for writing acoustic recordings to an NWB file.

        Writes acoustic recordings as an ``AcousticWaveformSeries`` from the ndx_sound extension.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using ``natsort`` to ensure the files are in consecutive order.
                >>> from natsort import natsorted
                >>> natsorted(file_paths)
        verbose : bool, default: False
        """
        suffixes = [suffix for file_path in file_paths for suffix in Path(file_path).suffixes]
        format_is_not_supported = [
            suffix for suffix in suffixes if suffix not in [".wav"]
        ]  # TODO: add support for more formats
        if format_is_not_supported:
            raise ValueError(
                "The currently supported file format for audio is WAV file. "
                f"Some of the provided files does not match this format: {format_is_not_supported}."
            )
        self.verbose = verbose
        super().__init__(file_paths=file_paths)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        time_series_metadata_schema = get_schema_from_hdmf_class(TimeSeries)
        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
        time_series_metadata_schema.update(required=["name"])
        metadata_schema["properties"]["Behavior"].update(
            required=["Audio"],
            properties=dict(
                Audio=dict(
                    type="array",
                    minItems=1,
                    items=time_series_metadata_schema,
                )
            ),
        )
        return metadata_schema

    def get_metadata(self) -> dict:
        default_name = "AcousticWaveformSeries"
        is_multiple_file_path = len(self.source_data["file_paths"]) > 1
        audio_metadata = [
            dict(
                name=default_name + str(file_ind) if is_multiple_file_path and file_ind > 0 else default_name,
                description="Acoustic waveform series.",
            )
            for file_ind, file_path in enumerate(self.source_data["file_paths"])
        ]
        behavior_metadata = dict(Audio=audio_metadata)

        metadata = super().get_metadata()
        metadata.update(Behavior=behavior_metadata)
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve the original unaltered timestamps for this interface! "
            "Define the `get_original_timestamps` method for this interface."
        )

    def get_timestamps(self) -> np.ndarray:
        raise NotImplementedError(
            "Unable to retrieve timestamps for this interface! Define the `get_timestamps` method for this interface."
        )

    def align_timestamps(self, aligned_timestamps: np.ndarray):
        raise NotImplementedError(
            "The protocol for synchronizing the timestamps of this interface has not been specified!"
        )

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 1000,
        write_as: Literal["stimulus", "acquisition"] = "stimulus",
        starting_times: Optional[list] = None,
        iterator_options: Optional[dict] = None,
        compression_options: Optional[dict] = None,
        overwrite: bool = False,
        verbose: bool = True,
    ):
        """

        Parameters
        ----------
        nwbfile_path : FilePathType, optional
            If a file exists at this path, append to it. If not, write the file here.
        nwbfile : NWBFile, optional
            Append to this NWBFile object
        metadata : dict, optional
        stub_test : bool, default: False
        stub_frames : int, default: 1000
        write_as : {'stimulus', 'acquisition'}
            The acoustic waveform series can be added to the NWB file either as
            "stimulus" or as "acquisition".
        starting_times : list, optional
            Starting time for each AcousticWaveformSeries
        iterator_options : dict, optional
            Dictionary of options for the SliceableDataChunkIterator.
        compression_options : dict, optional
            Dictionary of options for compressing the data for H5DataIO.
        overwrite : bool, default: False
        verbose : bool, default: True

        Returns
        -------
        NWBFile

        """
        file_paths = self.source_data["file_paths"]
        audio_metadata = metadata["Behavior"]["Audio"]
        # Checks for metadata
        _check_file_paths(file_paths=file_paths, metadata=audio_metadata)
        _check_audio_names_are_unique(metadata=audio_metadata)

        audio_name_list = [audio["name"] for audio in audio_metadata]
        any_duplicated_audio_names = len(set(audio_name_list)) < len(file_paths)
        if any_duplicated_audio_names:
            raise ValueError("There are duplicated file names in the metadata!")

        starting_times = _check_starting_times(starting_times=starting_times, metadata=audio_metadata)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            for file_ind, (acoustic_waveform_series_metadata, file_path) in enumerate(zip(audio_metadata, file_paths)):
                sampling_rate, acoustic_series = read(filename=file_path, mmap=True)
                if stub_test:
                    acoustic_series = acoustic_series[:stub_frames]

                add_acoustic_waveform_series(
                    acoustic_series=acoustic_series,
                    nwbfile=nwbfile_out,
                    rate=sampling_rate,
                    metadata=acoustic_waveform_series_metadata,
                    write_as=write_as,
                    starting_time=starting_times[file_ind],
                    iterator_options=iterator_options,
                    compression_options=compression_options,
                )

        return nwbfile_out
