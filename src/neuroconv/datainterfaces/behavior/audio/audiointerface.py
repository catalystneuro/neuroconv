import json
from pathlib import Path
from typing import List, Literal, Optional
from warnings import warn

import numpy as np
import scipy
from pynwb import NWBFile, TimeSeries

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces.behavior.video.videodatainterface import _check_duplicates
from neuroconv.tools.audio import add_acoustic_waveform_series
from neuroconv.tools.nwb_helpers import make_or_load_nwbfile
from neuroconv.utils import FilePathType, get_base_schema


def _check_audio_names_are_unique(metadata: dict):
    neurodata_names = [neurodata["name"] for neurodata in metadata]
    neurodata_names_are_unique = len(set(neurodata_names)) == len(neurodata_names)
    assert neurodata_names_are_unique, f"Some of the names for Audio metadata are not unique."


class AudioInterface(BaseDataInterface):
    """Data interface for writing acoustic recordings to an NWB file."""

    def __init__(self, file_paths: list, verbose: bool = False):
        """
        Create the interface for writing acoustic recordings as AcousticWaveformSeries.

        Parameters
        ----------
        file_paths : list of FilePathTypes
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using `natsort` to ensure the files are in consecutive order.
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
        self._starting_times = None

    def get_metadata_schema(self):
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

    def align_timestamps(self, aligned_timestamps: List[np.ndarray]):
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def align_starting_time(self, starting_time: float):
        raise NotImplementedError(
            "The VideoInterface operates on a list of file paths; to reduce ambiguity, please choose "
            "between `align_global_starting_time` (shift starting time of each video by the same value) "
            "and `align_starting_times` (specify a list of values to use in shifting the starting time for each video)."
        )

    def align_global_starting_time(self, global_starting_time: float, stub_test: bool = False):
        """
        Align all starting times for all videos in this interface relative to the common session start time.
        Must be in units seconds relative to the common 'session_start_time'.
        Parameters
        ----------
        global_starting_time : float
            The starting time for all temporal data in this interface.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.
            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        if self._timestamps is not None:
            self.align_timestamps(
                aligned_timestamps=[
                    timestamps + global_starting_time for timestamps in self.get_timestamps(stub_test=stub_test)
                ]
            )
        elif self._starting_times is not None:
            self._starting_times = [starting_time + global_starting_time for starting_time in self._starting_times]
        else:
            raise ValueError("There are no timestamps or starting times set to shift by a global value!")

    def align_starting_times(self, starting_times: List[float], stub_test: bool = False):
        """
        Align the individual starting time for each video in this interface relative to the common session start time.
        Must be in units seconds relative to the common 'session_start_time'.
        Parameters
        ----------
        starting_times : list of floats
            The relative starting times of each video.
        stub_test : bool, default: False
            If timestamps have not been set to this interface, it will attempt to retrieve them
            using the `.get_original_timestamps` method, which scans through each video;
            a process which can take some time to complete.
            To limit that scan to a small number of frames, set `stub_test=True`.
        """
        starting_times_length = len(starting_times)
        assert isinstance(starting_times, list) and all(
            [isinstance(x, float) for x in starting_times]
        ), "Argument 'starting_times' must be a list of floats."
        assert starting_times_length == self._number_of_audio_files, (
            f"The number of entries in 'starting_times' ({starting_times_length}) must be equal to the number of "
            f"audio file paths ({self._number_of_audio_files})."
        )

        self._starting_times = starting_times

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        raise NotImplementedError("The AudioInterface does not yet support timestamps.")

    def run_conversion(
        self,
        nwbfile_path: Optional[FilePathType] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 1000,
        write_as: Literal["stimulus", "acquisition"] = "stimulus",
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
        _check_audio_names_are_unique(metadata=audio_metadata)
        assert len(audio_metadata) == self._number_of_audio_files, (
            f"The Audio metadata is incomplete ({len(audio_metadata)} entry)! "
            f"Expected {self._number_of_audio_files} (one for each entry of 'file_paths')."
        )

        audio_metadata_unique, file_paths_unique = _check_duplicates(audio_metadata, file_paths)
        unpacked_file_paths_unique = [file_path[0] for file_path in file_paths_unique]

        if self._number_of_audio_files > 1 and self._starting_times is None:
            raise ValueError(
                "If you have multiple audio files, then you must specify each starting time with '.align_starting_time(...)'!"
            )
        starting_times = self._starting_times or [0.0]

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            for file_index, (acoustic_waveform_series_metadata, file_path) in enumerate(
                zip(audio_metadata_unique, unpacked_file_paths_unique)
            ):
                sampling_rate, acoustic_series = scipy.io.wavfile.read(filename=file_path, mmap=True)
                if stub_test:
                    acoustic_series = acoustic_series[:stub_frames]

                add_acoustic_waveform_series(
                    acoustic_series=acoustic_series,
                    nwbfile=nwbfile_out,
                    rate=sampling_rate,
                    metadata=acoustic_waveform_series_metadata,
                    write_as=write_as,
                    starting_time=starting_times[file_index],
                    iterator_options=iterator_options,
                    compression_options=compression_options,
                )

        return nwbfile_out
