import warnings
from typing import Literal

from pydantic import FilePath

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import ArrayType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Interface for HDF5 imaging data."""

    display_name = "HDF5 Imaging"
    associated_suffixes = (".h5", ".hdf5")
    info = "Interface for HDF5 imaging data."

    @classmethod
    def get_extractor_class(cls):
        from roiextractors import Hdf5ImagingExtractor

        return Hdf5ImagingExtractor

    def __init__(
        self,
        file_path: FilePath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        mov_field: str = "mov",
        sampling_frequency: float | None = None,
        start_time: float | None = None,
        metadata: dict | None = None,
        channel_names: ArrayType | None = None,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
    ):
        """

        Parameters
        ----------
        file_path : FilePath
            Path to .h5 or .hdf5 file.
        mov_field : str, default: 'mov'
        sampling_frequency : float, optional
        start_time : float, optional
        metadata : dict, optional
        channel_names : list of str, optional
        verbose : bool, default: False
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "mov_field",
                "sampling_frequency",
                "start_time",
                "metadata",
                "channel_names",
                "verbose",
                "photon_series_type",
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
                f"Passing arguments positionally to Hdf5ImagingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            mov_field = positional_values.get("mov_field", mov_field)
            sampling_frequency = positional_values.get("sampling_frequency", sampling_frequency)
            start_time = positional_values.get("start_time", start_time)
            metadata = positional_values.get("metadata", metadata)
            channel_names = positional_values.get("channel_names", channel_names)
            verbose = positional_values.get("verbose", verbose)
            photon_series_type = positional_values.get("photon_series_type", photon_series_type)

        super().__init__(
            file_path=file_path,
            mov_field=mov_field,
            sampling_frequency=sampling_frequency,
            start_time=start_time,
            metadata=metadata,
            channel_names=channel_names,
            verbose=verbose,
            photon_series_type=photon_series_type,
        )
