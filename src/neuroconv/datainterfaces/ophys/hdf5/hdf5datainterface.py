from typing import Literal

from pydantic import ConfigDict, FilePath, validate_call

from ..baseimagingextractorinterface import BaseImagingExtractorInterface
from ....utils import ArrayType


class Hdf5ImagingInterface(BaseImagingExtractorInterface):
    """Interface for HDF5 imaging data."""

    display_name = "HDF5 Imaging"
    associated_suffixes = (".h5", ".hdf5")
    info = "Interface for HDF5 imaging data."

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath,
        mov_field: str = "mov",
        sampling_frequency: float | None = None,
        start_time: float | None = None,
        metadata: dict | None = None,
        channel_names: ArrayType | None = None,
        verbose: bool = False,
        photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
        metadata_key: str = "default",
    ):
        """

        Parameters
        ----------
        file_path : FilePath
            Path to .h5 or .hdf5 file.
        mov_field : str, default: 'mov'
            The field in the HDF5 file containing the movie data.
        sampling_frequency : float, optional
            The sampling frequency in Hz.
        start_time : float, optional
            The start time of the imaging data.
        metadata : dict, optional
            Additional metadata to include.
        channel_names : list of str, optional
            Names of the channels.
        verbose : bool, default: False
            Whether to print verbose output.
        photon_series_type : {"OnePhotonSeries", "TwoPhotonSeries"}, default: "TwoPhotonSeries"
            The type of photon series to create.
        metadata_key : str, optional
            The key to use for organizing metadata in the new dictionary structure.
            This single key will be used for Device, ImagingPlane, and PhotonSeries.
            Default is "default".
        """
        super().__init__(
            file_path=file_path,
            mov_field=mov_field,
            sampling_frequency=sampling_frequency,
            start_time=start_time,
            metadata=metadata,
            channel_names=channel_names,
            verbose=verbose,
            photon_series_type=photon_series_type,
            metadata_key=metadata_key,
        )
