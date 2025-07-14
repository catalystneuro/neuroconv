
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

    def get_plane_segmentation_columns(self) -> dict[str, dict[str, any]]:
        """
        Get quality metrics to be added as columns to the PlaneSegmentation table.

        Returns
        -------
        dict
            Dictionary where keys are column names and values are dictionaries
            containing 'data' and 'description' for each quality metric.
        """
        segmentation_extractor = self.segmentation_extractor
        columns = {}

        # Get all ROI IDs
        roi_ids = segmentation_extractor.get_roi_ids()

        # Signal-to-noise ratio
        if hasattr(segmentation_extractor, "_property_data") and "snr" in segmentation_extractor._property_data:
            snr_values = segmentation_extractor.get_property(key="snr", ids=roi_ids)
            columns["snr"] = {"data": snr_values, "description": "Signal-to-noise ratio for each component"}

        # Spatial correlation values
        if hasattr(segmentation_extractor, "_property_data") and "r_values" in segmentation_extractor._property_data:
            r_values = segmentation_extractor.get_property(key="r_values", ids=roi_ids)
            columns["r_values"] = {"data": r_values, "description": "Spatial correlation values for each component"}

        # CNN predictions
        if hasattr(segmentation_extractor, "_property_data") and "cnn_preds" in segmentation_extractor._property_data:
            cnn_preds = segmentation_extractor.get_property(key="cnn_preds", ids=roi_ids)
            columns["cnn_preds"] = {
                "data": cnn_preds,
                "description": "CNN classifier predictions for component quality (0-1, higher = more neuron-like)",
            }

        return columns

    def add_to_plane_segmentation(self, plane_segmentation):
        """
        Add quality metrics as columns to a PlaneSegmentation table.

        Parameters
        ----------
        plane_segmentation : pynwb.ophys.PlaneSegmentation
            The PlaneSegmentation object to add quality metrics to.
        """
        columns = self.get_plane_segmentation_columns()

        for column_name, column_info in columns.items():
            plane_segmentation.add_column(
                name=column_name, description=column_info["description"], data=column_info["data"]
            )
