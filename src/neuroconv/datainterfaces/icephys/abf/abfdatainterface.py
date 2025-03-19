import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from warnings import warn

from pydantic import FilePath, validate_call

from ..baseicephysinterface import BaseIcephysInterface


def get_start_datetime(neo_reader):
    """
    Get start datetime for Abf file.

    Parameters
    ----------
    neo_reader : neo.io.AxonIO
        The Neo reader object for the ABF file.

    Returns
    -------
    datetime
        The start date and time of the recording.
    """
    if all(k in neo_reader._axon_info for k in ["uFileStartDate", "uFileStartTimeMS"]):
        startDate = str(neo_reader._axon_info["uFileStartDate"])
        startTime = round(neo_reader._axon_info["uFileStartTimeMS"] / 1000)
        startDate = datetime.strptime(startDate, "%Y%m%d")
        startTime = timedelta(seconds=startTime)
        return startDate + startTime
    else:
        warn(
            f"uFileStartDate or uFileStartTimeMS not found in {neo_reader.filename.split('/')[-1]}, datetime for "
            "recordings might be wrongly stored."
        )
        return neo_reader._axon_info["rec_datetime"]


class AbfInterface(BaseIcephysInterface):
    """Interface for ABF intracellular electrophysiology data."""

    display_name = "ABF Icephys"
    associated_suffixes = (".abf",)
    info = "Interface for ABF intracellular electrophysiology data."

    ExtractorName = "AxonIO"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_paths"] = dict(
            type="array",
            minItems=1,
            items={"type": "string", "format": "file"},
            description="Array of paths to ABF files.",
        )
        source_schema["properties"]["icephys_metadata"] = dict(
            type="object", description="Metadata for this experiment."
        )
        source_schema["properties"]["icephys_metadata_file_path"] = dict(
            type="string", format="file", description="Path to JSON file containing metadata for this experiment."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        file_paths: list[FilePath],
        icephys_metadata: Optional[dict] = None,
        icephys_metadata_file_path: Optional[FilePath] = None,
    ):
        """
        ABF IcephysInterface based on Neo AxonIO.

        Parameters
        ----------
        file_paths : list of FilePaths
            List of files to be converted to the same NWB file.
        icephys_metadata : dict, optional
            Dictionary containing the Icephys-specific metadata.
        icephys_metadata_file_path : FilePath, optional
            JSON file containing the Icephys-specific metadata.
        """
        super().__init__(file_paths=file_paths)
        self.source_data.update(
            icephys_metadata=icephys_metadata,
            icephys_metadata_file_path=icephys_metadata_file_path,
        )

    def get_metadata(self) -> dict:
        from ....tools.neo import get_number_of_electrodes, get_number_of_segments

        metadata = super().get_metadata()

        if self.source_data["icephys_metadata"]:
            icephys_metadata = self.source_data["icephys_metadata"]
        elif self.source_data["icephys_metadata_file_path"]:
            with open(self.source_data["icephys_metadata_file_path"]) as json_file:
                icephys_metadata = json.load(json_file)
        else:
            icephys_metadata = dict()

        # Recordings sessions metadata (one Session is one abf file / neo reader)
        icephys_sessions = icephys_metadata.get("recording_sessions", dict())

        # LabMetadata
        if any(x in icephys_metadata for x in ("cell_id", "slice_id", "targeted_layer", "inferred_layer")):
            metadata["ndx-dandi-icephys"] = dict(
                # Required fields for DANDI
                cell_id=icephys_metadata.get("cell_id"),
                slice_id=icephys_metadata.get("slice_id"),
                # Lab specific metadata
                targeted_layer=icephys_metadata.get("targeted_layer", ""),
                inferred_layer=icephys_metadata.get("inferred_layer", ""),
            )

        # Extract start_time info
        first_reader = self.readers_list[0]
        first_session_time = get_start_datetime(neo_reader=first_reader)
        session_start_time = first_session_time.strftime("%Y-%m-%dT%H:%M:%S%z")

        metadata["NWBFile"].update(session_start_time=session_start_time)
        metadata["Icephys"]["Sessions"] = list()

        # Extract useful metadata from each reader in the sequence
        i = 0
        ii = 0
        iii = 0
        for ir, reader in enumerate(self.readers_list):
            # Get extra info from metafile, if present
            abf_file_name = Path(reader.filename).name
            item = [s for s in icephys_sessions if Path(s.get("abf_file_name", "")).name == abf_file_name]
            extra_info = item[0] if len(item) > 0 else dict()
            abfDateTime = get_start_datetime(neo_reader=reader)

            # Calculate session start time relative to first abf file (first session), in seconds
            relative_session_start_time = abfDateTime - first_session_time
            relative_session_start_time = float(relative_session_start_time.seconds)

            metadata["Icephys"]["Sessions"].append(
                dict(
                    name=abf_file_name,
                    relative_session_start_time=relative_session_start_time,
                    icephys_experiment_type=extra_info.get("icephys_experiment_type", None),
                    stimulus_type=extra_info.get("stimulus_type", "not described"),
                    recordings=list(),
                )
            )

            n_segments = get_number_of_segments(reader, block=0)
            n_electrodes = get_number_of_electrodes(reader)

            # Loop through segments (sequential recordings table)
            for sg in range(n_segments):
                # Loop through channels (simultaneous recordings table)
                for el in range(n_electrodes):
                    metadata["Icephys"]["Sessions"][ir]["recordings"].append(
                        dict(
                            intracellular_recordings_table_ind=i,
                            simultaneous_recordings_table_ind=ii,
                            sequential_recordings_table_ind=iii,
                            # repetitions_table_id=0,
                            # experimental_conditions_table_id=0
                        )
                    )
                    i += 1
                ii += 1
            iii += 1

        return metadata

    def set_aligned_starting_time(self, aligned_starting_time: float):
        for reader in self.readers_list:
            number_of_segments = reader.header["nb_segment"][0]
            for segment_index in range(number_of_segments):
                reader._t_starts[segment_index] += aligned_starting_time

    def set_aligned_segment_starting_times(
        self, aligned_segment_starting_times: list[list[float]], stub_test: bool = False
    ):
        """
        Align the individual starting time for each video in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_starting_times : list of list of floats
            The relative starting times of each video.
            Outer list is over file paths (readers).
            Inner list is over segments of each recording.
        stub_test : bool, default=False
        """
        number_of_files_from_starting_times = len(aligned_segment_starting_times)
        assert number_of_files_from_starting_times == len(self.readers_list), (
            f"The length of the outer list of 'starting_times' ({number_of_files_from_starting_times}) "
            "does not match the number of files ({len(self.readers_list)})!"
        )

        for file_index, (reader, aligned_segment_starting_times_by_file) in enumerate(
            zip(self.readers_list, aligned_segment_starting_times)
        ):
            number_of_segments = reader.header["nb_segment"][0]
            assert number_of_segments == len(
                aligned_segment_starting_times_by_file
            ), f"The length of starting times index {file_index} does not match the number of segments of that reader!"

            reader._t_starts = aligned_segment_starting_times_by_file
