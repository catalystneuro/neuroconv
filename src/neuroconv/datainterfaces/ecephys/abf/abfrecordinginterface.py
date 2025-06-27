"""Data interface for Axon ABF extracellular recording files."""

from pydantic import FilePath, validate_call

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_json_schema_from_method_signature


class AbfRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface for ABF extracellular recording files.
    
    This interface treats ABF files as extracellular electrophysiology
    recording data, suitable for multi-electrode array recordings.
    For intracellular data, use the AbfInterface instead.
    """

    display_name = "ABF Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("axon", "abf")
    associated_suffixes = (".abf",)
    info = "Interface for ABF extracellular recording data from Axon instruments."

    # We'll use the Neo-based extractor directly
    ExtractorName = "NeoBaseRecordingExtractor"
    ExtractorModuleName = "spikeinterface.extractors.neoextractors.neobaseextractor"

    @classmethod
    def get_source_schema(cls) -> dict:
        """Get the schema for the source data."""
        source_schema = get_json_schema_from_method_signature(
            method=cls.__init__, exclude=["stream_id", "stream_name", "block_index"]
        )
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(
            description="Path to ABF file."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        stream_id: str | None = None,
        stream_name: str | None = None,
        block_index: int | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of ABF file as extracellular recording data.

        Parameters
        ----------
        file_path : FilePath
            Path to ABF file.
        stream_id : str, optional
            If there are several streams, specify the stream id you want to load.
        stream_name : str, optional
            If there are several streams, specify the stream name you want to load.
        block_index : int, optional
            If there are several blocks, specify the block index you want to load.
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        """
        # Use Neo AxonIO through the base class
        super().__init__(
            file_path=file_path,
            stream_id=stream_id,
            stream_name=stream_name,
            block_index=block_index,
            verbose=verbose,
            es_key=es_key,
        )

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """Convert source data to extractor kwargs."""
        extractor_kwargs = source_data.copy()
        extractor_kwargs["all_annotations"] = True
        return extractor_kwargs