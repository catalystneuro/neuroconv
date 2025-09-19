from datetime import datetime, timedelta
from pathlib import Path
from warnings import warn

from pydantic import FilePath
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict, get_schema_from_hdmf_class


class AxonRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface class for converting extracellular data recorded in Axon Binary Format (ABF) data.

    Uses the :py:func:`~spikeinterface.extractors.read_axon` reader from SpikeInterface.
    """

    display_name = "Axon Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("axon", "abf")
    associated_suffixes = (".abf",)
    info = "Interface for extracellular data recorded in Axon Binary Format (ABF) recordings."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to an Axon Binary Format (.abf) file"
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs["all_annotations"] = True

        return extractor_kwargs

    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Load and prepare raw data and corresponding metadata from the Axon Binary Format (.abf files).

        Parameters
        ----------
        file_path : FilePath
            Path to an Axon Binary Format (.abf) file
        verbose : bool, default: False
            Verbose
        es_key : str, default: "ElectricalSeries"
            The key for the ElectricalSeries in the metadata
        """

        self.file_path = Path(file_path)

        init_kwargs = dict(
            file_path=self.file_path,
            verbose=verbose,
            es_key=es_key,
        )

        super().__init__(**init_kwargs)

    def _get_start_datetime(self, neo_reader):
        """
        Get start datetime for ABF file.

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

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        ecephys_metadata = metadata["Ecephys"]

        # Extract session start time from ABF file using the existing neo_reader
        neo_reader = self.recording_extractor.neo_reader
        session_start_time = self._get_start_datetime(neo_reader)
        session_start_time_str = session_start_time.strftime("%Y-%m-%dT%H:%M:%S%z")
        metadata["NWBFile"].update(session_start_time=session_start_time_str)

        # Add device information
        axon_device = dict(
            name="Axon Instruments",
            description="Axon Instruments data acquisition system (pCLAMP/AxoScope)",
            manufacturer="Molecular Devices",
        )
        device_list = [axon_device]
        ecephys_metadata.update(Device=device_list)

        # Update electrode groups with device information
        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"]
        for electrode_group in electrode_group_metadata:
            electrode_group["device"] = axon_device["name"]

        # Add electrical series metadata
        ecephys_metadata.update(
            ElectricalSeriesRaw=dict(
                name="ElectricalSeriesRaw", description="Raw acquisition traces from Axon Binary Format file."
            ),
        )

        return metadata
