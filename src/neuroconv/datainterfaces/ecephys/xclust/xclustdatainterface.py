from typing import Optional

from pydantic import DirectoryPath, FilePath

from ..basesortingextractorinterface import BaseSortingExtractorInterface


class XClustSortingInterface(BaseSortingExtractorInterface):
    """Primary data interface class for converting XClust (.CEL) spike sorting data."""

    display_name = "XClust Sorting"
    associated_suffixes = (".CEL",)
    info = "Interface for XClust (.CEL) spike sorting data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.xclustextractors import XClustSortingExtractor

        return XClustSortingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"] = {
            "folder_path": {
                "type": "string",
                "format": "directory",
                "description": "Path to folder containing .CEL files.",
            },
            "file_path_list": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of paths to .CEL files.",
            },
            "sampling_frequency": {
                "type": "number",
                "description": "Sampling frequency of the original recording in Hz.",
            },
        }
        source_schema["required"] = ["sampling_frequency"]
        return source_schema

    def __init__(
        self,
        *,
        folder_path: Optional[DirectoryPath] = None,
        file_path_list: Optional[list[FilePath]] = None,
        sampling_frequency: float,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """
        Initialize the XClust sorting interface.

        Parameters
        ----------
        folder_path : DirectoryPath, optional
            Path to a folder containing .CEL files.
        file_path_list : list of FilePath, optional
            Explicit list of .CEL file paths.
        sampling_frequency : float
            Sampling frequency of the original recording in Hz.
        verbose : bool, default: False
            Whether to print verbose output.
        metadata_key : str, optional
            Key of this sorting's entry in ``metadata["Ecephys"]["Sortings"]``. Defaults to ``"xclust_sorting"``.
        """
        if folder_path is not None and file_path_list is not None:
            raise ValueError("Specify either 'folder_path' or 'file_path_list', not both.")
        if folder_path is None and file_path_list is None:
            raise ValueError("Must specify either 'folder_path' or 'file_path_list'.")

        self.metadata_key = metadata_key or "xclust_sorting"
        super().__init__(
            verbose=verbose,
            folder_path=folder_path,
            file_path_list=file_path_list,
            sampling_frequency=sampling_frequency,
        )
