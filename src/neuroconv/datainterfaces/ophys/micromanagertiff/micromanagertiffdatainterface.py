import warnings

from dateutil.parser import parse
from pydantic import DirectoryPath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import DeepDict


class MicroManagerTiffImagingInterface(BaseImagingExtractorInterface):
    """Data Interface for MicroManagerTiffImagingExtractor."""

    display_name = "Micro-Manager TIFF Imaging"
    associated_suffixes = (".ome", ".tif", ".json")
    info = "Interface for Micro-Manager TIFF imaging data."

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Get the source schema for the Micro-Manager TIFF imaging interface.

        Returns
        -------
        dict
            The schema dictionary containing input parameters and descriptions
            for initializing the Micro-Manager TIFF interface.
        """
        source_schema = super().get_source_schema()

        source_schema["properties"]["folder_path"]["description"] = "The folder containing the OME-TIF image files."
        return source_schema

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import MicroManagerTiffImagingExtractor

        return MicroManagerTiffImagingExtractor

    @validate_call
    def __init__(
        self, folder_path: DirectoryPath, *args, verbose: bool = False
    ):  # TODO: change to * (keyword only) on or after August 2026
        """
        Data Interface for MicroManagerTiffImagingExtractor.

        Parameters
        ----------
        folder_path : DirectoryPath
            The folder path that contains the OME-TIF image files (.ome.tif files) and
           the 'DisplaySettings' JSON file.
        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "verbose",
            ]
            num_positional_args_before_args = 1  # folder_path
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
                f"Passing arguments positionally to MicroManagerTiffImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            verbose = positional_values.get("verbose", verbose)

        super().__init__(folder_path=folder_path)
        self.verbose = verbose
        # Micro-Manager uses "Default" as channel name, for clarity we rename it to  'OpticalChannelDefault'
        channel_name = self.imaging_extractor._channel_names[0]
        self.imaging_extractor._channel_names = [f"OpticalChannel{channel_name}"]

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Micro-Manager TIFF imaging data.

        Returns
        -------
        dict
            Dictionary containing metadata including session start time, imaging plane details,
            and two-photon series configuration.
        """
        metadata = super().get_metadata()

        micromanager_metadata = self.imaging_extractor.micromanager_metadata
        session_start_time = parse(micromanager_metadata["Summary"]["StartTime"])
        metadata["NWBFile"].update(session_start_time=session_start_time)

        imaging_plane_metadata = metadata["Ophys"]["ImagingPlane"][0]
        imaging_plane_metadata.update(
            imaging_rate=self.imaging_extractor.get_sampling_frequency(),
        )
        metadata["Ophys"]["TwoPhotonSeries"][0].update(
            unit="px",
            format="tiff",
        )

        return metadata
