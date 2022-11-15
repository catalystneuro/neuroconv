from pathlib import Path
from typing import Optional
from warnings import warn

from hdmf.backends.hdf5 import H5DataIO
from scipy.io.wavfile import read

from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces.behavior.video.videodatainterface import _check_duplicates
from neuroconv.tools.hdmf import SliceableDataChunkIterator
from neuroconv.tools.nwb_helpers import (
    make_or_load_nwbfile,
)
from neuroconv.utils import (
    get_schema_from_hdmf_class,
    get_base_schema,
    OptionalFilePathType,
)
from pynwb import NWBFile, TimeSeries

from ndx_sound import AcousticWaveformSeries


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

    def add_acoustic_waveform_series(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        file_path: str,
        starting_time: float,
        write_as: Optional[str] = "stimulus",  # "stimulus" or "acquisition"
        stub_test: bool = False,
        stub_frames: int = 1000,
        iterator_options: Optional[dict] = None,
        compression_options: Optional[dict] = None,
    ):

        compression_options = compression_options or dict(compression="gzip")
        iterator_options = iterator_options or dict()

        container = nwbfile.acquisition if write_as == "acquisition" else nwbfile.stimulus
        # Early return if acoustic waveform series with this name already exists in NWBFile
        if metadata["name"] in container:
            return

        # Load the audio file
        sampling_rate, audio_data = read(filename=file_path, mmap=True)
        if stub_test:
            audio_data = audio_data[:stub_frames]

        acoustic_waveform_series_kwargs = dict(
            rate=float(sampling_rate),
            starting_time=starting_time,
            data=H5DataIO(SliceableDataChunkIterator(data=audio_data, **iterator_options), **compression_options)
            if not stub_test
            else audio_data,
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

        return nwbfile

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

        assert write_as in ["stimulus", "acquisition"], "Audio can be written either as 'stimulus' or 'acquisition'."

        metadata = metadata or dict()

        audio_metadata = metadata.get("Behavior", dict()).get("Audio", None)
        if audio_metadata is None:
            audio_metadata = self.get_metadata()["Behavior"]["Audio"]

        number_of_file_paths = len(file_paths)
        assert len(audio_metadata) == number_of_file_paths, (
            "Incomplete metadata "
            f"(number of metadata in audio {len(audio_metadata)})"
            f"is not equal to the number of file_paths {number_of_file_paths}"
        )

        audio_names = [audio["name"] for audio in audio_metadata]
        audio_names_are_unique = len(set(audio_names)) == len(audio_names)
        assert audio_names_are_unique, "Some of the names for AcousticWaveformSeries are not unique."

        audio_metadata_unique, file_paths_unique = _check_duplicates(audio_metadata, file_paths)
        unpacked_file_paths_unique = [file_path[0] for file_path in file_paths_unique]

        if starting_times is not None:
            assert isinstance(starting_times, list) and all(
                [isinstance(x, float) for x in starting_times]
            ), "Argument 'starting_times' must be a list of floats."

            assert len(starting_times) == len(audio_metadata_unique), (
                f"starting times list length {len(starting_times)} must be equal to number of unique "
                f"AcousticWaveformSeries {len(audio_metadata_unique)} \n"
                f"Audio metadata provided as input {audio_metadata} \n"
                f"starting times = {starting_times} \n"
                f"AcousticWaveformSeries after _check_duplicates {audio_metadata_unique}"
            )

        else:
            if len(audio_metadata_unique) == 1:
                warn("starting_times not provided, setting to 0.0")
                starting_times = [0.0]
            else:
                raise ValueError("provide starting times as a list of len " f"{len(audio_metadata_unique)}")

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=self.verbose
        ) as nwbfile_out:
            for file_ind, (acoustic_waveform_series_metadata, file_path) in enumerate(
                zip(audio_metadata_unique, unpacked_file_paths_unique)
            ):

                self.add_acoustic_waveform_series(
                    file_path=file_path,
                    metadata=acoustic_waveform_series_metadata,
                    nwbfile=nwbfile_out,
                    write_as=write_as,
                    stub_test=stub_test,
                    starting_time=starting_times[file_ind],
                    iterator_options=iterator_options,
                    compression_options=compression_options,
                )

        return nwbfile_out
