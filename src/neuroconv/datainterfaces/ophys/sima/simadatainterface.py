import warnings

from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class SimaSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for SimaSegmentationExtractor."""

    display_name = "SIMA Segmentation"
    associated_suffixes = (".sima",)
    info = "Interface for SIMA segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import SimaSegmentationExtractor

        return SimaSegmentationExtractor

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        sima_segmentation_label: str = "auto_ROIs",
        metadata_key: str | None = None,
    ):
        """

        Parameters
        ----------
        file_path : FilePath
        sima_segmentation_label : str, default: "auto_ROIs"
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "sima_segmentation".
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "sima_segmentation_label",
            ]
            num_positional_args_before_args = 1  # file_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to SimaSegmentationInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            sima_segmentation_label = positional_values.get("sima_segmentation_label", sima_segmentation_label)

        if metadata_key is None:
            metadata_key = "sima_segmentation"

        super().__init__(
            file_path=file_path, sima_segmentation_label=sima_segmentation_label, metadata_key=metadata_key
        )

    def get_metadata(self, *, use_new_metadata_format: bool = False):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with SIMA."},
                },
            }
            return metadata

        return super().get_metadata()
