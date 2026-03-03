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
        self, file_path: FilePath, *args, sima_segmentation_label: str = "auto_ROIs"
    ):  # TODO: change to * (keyword only) on or after August 2026
        """

        Parameters
        ----------
        file_path : FilePath
        sima_segmentation_label : str, default: "auto_ROIs"
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

        super().__init__(file_path=file_path, sima_segmentation_label=sima_segmentation_label)
