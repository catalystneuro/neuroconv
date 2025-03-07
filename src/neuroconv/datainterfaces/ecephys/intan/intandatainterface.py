from pathlib import Path

from pydantic import FilePath
from pynwb.ecephys import ElectricalSeries

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_schema_from_hdmf_class


class IntanRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting Intan data using the

    :py:class:`~spikeinterface.extractors.IntanRecordingExtractor`.
    """

    display_name = "Intan Recording"
    associated_suffixes = (".rhd", ".rhs")
    info = "Interface for Intan recording data."
    stream_id = "0"  # This are the amplifier channels, corresponding to the stream_name 'RHD2000 amplifier channel'

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to either a .rhd or a .rhs file"
        return source_schema

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        extractor_kwargs = source_data.copy()
        extractor_kwargs["all_annotations"] = True
        extractor_kwargs["stream_id"] = self.stream_id

        return extractor_kwargs

    def __init__(
        self,
        file_path: FilePath,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        ignore_integrity_checks: bool = False,
    ):
        """
        Load and prepare raw data and corresponding metadata from the Intan format (.rhd or .rhs files).

        Parameters
        ----------
        file_path : FilePath
            Path to either a rhd or a rhs file

        verbose : bool, default: False
            Verbose
        es_key : str, default: "ElectricalSeries"
        ignore_integrity_checks, bool, default: False.
            If True, data that violates integrity assumptions will be loaded. At the moment the only integrity
            check performed is that timestamps are continuous. If False, an error will be raised if the check fails.
        """

        self.file_path = Path(file_path)

        init_kwargs = dict(
            file_path=self.file_path,
            verbose=verbose,
            es_key=es_key,
            ignore_integrity_checks=ignore_integrity_checks,
        )

        super().__init__(**init_kwargs)

    def get_metadata_schema(self) -> dict:
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            ElectricalSeriesRaw=get_schema_from_hdmf_class(ElectricalSeries)
        )
        return metadata_schema

    def get_metadata(self) -> dict:
        metadata = super().get_metadata()
        ecephys_metadata = metadata["Ecephys"]

        # Add device

        system = self.file_path.suffix  # .rhd or .rhs
        device_description = {".rhd": "RHD Recording System", ".rhs": "RHS Stim/Recording System"}[system]

        intan_device = dict(
            name="Intan",
            description=device_description,
            manufacturer="Intan",
        )
        device_list = [intan_device]
        ecephys_metadata.update(Device=device_list)

        electrode_group_metadata = ecephys_metadata["ElectrodeGroup"]
        for electrode_group in electrode_group_metadata:
            electrode_group["device"] = intan_device["name"]
        # Add electrodes and electrode groups
        ecephys_metadata.update(
            ElectricalSeriesRaw=dict(name="ElectricalSeriesRaw", description="Raw acquisition traces."),
        )

        return metadata
