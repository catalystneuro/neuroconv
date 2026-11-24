from pydantic import FilePath, validate_call

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class NeuroExplorerSortingInterface(BaseSortingExtractorInterface):
    """
    Data interface for the sorted units of NeuroExplorer files.

    Uses :py:func:`~spikeinterface.extractors.read_neuroexplorer_sorting` from SpikeInterface.
    """

    display_name = "NeuroExplorer Sorting"
    associated_suffixes = (".nex",)
    info = "Interface for the sorted units of NeuroExplorer files."

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["file_path"]["description"] = "Path to the NeuroExplorer file (.nex)."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import NeuroExplorerSortingExtractor

        return NeuroExplorerSortingExtractor

    @validate_call
    def __init__(self, file_path: FilePath, *, verbose: bool = False, metadata_key: str | None = None):
        """
        Load the neuron variables of a NeuroExplorer file as units.

        Parameters
        ----------
        file_path : FilePath
            Path to the NeuroExplorer file (.nex).
        verbose : bool, default: False
            Allows verbosity.
        metadata_key : str, optional
            Key of this sorting's entry in ``metadata["Ecephys"]["Sortings"]``. Defaults to
            ``"neuroexplorer_sorting"``.
        """
        self.metadata_key = metadata_key or "neuroexplorer_sorting"
        super().__init__(file_path=file_path, verbose=verbose)
