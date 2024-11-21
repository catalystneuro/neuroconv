import json
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import scipy
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools.audio import add_acoustic_waveform_series
from ....utils import (
    get_base_schema,
)


def _check_audio_names_are_unique(metadata: dict):
    neurodata_names = [neurodata["name"] for neurodata in metadata]
    neurodata_names_are_unique = len(set(neurodata_names)) == len(neurodata_names)
    assert neurodata_names_are_unique, "Some of the names for Audio metadata are not unique."


class AudioInterface(BaseTemporalAlignmentInterface):
    """Data interface for writing .wav audio recordings to an NWB file."""

    display_name = "Wav Audio"
    keywords = ("sound", "microphone")
    associated_suffixes = (".wav",)
    info = "Interface for writing audio recordings to an NWB file."

    @validate_call
    def __init__(self, file_paths: list[FilePath], verbose: bool = False):
        """
        Data interface for writing acoustic recordings to an NWB file.

        Writes acoustic recordings as an ``AcousticWaveformSeries`` from the ndx_sound extension.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using ``natsort`` to ensure the files are in consecutive order::

                from natsort import natsorted
                natsorted(file_paths)

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

        self._number_of_audio_files = len(file_paths)
        self.verbose = verbose
        super().__init__(file_paths=file_paths)
        self._segment_starting_times = None

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()

        time_series_metadata_schema_path = (
            Path(__file__).parent.parent.parent.parent / "schemas" / "time_series_schema.json"
        )
        with open(file=time_series_metadata_schema_path) as fp:
            time_series_metadata_schema = json.load(fp=fp)
        time_series_metadata_schema.update(required=["name"])

        metadata_schema["properties"]["Behavior"] = get_base_schema(tag="Behavior")
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
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def get_timestamps(self) -> Optional[np.ndarray]:
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def set_aligned_starting_time(self, aligned_starting_time: float):
        """
        Align all starting times for all audio files in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_starting_time : float
            The common starting time for all temporal data in this interface.
            Applies to all segments if there are multiple file paths used by the interface.
        """
        if self._segment_starting_times is None and self._number_of_audio_files == 1:
            self._segment_starting_times = [aligned_starting_time]
        elif self._segment_starting_times is not None and self._number_of_audio_files > 1:
            self._segment_starting_times = [
                segment_starting_time + aligned_starting_time for segment_starting_time in self._segment_starting_times
            ]
        else:
            raise ValueError(
                "There are no segment starting times to shift by a common value! "
                "Please set them using 'set_aligned_segment_starting_times'."
            )

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float]):
        """
        Align the individual starting time for each audio file in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The relative starting times of each audio file (segment).
        """
        aligned_segment_starting_times_length = len(aligned_segment_starting_times)
        assert isinstance(aligned_segment_starting_times, list) and all(
            [isinstance(x, float) for x in aligned_segment_starting_times]
        ), "Argument 'aligned_segment_starting_times' must be a list of floats."
        assert aligned_segment_starting_times_length == self._number_of_audio_files, (
            f"The number of entries in 'aligned_segment_starting_times' ({aligned_segment_starting_times_length}) "
            f"must be equal to the number of audio file paths ({self._number_of_audio_files})."
        )

        self._segment_starting_times = aligned_segment_starting_times

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 1000,
        write_as: Literal["stimulus", "acquisition"] = "stimulus",
        iterator_options: Optional[dict] = None,
        compression_options: Optional[dict] = None,  # TODO: remove completely after 10/1/2024
        overwrite: bool = False,
        verbose: bool = True,
    ):
        """
        Parameters
        ----------
        nwbfile : NWBFile
            Append to this NWBFile object
        metadata : dict, optional
        stub_test : bool, default: False
        stub_frames : int, default: 1000
        write_as : {'stimulus', 'acquisition'}
            The acoustic waveform series can be added to the NWB file either as
            "stimulus" or as "acquisition".
        iterator_options : dict, optional
            Dictionary of options for the SliceableDataChunkIterator.
        overwrite : bool, default: False
        verbose : bool, default: True

        Returns
        -------
        NWBFile
        """
        file_paths = self.source_data["file_paths"]
        audio_metadata = metadata["Behavior"]["Audio"]
        _check_audio_names_are_unique(metadata=audio_metadata)
        assert len(audio_metadata) == self._number_of_audio_files, (
            f"The Audio metadata is incomplete ({len(audio_metadata)} entry)! "
            f"Expected {self._number_of_audio_files} (one for each entry of 'file_paths')."
        )

        audio_name_list = [audio["name"] for audio in audio_metadata]
        any_duplicated_audio_names = len(set(audio_name_list)) < len(file_paths)
        if any_duplicated_audio_names:
            raise ValueError("There are duplicated file names in the metadata!")

        if self._number_of_audio_files > 1 and self._segment_starting_times is None:
            raise ValueError(
                "If you have multiple audio files, then you must specify each starting time by calling "
                "'.set_aligned_segment_starting_times(...)'!"
            )
        starting_times = self._segment_starting_times or [0.0]

        for file_index, (acoustic_waveform_series_metadata, file_path) in enumerate(zip(audio_metadata, file_paths)):
            sampling_rate, acoustic_series = scipy.io.wavfile.read(filename=file_path, mmap=True)

            if stub_test:
                acoustic_series = acoustic_series[:stub_frames]

            add_acoustic_waveform_series(
                acoustic_series=acoustic_series,
                nwbfile=nwbfile,
                rate=sampling_rate,
                metadata=acoustic_waveform_series_metadata,
                write_as=write_as,
                starting_time=starting_times[file_index],
                iterator_options=iterator_options,
                compression_options=compression_options,  # TODO: remove completely after 10/1/2024; still passing for deprecation warning
            )

        return nwbfile
