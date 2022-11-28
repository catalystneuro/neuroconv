from pathlib import Path
from typing import Optional
from warnings import warn

from scipy.io.wavfile import read

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces.behavior.video.videodatainterface import _check_duplicates
from neuroconv.tools.audio import add_acoustic_waveform_series
from neuroconv.tools.nwb_helpers import (
    make_or_load_nwbfile,
)
from neuroconv.utils import (
    get_schema_from_hdmf_class,
    get_base_schema,
    OptionalFilePathType,
)
from pynwb import NWBFile, TimeSeries


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


def _check_starting_times(starting_times: list, metadata: dict) -> list:
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
    """Data interface for writing acoustic recordings to an NWB file."""

    def __init__(self, file_paths: list, verbose: bool = False):
        """
        Create the interface for writing acoustic recordings as AcousticWaveformSeries.

        Parameters
        ----------
        file_paths: list of FilePathTypes
            The file paths to the audio recordings in sorted, consecutive order.
            We recommend using `natsort` to ensure the files are in consecutive order.
            from natsort import natsorted
            natsorted(file_paths)
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

    def get_metadata_schema(self):

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

    def get_metadata(self):
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

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        stub_test: bool = False,
        stub_frames: int = 1000,
        write_as: str = "stimulus",
        starting_times: Optional[list] = None,
        iterator_options: Optional[dict] = None,
        compression_options: Optional[dict] = None,
        overwrite: bool = False,
        verbose: bool = True,
    ):
        file_paths = self.source_data["file_paths"]
        audio_metadata = metadata["Behavior"]["Audio"]
        # Checks for metadata
        _check_file_paths(file_paths=file_paths, metadata=audio_metadata)
        _check_audio_names_are_unique(metadata=audio_metadata)

        audio_metadata_unique, file_paths_unique = _check_duplicates(audio_metadata, file_paths)
        unpacked_file_paths_unique = [file_path[0] for file_path in file_paths_unique]

        starting_times = _check_starting_times(starting_times=starting_times, metadata=audio_metadata_unique)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            for file_ind, (acoustic_waveform_series_metadata, file_path) in enumerate(
                zip(audio_metadata_unique, unpacked_file_paths_unique)
            ):
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
