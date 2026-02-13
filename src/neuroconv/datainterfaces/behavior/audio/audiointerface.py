import json
import struct
import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools.audio import add_acoustic_waveform_series
from ....utils import (
    DeepDict,
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
    def __init__(
        self, file_paths: list[FilePath], *args, verbose: bool = False
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Data interface for writing acoustic recordings to an NWB file.

        Writes acoustic recordings as an ``AcousticWaveformSeries`` from the ndx_sound extension.

        Parameters
        ----------
        file_paths : list of FilePaths
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using ``natsort`` to ensure the files are in consecutive order::

                from natsort import natsorted
                natsorted(file_paths)

        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
            ]
            num_positional_args_before_args = 1  # file_paths
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to AudioInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)

        # This import is to assure that ndx_sound is in the global namespace when an pynwb.io object is created.
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        import ndx_sound  # noqa: F401

        # Only check the last suffix of each file path
        suffixes = [Path(file_path).suffix for file_path in file_paths]
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
        with open(file=time_series_metadata_schema_path, encoding="utf-8") as fp:
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

    def get_metadata(self) -> DeepDict:
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

    def get_timestamps(self) -> np.ndarray | None:
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
        metadata: dict | None = None,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stub_test: bool = False,
        stub_frames: int = 1000,
        write_as: Literal["stimulus", "acquisition"] = "stimulus",
        iterator_options: dict | None = None,
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

        Returns
        -------
        NWBFile
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stub_test",
                "stub_frames",
                "write_as",
                "iterator_options",
            ]
            num_positional_args_before_args = 2  # nwbfile, metadata
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"add_to_nwbfile() takes at most {len(parameter_names) + num_positional_args_before_args} positional arguments but "
                    f"{len(args) + num_positional_args_before_args} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to AudioInterface.add_to_nwbfile() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stub_test = positional_values.get("stub_test", stub_test)
            stub_frames = positional_values.get("stub_frames", stub_frames)
            write_as = positional_values.get("write_as", write_as)
            iterator_options = positional_values.get("iterator_options", iterator_options)

        import scipy

        metadata = metadata or self.get_metadata()

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
            # Check if the WAV file is 24-bit (3 bytes per sample)
            bit_depth = self._get_wav_bit_depth(file_path)

            # Memory mapping is not compatible with 24-bit WAV files
            use_mmap = bit_depth != 24

            sampling_rate, acoustic_series = scipy.io.wavfile.read(filename=file_path, mmap=use_mmap)

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
            )

        return nwbfile

    @staticmethod
    def _get_wav_bit_depth(file_path: FilePath) -> int:
        """
        Get the bit depth of a WAV file.
        Parameters
        ----------
        file_path : str or Path
            Path to the WAV file
        Returns
        -------
        int
            Bit depth of the WAV file (8, 16, 24, 32, etc.)
        """

        struct_module_uint16 = "<H"  # < Is little-endian

        with open(file_path, "rb") as f:
            f.seek(34)
            bits_per_sample = struct.unpack(struct_module_uint16, f.read(2))[0]

            return bits_per_sample
