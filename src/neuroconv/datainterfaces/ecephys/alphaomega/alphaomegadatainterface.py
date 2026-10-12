from pydantic import DirectoryPath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict


class AlphaOmegaRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface class for converting AlphaOmega recording data.

    Uses the :py:func:`~spikeinterface.extractors.read_alphaomega` reader from SpikeInterface.
    """

    display_name = "AlphaOmega Recording"
    associated_suffixes = (".mpx",)
    info = "Interface class for converting AlphaOmega recording data."
    stream_id = "RAW"

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["folder_path"]["description"] = "Path to the folder of .mpx files."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            AlphaOmegaRecordingExtractor,
        )

        return AlphaOmegaRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to add stream_id parameter."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs["stream_id"] = self.stream_id
        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        folder_path: DirectoryPath,
        *,
        verbose: bool = False,
        es_key: str | None = None,
        metadata_key: str | None = None,
    ):
        """
        Load and prepare data for AlphaOmega.

        Parameters
        ----------
        folder_path: string or Path
            Path to the folder of .mpx files.
        verbose: boolean
            Allows verbose.
            Default is False.
        es_key: str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"alpha_omega_recording"``.
        """

        super().__init__(folder_path=folder_path, verbose=verbose, es_key=es_key, metadata_key=metadata_key)

        if metadata_key is None:
            self.metadata_key = "alpha_omega_recording"

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)
        annotation = self.recording_extractor.neo_reader.raw_annotations
        metadata["NWBFile"].update(session_start_time=annotation["blocks"][0]["rec_datetime"])
        return metadata
