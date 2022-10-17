"""Author: Luiz Tauffer."""
import json
from datetime import datetime, timedelta
from warnings import warn

from ..baseicephysinterface import BaseIcephysInterface


def get_start_datetime(neo_reader):
    """Get start datetime for Abf file."""
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

    ExtractorName = "AxonIO"

    @classmethod
    def get_source_schema(cls):
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

    def __init__(self, file_paths: list, icephys_metadata: dict = None, icephys_metadata_file_path: str = None):
        """
        ABF IcephysInterface based on Neo AxonIO.

        Parameters
        ----------
            file_paths: list
                List of files to be converted to the same nwb file.
            icephys_metadata: dict, optional
                Dictionary containing the Icephys-specific metadata. Defaults to None.
            icephys_metadata_file_path: str, optional
                JSON file containing the Icephys-specific metadata. Defaults to None.
        """
        super().__init__(file_paths=file_paths)
        self.source_data["icephys_metadata"] = icephys_metadata
        self.source_data["icephys_metadata_file_path"] = icephys_metadata_file_path

    def get_metadata(self):
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
            abf_file_name = reader.filename.split("/")[-1]
            item = [s for s in icephys_sessions if s.get("abf_file_name", "") == abf_file_name]
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
