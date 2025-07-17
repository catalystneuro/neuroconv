from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class CaimanSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for CaimanSegmentationExtractor."""

    display_name = "CaImAn Segmentation"
    associated_suffixes = (".hdf5",)
    info = "Interface for CaImAn segmentation data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the CaImAn segmentation interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the CaImAn segmentation interface.
        """
        source_metadata = super().get_source_schema()
        source_metadata["properties"]["file_path"]["description"] = "Path to .hdf5 file."
        return source_metadata

    def __init__(self, file_path: FilePath, verbose: bool = False):
        """
        Parameters
        ----------
        file_path : FilePath
            Path to .hdf5 file.
        verbose : bool, default False
            Whether to print progress
        """
        super().__init__(file_path=file_path)
        self.verbose = verbose

    def add_to_nwbfile(self, nwbfile, include_quality_metrics: bool = True, **kwargs):
        """
        Add CaImAn segmentation data to NWBFile with optional quality metrics.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the segmentation data to.
        include_quality_metrics : bool, default: True
            Whether to include quality metrics as columns in the PlaneSegmentation table.

            Available CaImAn quality metrics (if present in the HDF5 file):
            - snr: Signal-to-noise ratio for each component
            - r_values: Spatial correlation values for each component
            - cnn_preds: CNN classifier predictions for component quality (0-1, higher = more neuron-like)

            These metrics are automatically stored as properties in the CaImAn segmentation
            extractor during initialization and will be added as columns if available.

        """
        super().add_to_nwbfile(nwbfile=nwbfile, include_quality_metrics=include_quality_metrics)
