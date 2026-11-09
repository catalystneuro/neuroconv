import json
import struct
import warnings
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ...._temporal_alignment import _TemporalAlignment
from ....basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from ....tools.audio import add_acoustic_waveform_series
from ....tools.nwb_helpers._metadata_and_file_helpers import _validate_metadata_key
from ....utils import (
    DeepDict,
    calculate_regular_series_rate,
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
        self,
        file_path: FilePath | None = None,
        *,
        file_paths: list[FilePath] | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """
        Data interface for writing acoustic recordings to an NWB file.

        Writes acoustic recordings as an ``AcousticWaveformSeries`` from the ndx_sound extension.

        Parameters
        ----------
        file_path : FilePath, optional
            The path to the audio recording. For several recordings, use one interface per file.
        file_paths : list of FilePaths, optional
            Deprecated. Use ``file_path`` with one interface per file instead. Will be removed in v0.13.0.
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using ``natsort`` to ensure the files are in consecutive order::

                from natsort import natsorted
                natsorted(file_paths)

        metadata_key : str, optional
            Snake_case key that identifies this recording's entry under
            ``metadata["Audio"]["AcousticWaveformSeries"]``. Defaults to ``f"audio_{file_path.stem}"``.
            The series name is the entry's ``name`` field, which defaults to ``"AcousticWaveformSeries"``.
            Not used with ``file_paths``, whose metadata is the ``metadata["Behavior"]["Audio"]`` list.
        verbose : bool, default: False
        """

        # This import is to assure that ndx_sound is in the global namespace when an pynwb.io object is created.
        # For more detail, see https://github.com/rly/ndx-pose/issues/36
        import ndx_sound  # noqa: F401

        if (file_path is None) == (file_paths is None):
            raise ValueError("AudioInterface takes exactly one of 'file_path' or the deprecated 'file_paths'.")
        if file_paths is not None:
            warnings.warn(
                "The 'file_paths' parameter of AudioInterface is deprecated and will be removed in v0.13.0, and it does "
                "not support 'temporal_alignment'. Use 'file_path' with one AudioInterface per file instead.",
                FutureWarning,
                stacklevel=4,  # __init__, two validate_call frames, caller
            )
            self.metadata_key = None
        else:
            self.metadata_key = metadata_key or f"audio_{Path(file_path).stem}"
            file_paths = [file_path]

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
        if self.metadata_key is None:
            super().__init__(file_paths=file_paths)
        else:
            super().__init__(file_path=file_path)
        self._segment_starting_times = None

        # Alignment by composition, with the one recording keyed by `metadata_key`. See neuroconv/_temporal_alignment.py.
        # The deprecated `file_paths` keeps its own starting times and registers nothing.
        self.temporal_alignment = _TemporalAlignment()
        if self.metadata_key is not None:
            self.temporal_alignment._register(
                key=self.metadata_key,
                get_native_times=self._get_native_times,
                default_start_time=0.0,
                get_number_of_samples=lambda: self._read_acoustic_series(file_path)[1].shape[0],
            )

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()

        time_series_metadata_schema_path = (
            Path(__file__).parent.parent.parent.parent / "schemas" / "time_series_schema.json"
        )
        with open(file=time_series_metadata_schema_path, encoding="utf-8") as fp:
            time_series_metadata_schema = json.load(fp=fp)
        time_series_metadata_schema.update(required=["name"])

        if self.metadata_key is not None:
            metadata_schema["properties"]["Audio"] = get_base_schema(tag="Audio")
            metadata_schema["properties"]["Audio"].update(
                required=["AcousticWaveformSeries"],
                properties=dict(
                    AcousticWaveformSeries=dict(
                        type="object",
                        properties={self.metadata_key: time_series_metadata_schema},
                        required=[self.metadata_key],
                    )
                ),
            )
            return metadata_schema

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
        if self.metadata_key is not None:
            metadata = super().get_metadata()
            metadata["Audio"]["AcousticWaveformSeries"][self.metadata_key] = dict(
                name="AcousticWaveformSeries",
                description="Acoustic waveform series.",
            )
            return metadata

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
        if self.metadata_key is None:
            raise NotImplementedError("The AudioInterface does not yet support timestamps.")
        warnings.warn(
            "`get_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].get_times()` instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.temporal_alignment[self.metadata_key].get_times()

    def set_aligned_timestamps(self, aligned_timestamps: list[np.ndarray]):
        if self.metadata_key is None:
            raise NotImplementedError("The AudioInterface does not yet support timestamps.")
        warnings.warn(
            "`set_aligned_timestamps` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment[key].set_times(times)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.temporal_alignment[self.metadata_key].set_times(aligned_timestamps)

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
        warnings.warn(
            "`set_aligned_starting_time` is deprecated and will be removed in v0.13.0. "
            "Use `interface.temporal_alignment.shift_times(delta)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        if self.metadata_key is not None:
            # The recording starts at zero, so the old first call placing it and later calls shifting it are one shift
            self.temporal_alignment.shift_times(aligned_starting_time)
            return

        # A shift, so it accumulates: whatever starting times are already set move together. Only a
        # single file can start from nothing, since the shift then places that one file; several files
        # need their relative starting times first.
        if self._segment_starting_times is not None:
            self._segment_starting_times = [
                segment_starting_time + aligned_starting_time for segment_starting_time in self._segment_starting_times
            ]
        elif self._number_of_audio_files == 1:
            self._segment_starting_times = [aligned_starting_time]
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
        warnings.warn(
            "`set_aligned_segment_starting_times` is deprecated and will be removed in v0.13.0. Use one "
            "AudioInterface per file and `interface.temporal_alignment[key].move_start_to(starting_time)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        aligned_segment_starting_times_length = len(aligned_segment_starting_times)
        assert isinstance(aligned_segment_starting_times, list) and all(
            [isinstance(x, float) for x in aligned_segment_starting_times]
        ), "Argument 'aligned_segment_starting_times' must be a list of floats."
        assert aligned_segment_starting_times_length == self._number_of_audio_files, (
            f"The number of entries in 'aligned_segment_starting_times' ({aligned_segment_starting_times_length}) "
            f"must be equal to the number of audio file paths ({self._number_of_audio_files})."
        )

        if self.metadata_key is not None:
            self.temporal_alignment[self.metadata_key].move_start_to(aligned_segment_starting_times[0])
            return

        self._segment_starting_times = aligned_segment_starting_times

    def align_by_interpolation(self, unaligned_timestamps: np.ndarray, aligned_timestamps: np.ndarray):
        if self.metadata_key is None:
            raise NotImplementedError("The AudioInterface does not yet support timestamps.")
        warnings.warn(
            "`align_by_interpolation` is deprecated and will be removed in v0.13.0. Use "
            "`interface.temporal_alignment.remap_times(local_sync_times=..., reference_sync_times=...)` instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.temporal_alignment.remap_times(
            local_sync_times=unaligned_timestamps, reference_sync_times=aligned_timestamps
        )

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        stub_frames: int = 1000,
        parent_container: Literal["stimulus", "acquisition"] | None = None,
        iterator_options: dict | None = None,
        write_as: Literal["stimulus", "acquisition"] | None = None,
    ):
        """
        Parameters
        ----------
        nwbfile : NWBFile
            Append to this NWBFile object
        metadata : dict, optional
        stub_test : bool, default: False
        stub_frames : int, default: 1000
        parent_container : {'stimulus', 'acquisition'}, optional
            The acoustic waveform series can be added to the NWB file either as
            "stimulus" or as "acquisition". When not passed, it is added as "stimulus" with a
            ``FutureWarning``, and the default becomes "acquisition" in v0.13.0.
        iterator_options : dict, optional
            Dictionary of options for the SliceableDataChunkIterator.
        write_as : {'stimulus', 'acquisition'}, optional
            Deprecated. Use ``parent_container`` instead. Will be removed in v0.12.0.

        Returns
        -------
        NWBFile
        """
        if write_as is not None:
            warnings.warn(
                "The 'write_as' parameter of AudioInterface.add_to_nwbfile() is deprecated and will be removed "
                "in v0.12.0. Use 'parent_container' instead.",
                FutureWarning,
                stacklevel=2,
            )
            parent_container = write_as

        if parent_container is None:
            warnings.warn(
                "The default 'parent_container' of AudioInterface.add_to_nwbfile() will change from 'stimulus' to "
                "'acquisition' in v0.13.0. Pass parent_container='stimulus' to keep the current behavior or "
                "parent_container='acquisition' to adopt the new default.",
                FutureWarning,
                stacklevel=2,
            )
            parent_container = "stimulus"

        metadata = metadata or self.get_metadata()

        if self.metadata_key is not None:
            metadata_path = ("Audio", "AcousticWaveformSeries")
            _validate_metadata_key(metadata, metadata_path=metadata_path, metadata_key=self.metadata_key)
            file_paths = [self.source_data["file_path"]]
            audio_metadata = [metadata["Audio"]["AcousticWaveformSeries"][self.metadata_key]]

            time_bearing_object = self.temporal_alignment[self.metadata_key]
            if time_bearing_object._times is None:
                # Times nobody set run at the file's sampling rate, so the start is all the alignment changes
                file_timings = [dict(starting_time=time_bearing_object._get_start_time())]
            else:
                timestamps = time_bearing_object.get_times()
                rate = calculate_regular_series_rate(series=timestamps)
                if rate is not None:
                    file_timings = [dict(starting_time=timestamps[0], rate=rate)]
                else:
                    file_timings = [dict(timestamps=timestamps)]
        else:
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
            file_timings = [dict(starting_time=starting_time) for starting_time in starting_times]

        for acoustic_waveform_series_metadata, file_path, file_timing in zip(audio_metadata, file_paths, file_timings):
            sampling_rate, acoustic_series = self._read_acoustic_series(file_path)
            # The file's sampling rate unless the alignment gave times with a rate of their own
            timing = dict(rate=sampling_rate) | file_timing

            if stub_test:
                acoustic_series = acoustic_series[:stub_frames]
                if "timestamps" in timing:
                    timing["timestamps"] = timing["timestamps"][:stub_frames]

            add_acoustic_waveform_series(
                acoustic_series=acoustic_series,
                nwbfile=nwbfile,
                metadata=acoustic_waveform_series_metadata,
                parent_container=parent_container,
                iterator_options=iterator_options,
                **timing,
            )

        return nwbfile

    def _get_native_times(self) -> np.ndarray:
        """Return the time of every sample, spaced by the sampling rate from zero, since a WAV file records no start."""
        sampling_rate, acoustic_series = self._read_acoustic_series(self.source_data["file_path"])
        return np.arange(acoustic_series.shape[0]) / sampling_rate

    def _read_acoustic_series(self, file_path: FilePath) -> tuple[int, np.ndarray]:
        """Read the sampling rate and the samples of a WAV file."""
        import scipy

        # Check if the WAV file is 24-bit (3 bytes per sample)
        bit_depth = self._get_wav_bit_depth(file_path)

        # Memory mapping is not compatible with 24-bit WAV files
        use_mmap = bit_depth != 24

        return scipy.io.wavfile.read(filename=file_path, mmap=use_mmap)

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
