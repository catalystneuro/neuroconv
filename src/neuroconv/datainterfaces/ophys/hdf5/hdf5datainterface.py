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
        sampling_frequency: float = None,
        start_time: float = None,
        metadata: dict = None,
        channel_names: ArrayType = None,
        verbose: bool = True,
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
        verbose : bool, default: True
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
        )
