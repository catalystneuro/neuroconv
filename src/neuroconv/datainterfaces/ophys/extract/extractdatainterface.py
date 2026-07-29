import warnings

from pydantic import FilePath

from ..basesegmentationextractorinterface import BaseSegmentationExtractorInterface


class ExtractSegmentationInterface(BaseSegmentationExtractorInterface):
    """Data interface for ExtractSegmentationExtractor."""

    display_name = "EXTRACT Segmentation"
    associated_suffixes = (".mat",)
    info = "Interface for EXTRACT segmentation."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import ExtractSegmentationExtractor

        return ExtractSegmentationExtractor

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        sampling_frequency: float,
        output_struct_name: str | None = None,
        verbose: bool = False,
        metadata_key: str | None = None,
    ):
        """

        Parameters
        ----------
        file_path : FilePath
        sampling_frequency : float
        output_struct_name : str, optional
        verbose: bool, default : True
        metadata_key : str, optional
            Metadata key for this interface. When None, defaults to "extract_segmentation".
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "sampling_frequency",
                "output_struct_name",
                "verbose",
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
                f"Passing arguments positionally to ExtractSegmentationInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            output_struct_name = positional_values.get("output_struct_name", output_struct_name)
            verbose = positional_values.get("verbose", verbose)

        if metadata_key is None:
            metadata_key = "extract_segmentation"

        self.verbose = verbose
        super().__init__(
            file_path=file_path,
            sampling_frequency=sampling_frequency,
            output_struct_name=output_struct_name,
            metadata_key=metadata_key,
        )

    def get_metadata(self, *, use_new_metadata_format: bool = False):
        if use_new_metadata_format:
            metadata = super().get_metadata(use_new_metadata_format=True)
            metadata["Ophys"] = {
                "PlaneSegmentations": {
                    self.metadata_key: {"description": "Segmentation data acquired with EXTRACT."},
                },
            }
            return metadata

        return super().get_metadata()
